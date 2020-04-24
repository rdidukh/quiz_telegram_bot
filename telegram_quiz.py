from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from quiz_db import Answer, Message, QuizDb, Team
import telegram.ext
import telegram.update
import threading
import time
from typing import Callable, List, Optional, Set


class TelegramQuizError(Exception):
    pass


@dataclass
class Strings:
    registration_invitation: str = ''
    registration_confirmation: str = ''
    answer_confirmation: str = ''


@dataclass
class QuizStatus:
    update_id: int
    quiz_id: str
    language: str
    question: Optional[int]
    registration: bool
    time: str = field(default=None, compare=False)


@dataclass
class Updates:
    status: QuizStatus
    teams: List[Team]
    answers: List[Answer]


class TelegramQuiz:
    def __init__(self, *, id: str,
                 bot_token: str,
                 quiz_db: QuizDb,
                 strings_file: str,
                 language: str):
        self.id = id
        self.quiz_db = quiz_db
        self.registration_handler: telegram.ext.MessageHandler = None
        self.question_handler: telegram.ext.MessageHandler = None
        self.question: Optional[int] = None
        self.updater = telegram.ext.Updater(bot_token, use_context=True)
        self.language = language
        self.strings: Strings = self._get_strings(strings_file, language)
        self._status_update_id = 0
        self._lock = threading.Lock()
        self._subscribers: Set[Callable[[], None]] = set()

    def _get_strings(self, strings_file: str, language: str) -> Strings:
        try:
            with open(strings_file) as file:
                content = file.read()
        except Exception as e:
            raise TelegramQuizError(f'Could not read file {strings_file}: {e}')

        try:
            obj = json.loads(content)
        except json.JSONDecodeError as e:
            raise TelegramQuizError(
                f'Could not parse file {strings_file}: {e}')

        if language not in obj:
            raise TelegramQuizError(
                f'Language {language} is not supported in file {strings_file}')

        strings = Strings()
        for string in ("registration_invitation", "registration_confirmation", "answer_confirmation"):
            if string not in obj[language]:
                raise TelegramQuizError(
                    f'String {string} for language {language} not specified in file {strings_file}')
            setattr(strings, string, obj[language][string])

        return strings

    def add_updates_subscriber(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._subscribers.add(callback)

    def remove_updates_subscriber(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._subscribers.remove(callback)

    def _handle_registration_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        start_time = time.time()
        with self._lock:
            if self.registration_handler is None:
                return
            chat_id = update.message.chat_id
            message: telegram.message.Message = update.message

            if context.chat_data.get('typing_name'):
                del context.chat_data['typing_name']
                text = update.message.text
                registration_time = update.message.date.timestamp()

                text = ' '.join(text.split())[:30]

                logging.info(
                    f'Registration message. chat_id: {chat_id}, quiz_id: "{self.id}", name: "{text}"')
                update_id = self.quiz_db.update_team(
                    quiz_id=self.id, team_id=chat_id, name=text, registration_time=registration_time)
                if update_id:
                    message.reply_text(
                        self.strings.registration_confirmation.format(team=text))
                else:
                    logging.warning(
                        f'Outdated registration. quiz_id: "{self.id}", chat_id: {chat_id}, name: {text}')
            else:
                logging.info(
                    f'Requesting a team to send their name. chat_id: {chat_id}, quiz_id: "{self.id}"')
                context.chat_data['typing_name'] = True
                message.reply_text(self.strings.registration_invitation)
        logging.info(
            f'Registration update took {1000*(time.time() - start_time):.3f} ms.')

    def start_registration(self):
        with self._lock:
            if self.question is not None:
                logging.warning(f'Trying to start registration for quiz "{self.id}", '
                                f'when question {self.question} is running.')
                raise TelegramQuizError(
                    f'Can not start registration of quiz "{self.id}" when question {self.question} is running.')
            if self.registration_handler:
                logging.warning(
                    f'Trying to start registration for quiz "{self.id}", but registration is already running.')
                raise TelegramQuizError(
                    f'Can not start registration of quiz "{self.id}" because registration is already on.')
            self.registration_handler = telegram.ext.MessageHandler(
                telegram.ext.Filters.text, self._handle_registration_update)
            self.updater.dispatcher.add_handler(
                self.registration_handler, group=1)
            self._on_status_update()
            logging.info(f'Registration for quiz "{self.id}" has started.')

    def stop_registration(self):
        with self._lock:
            if not self.registration_handler:
                logging.warning(
                    f'Trying to stop registration for quiz "{self.id}", but registration was not running.')
                raise TelegramQuizError(
                    f'Can not stop registration of quiz "{self.id}" because registration is not running.')
            self.updater.dispatcher.remove_handler(
                self.registration_handler, group=1)
            self.registration_handler = None
            self._on_status_update()
            logging.info(f'Registration for quiz "{self.id}" has ended.')

    def is_registration(self) -> bool:
        return self.registration_handler is not None

    def _handle_answer_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        start_time = time.time()
        with self._lock:
            if self.question is None:
                return
            chat_id = update.message.chat_id
            answer = update.message.text
            answer_time = update.message.date.timestamp()

            answer = ' '.join(answer.split())[:50]

            teams = self.quiz_db.get_teams(quiz_id=self.id, team_id=chat_id)
            if not teams:
                return
            team = teams[0]
            logging.info(f'Answer received. '
                         f'question: {self.question}, quiz_id: {self.id}, team_id: {team.id}, '
                         f'team: "{team.name}", answer: "{answer}"')

            update_id = self.quiz_db.update_answer(
                quiz_id=self.id,
                question=self.question,
                team_id=chat_id,
                answer=answer,
                answer_time=answer_time,
            )

            if update_id:
                reply = self.strings.answer_confirmation.format(answer=answer)
                self.updater.dispatcher.run_async(
                    update.message.reply_text, reply)
            else:
                logging.warning(
                    f'Outdated answer. quiz_id: "{self.id}", question: {self.question}, '
                    'team_id: {chat_id}, answer: {answer}, time: {answer_time}')
        logging.info(
            f'Answer update took {1000*(time.time() - start_time):.3f} ms.')

    def start_question(self, question: int):
        with self._lock:
            if not isinstance(question, int):
                raise Exception('Parameter question must be an integer.')
            if self.registration_handler:
                logging.warning(f'Trying to start question {question} for quiz "{self.id}", '
                                f'but the registration is not finished.')
                raise TelegramQuizError(
                    'Can not start a question during registration.')
            if self.question is not None:
                logging.warning(f'Trying to start question {question} for quiz "{self.id}", '
                                f'but question {self.question} is already started.')
                raise TelegramQuizError(
                    f'Can not start question {question} because question {self.question} is already running.')
            self.question_handler = telegram.ext.MessageHandler(
                telegram.ext.Filters.text, self._handle_answer_update)
            self.updater.dispatcher.add_handler(
                self.question_handler, group=1)
            self.question = question
            self._on_status_update()
            logging.info(
                f'Question {question} for quiz "{self.id}" has started.')

    def stop_question(self):
        with self._lock:
            if self.question is None:
                logging.warning(
                    f'Attempt to stop a question, but no question was running. quiz_id: "{self.id}".')
                raise TelegramQuizError(
                    'Can not stop a question, when no question is running.')
            self.updater.dispatcher.remove_handler(
                self.question_handler, group=1)
            self.question = None
            self.question_handler = None
            self._on_status_update()
            logging.info(
                f'Question {self} for quiz "{self.id}" has stopped.')

    def _handle_log_update(self, update: telegram.update.Update, context):
        start_time = time.time()
        update_id = update.update_id or 0
        message: telegram.message.Message = update.message
        if not message:
            logging.warning(
                f'Telegram update with no message. update_id: {update_id}.')
            return
        timestamp = int(message.date.timestamp()) if message.date else 0
        chat_id = message.chat_id or 0
        text = message.text or ''

        logging.info(
            f'message: timestamp:{timestamp}, chat_id:{chat_id}, text: "{text}"')
        self.quiz_db.insert_message(Message(
            timestamp=timestamp, update_id=update_id, chat_id=chat_id, text=text))
        logging.info(
            f'Log update took {1000*(time.time() - start_time):.3f} ms.')

    def _handle_error(self, update, context):
        logging.error('Update "%s" caused error "%s"', update, context.error)

    def start(self):
        with self._lock:
            self.updater.dispatcher.add_error_handler(self._handle_error)
            self.updater.dispatcher.add_handler(telegram.ext.MessageHandler(
                telegram.ext.Filters.text, self._handle_log_update))
            self.updater.start_polling()
            self._on_status_update()

    def stop(self):
        # TODO: clean up updater handlers.
        with self._lock:
            self.updater.stop()
            self._on_status_update()

    def _on_status_update(self):
        self._status_update_id += 1
        for sub in self._subscribers:
            try:
                sub()
            except Exception:
                logging.exception('Subscriber raised an error.')

    @property
    def status_update_id(self) -> int:
        return self._status_update_id

    def get_status(self) -> QuizStatus:
        with self._lock:
            return QuizStatus(
                update_id=self._status_update_id,
                quiz_id=self.id,
                language=self.language,
                question=self.question,
                registration=bool(self.registration_handler),
                time=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            )
