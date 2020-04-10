from dataclasses import dataclass
import json
import logging
from quizzes_db import Message, QuizzesDb
import telegram.ext
from typing import Dict, Set


class TelegramQuizError(Exception):
    pass


@dataclass
class Strings:
    registration_invitation: str = ''
    registration_confirmation: str = ''
    answer_confirmation: str = ''


class TelegramQuiz:
    def __init__(self, *, id: str,
                 bot_token: str,
                 quizzes_db: QuizzesDb,
                 number_of_questions: int,
                 strings_file: str,
                 language: str,
                 logger: logging.Logger):
        self.id = id
        self.quizzes_db = quizzes_db
        self.logger = logger
        self.teams: Dict[int, str] = quizzes_db.select_teams(quiz_id=id)
        self.answers: Dict[int, Dict[int, str]
                           ] = quizzes_db.select_all_answers(quiz_id=id)
        self.registration_handler: telegram.ext.MessageHandler = None
        self.question_handler: telegram.ext.MessageHandler = None
        self.question_set: Set[str] = {f'{i:02}' for i in range(
            1, number_of_questions + 1)}
        self.number_of_questions = number_of_questions
        self.question_id: str = None
        self.updater = telegram.ext.Updater(bot_token, use_context=True)
        self.language = language
        self.strings: Strings = self._get_strings(strings_file, language)

    def _get_strings(self, strings_file: str, language: str) -> Strings:
        try:
            with open(strings_file) as file:
                content = file.read()
        except Exception as e:
            raise TelegramQuizError(f'Could not read file {strings_file}: {e}')

        try:
            obj = json.loads(content)
        except json.JSONDecodeError as e:
            raise TelegramQuizError(f'Could not parse file {strings_file}: {e}')

        if language not in obj:
            raise TelegramQuizError(f'Language {language} is not supported in file {strings_file}')

        strings = Strings()
        for string in ("registration_invitation", "registration_confirmation", "answer_confirmation"):
            if string not in obj[language]:
                raise TelegramQuizError(f'String {string} for language {language} not specified in file {strings_file}')
            setattr(strings, string, obj[language][string])

        return strings

    def _handle_registration_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        chat_id = update.message.chat_id
        name = update.message.text
        message: telegram.message.Message = update.message

        if context.chat_data.get('typing_name'):
            del context.chat_data['typing_name']
            name = update.message.text
            timestamp = update.message.date.timestamp()
            self.logger.info(
                f'Registration message. chat_id: {chat_id}, quiz_id: "{self.id}", name: "{name}"')
            message.reply_text(self.strings.registration_confirmation.format(team=name))
            self.quizzes_db.insert_team(
                chat_id=chat_id, quiz_id=self.id, name=name, timestamp=timestamp)
            self.teams[chat_id] = update.message.text
        else:
            self.logger.info(
                f'Requesting a team to send their name. chat_id: {chat_id}, quiz_id: "{self.id}"')
            context.chat_data['typing_name'] = True
            message.reply_text(self.strings.registration_invitation)

    def start_registration(self):
        if self.question_id:
            self.logger.warning(f'Trying to start registration for quiz "{self.id}", '
                                f'but question "{self.question_id}" is already started.')
            raise TelegramQuizError(
                f'Can not start registration of quiz "{self.id}" when question "{self.question_id}" is running.')
        if self.registration_handler:
            self.logger.warning(
                f'Trying to start registration for game "{self.id}", but registration is already running.')
            raise TelegramQuizError(
                f'Can not start registration of quiz "{self.id}" because registration is already on.')
        self.registration_handler = telegram.ext.MessageHandler(
            telegram.ext.Filters.text, self._handle_registration_update)
        self.updater.dispatcher.add_handler(
            self.registration_handler, group=1)
        self.logger.info(f'Registration for game "{self.id}" has started.')

    def stop_registration(self):
        if not self.registration_handler:
            self.logger.warning(
                f'Trying to stop registration for quiz "{self.id}", but registration was not running.')
            raise TelegramQuizError(
                f'Can not stop registration of quiz "{self.id}" because registration is not running.')
        self.updater.dispatcher.remove_handler(
            self.registration_handler, group=1)
        self.registration_handler = None
        self.logger.info(f'Registration for game "{self.id}" has ended.')

    def is_registration(self) -> bool:
        return self.registration_handler is not None

    def _handle_answer_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        chat_id = update.message.chat_id
        answer = update.message.text
        timestamp = update.message.date.timestamp()
        team_name = self.teams.get(chat_id)
        if team_name is None:
            return
        self.logger.info(f'Answer received. '
                         f'question_id: {self.question_id}, quiz_id: {self.id}, chat_id: {chat_id}, '
                         f'team: "{team_name}", answer: "{answer}"')
        self.quizzes_db.insert_answer(chat_id=chat_id, quiz_id=self.id, timestamp=timestamp,
                                      question_id=self.question_id, team_name=team_name, answer=answer)
        update.message.reply_text(self.strings.answer_confirmation.format(answer=answer))
        if self.question_id not in self.answers:
            self.answers[self.question_id] = {}
        self.answers[self.question_id][chat_id] = answer

    def start_question(self, question_id: str):
        if self.registration_handler:
            self.logger.warning(f'Trying to start question "{question_id}" for game "{self.id}", '
                                f'but the registration is not finished.')
            raise TelegramQuizError(
                'Can not start a question during registration.')
        if self.question_id:
            self.logger.warning(f'Trying to start question "{question_id}" for game "{self.id}", '
                                f'but question "{self.question_id}" is already started.')
            raise TelegramQuizError(
                'Can not start a question during another question.')
        if question_id not in self.question_set:
            self.logger.warning(f'Trying to start question "{question_id}" for game "{self.id}", '
                                f'but it is not in the question set.')
            raise TelegramQuizError(
                f'Can not start question "{question_id}" which is not in the question set.')
        self.question_handler = telegram.ext.MessageHandler(
            telegram.ext.Filters.text, self._handle_answer_update)
        self.updater.dispatcher.add_handler(
            self.question_handler, group=1)
        self.question_id = question_id
        self.logger.info(
            f'Question "{question_id}" for game "{self.id}" has started.')

    def stop_question(self):
        if not self.question_id:
            self.logger.warning(
                f'Attempt to stop a question, but no question was running. quiz_id: "{self.id}".')
            raise TelegramQuizError(
                'Can not stop a question, when no question is running.')
        self.updater.dispatcher.remove_handler(
            self.question_handler, group=1)
        self.question_id = None
        self.question_handler = None
        self.logger.info(
            f'Question "{self.question_id}" for game "{self.id}" has ended.')

    def _handle_log_update(self, update: telegram.update.Update, context):
        update_id = update.update_id or 0
        message: telegram.message.Message = update.message
        if not message:
            self.logger.warning(
                f'Telegram update with no message. update_id: {update_id}.')
            return
        timestamp = int(message.date.timestamp()) if message.date else 0
        chat_id = message.chat_id or 0
        text = message.text or ''

        self.logger.info(
            f'message: timestamp:{timestamp}, chat_id:{chat_id}, text: "{text}"')
        self.logger.info('Committing values to database...')
        self.quizzes_db.insert_message(Message(
            timestamp=timestamp, update_id=update_id, chat_id=chat_id, text=text))
        self.logger.info('Committing values to database done.')

    def _handle_error(self, update, context):
        self.logger.error('Update "%s" caused error "%s"',
                          update, context.error)

    def start(self):
        self.updater.dispatcher.add_error_handler(self._handle_error)
        self.updater.dispatcher.add_handler(telegram.ext.MessageHandler(
            telegram.ext.Filters.text, self._handle_log_update))
        self.updater.start_polling()

    def stop(self):
        self.updater.stop()
