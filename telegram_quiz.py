from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from quiz_db import Answer, Message, QuizDb, Team
import telegram
from telegram.ext import MessageHandler, Updater
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
    send_results_zero_correct_answers: str = ''
    send_results_correct_answers: str = ''


@dataclass
class QuizStatus:
    update_id: int
    quiz_id: Optional[str]
    language: Optional[str]
    question: Optional[int]
    registration: bool
    time: str = field(default=None, compare=False)


@dataclass
class Updates:
    status: QuizStatus
    teams: List[Team]
    answers: List[Answer]


class TelegramQuiz:
    def __init__(self, *, quiz_db: QuizDb, strings_file: str):
        self._quiz_db = quiz_db
        self._strings_file = strings_file
        self._lock = threading.Lock()
        self._id: Optional[str] = None
        self._question: Optional[int] = None
        self._registration_handler: Optional[MessageHandler] = None
        self._question_handler: Optional[MessageHandler] = None
        self._updater: Optional[Updater] = None
        self._language: Optional[str] = None
        self._strings: Optional[Strings] = None
        self._status_update_id = 0
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
        for string in Strings().__dict__:
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
            if self._registration_handler is None:
                logging.warning('Skipping registration update as registration closed.')
                return
            chat_id = update.message.chat_id
            message: telegram.message.Message = update.message

            if context.chat_data.get('typing_name'):
                del context.chat_data['typing_name']
                text = update.message.text
                registration_time = update.message.date.timestamp()

                text = ' '.join(text.split())[:30]

                logging.info(
                    f'Registration message. chat_id: {chat_id}, quiz_id: "{self._id}", name: "{text}"')
                update_id = self._quiz_db.update_team(
                    quiz_id=self._id, team_id=chat_id, name=text, registration_time=registration_time)
                if update_id:
                    message.reply_text(
                        self._strings.registration_confirmation.format(team=text))
                else:
                    logging.warning(
                        f'Outdated registration. quiz_id: "{self._id}", chat_id: {chat_id}, name: {text}')
            else:
                logging.info(
                    f'Requesting a team to send their name. chat_id: {chat_id}, quiz_id: "{self._id}"')
                context.chat_data['typing_name'] = True
                message.reply_text(self._strings.registration_invitation)
        logging.info(
            f'Registration update took {1000*(time.time() - start_time):.3f} ms.')

    def start_registration(self):
        with self._lock:
            if not self._id:
                raise TelegramQuizError('Can not start registration, because quiz is not started.')
            if self._question is not None:
                logging.warning(f'Can not start registration for quiz "{self._id}", '
                                f'because question {self._question} is already started.')
                raise TelegramQuizError(
                    f'Can not start registration of quiz "{self._id}" when question {self._question} is running.')
            if self._registration_handler:
                logging.warning(
                    f'Can not start registration for quiz "{self._id}", because registration is already started.')
                raise TelegramQuizError(
                    f'Can not start registration of quiz "{self._id}" because registration is already started.')
            self._registration_handler = telegram.ext.MessageHandler(
                telegram.ext.Filters.text, self._handle_registration_update)
            self._updater.dispatcher.add_handler(
                self._registration_handler, group=1)
            self._on_status_update()
            logging.info(f'Registration for quiz "{self._id}" has started.')

    def stop_registration(self):
        with self._lock:
            if not self._id:
                logging.warning('Can not stop registration, because quiz is not started.')
                raise TelegramQuizError('Can not stop registration, because quiz is not started.')
            if not self._registration_handler:
                logging.warning(
                    f'Can not stop registration for quiz "{self._id}", because registration is not started.')
                raise TelegramQuizError(
                    f'Can not stop registration of quiz "{self._id}" because registration is not started.')
            self._updater.dispatcher.remove_handler(
                self._registration_handler, group=1)
            self._registration_handler = None
            self._on_status_update()
            logging.info(f'Registration for quiz "{self._id}" has ended.')

    def is_registration(self) -> bool:
        return self._registration_handler is not None

    def _handle_answer_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        start_time = time.time()
        with self._lock:
            if self._question is None:
                logging.warning('Answer update skipped as question is not started.')
                return
            chat_id = update.message.chat_id
            answer = update.message.text
            answer_time = update.message.date.timestamp()

            answer = ' '.join(answer.split())[:50]

            teams = self._quiz_db.get_teams(quiz_id=self._id, team_id=chat_id)
            if not teams:
                return
            team = teams[0]
            logging.info(f'Answer received. '
                         f'question: {self._question}, quiz_id: {self._id}, team_id: {team.id}, '
                         f'team: "{team.name}", answer: "{answer}"')

            update_id = self._quiz_db.update_answer(
                quiz_id=self._id,
                question=self._question,
                team_id=chat_id,
                answer=answer,
                answer_time=answer_time,
            )

            if update_id:
                reply = self._strings.answer_confirmation.format(
                    answer=answer, question=self._question)
                self._updater.dispatcher.run_async(
                    update.message.reply_text, reply)
            else:
                logging.warning(
                    f'Outdated answer. quiz_id: "{self._id}", question: {self._question}, '
                    'team_id: {chat_id}, answer: {answer}, time: {answer_time}')
        logging.info(
            f'Answer update took {1000*(time.time() - start_time):.3f} ms.')

    def start_question(self, question: int):
        with self._lock:
            if not isinstance(question, int):
                raise Exception('Parameter question must be an integer.')
            if not self._id:
                raise TelegramQuizError(
                    f'Can not start question {question}, because quiz is not started.')
            if self._registration_handler:
                logging.warning(f'Can not start question {question} for quiz "{self._id}", '
                                f'because registration is started.')
                raise TelegramQuizError(
                    'Can not start a question during registration.')
            if self._question is not None:
                logging.warning(f'Trying to start question {question} for quiz "{self._id}", '
                                f'but question {self._question} is already started.')
                raise TelegramQuizError(
                    f'Can not start question {question} because question {self._question} is already running.')
            self._question_handler = telegram.ext.MessageHandler(
                telegram.ext.Filters.text, self._handle_answer_update)
            self._updater.dispatcher.add_handler(
                self._question_handler, group=1)
            self._question = question
            self._on_status_update()
            logging.info(
                f'Question {question} for quiz "{self._id}" has started.')

    def stop_question(self):
        with self._lock:
            if not self._id:
                raise TelegramQuizError('Can not stop a question, because quiz is not started.')
            if self._question is None:
                logging.warning(
                    f'Can not stop a question, because question is not started. quiz_id: "{self._id}".')
                raise TelegramQuizError(
                    'Can not stop a question, because question is not started.')
            self._updater.dispatcher.remove_handler(
                self._question_handler, group=1)
            self._question = None
            self._question_handler = None
            self._on_status_update()
            logging.info(
                f'Question {self} for quiz "{self._id}" has stopped.')

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
        self._quiz_db.insert_message(Message(
            timestamp=timestamp, update_id=update_id, chat_id=chat_id, text=text))
        logging.info(
            f'Log update took {1000*(time.time() - start_time):.3f} ms.')

    def _handle_error(self, update, context):
        logging.error('Update "%s" caused error "%s"', update, context.error)

    def start(self, *, quiz_id: str, bot_api_token: str, language: str, updater_factory: Callable[[str], Updater] = None):

        def default_updater_factory(bot_api_token: str):
            return Updater(bot_api_token, use_context=True)

        if not updater_factory:
            updater_factory = default_updater_factory

        with self._lock:
            if self._id:
                raise TelegramQuizError(f'Could not start quiz "{quiz_id}", '
                                        f'because quiz "{self._id}" is already running.')

            self._updater = updater_factory(bot_api_token)
            self._updater.dispatcher.add_error_handler(self._handle_error)
            self._updater.dispatcher.add_handler(telegram.ext.MessageHandler(
                telegram.ext.Filters.text, self._handle_log_update))
            self._updater.start_polling()
            self._id = quiz_id
            self._language = language
            self._strings = self._get_strings(self._strings_file, language)
            self._on_status_update()

    def stop(self):
        with self._lock:
            if not self._id:
                raise TelegramQuizError('Can not stop the quiz as it is not started.')
            self._updater.stop()
            self._updater = None
            self._id = None
            self._language = None
            self._strings = None
            self._registration_handler = None
            self._question_handler = None
            self._on_status_update()

    def _on_status_update(self):
        self._status_update_id += 1
        for sub in self._subscribers:
            try:
                sub()
            except Exception:
                logging.exception('Subscriber raised an error.')

    @property
    def id(self) -> Optional[str]:
        return self._id

    @property
    def status_update_id(self) -> int:
        return self._status_update_id

    @property
    def db(self) -> QuizDb:
        return self._quiz_db

    def get_status(self) -> QuizStatus:
        with self._lock:
            return QuizStatus(
                update_id=self._status_update_id,
                quiz_id=self._id,
                language=self._language,
                question=self._question,
                registration=bool(self._registration_handler),
                time=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            )

    def send_results(self, *, team_id: int) -> None:
        with self._lock:
            if not self._id:
                raise TelegramQuizError(f'Could not send results to team {team_id}, because the quiz is not started.')
            teams = self._quiz_db.get_teams(quiz_id=self._id, team_id=team_id)

            if not teams:
                raise TelegramQuizError(f'Team with id {team_id} does not exist.')

            answers = self._quiz_db.get_answers(
                quiz_id=self._id, team_id=team_id)

            correct_answers = sorted(
                [a.question for a in answers if bool(a.points)])

            if not correct_answers:
                message = self._strings.send_results_zero_correct_answers
            else:
                str_answers = ', '.join(
                    [str(a) for a in correct_answers])
                message = self._strings.send_results_correct_answers.format(
                    correctly_answered_questions=str_answers, total_score=len(correct_answers))

        try:
            self._updater.bot.send_message(team_id, message)
        except telegram.error.TelegramError:
            logging.exception('Send results message error.')
            raise TelegramQuizError('Could not send a message to the user.')
