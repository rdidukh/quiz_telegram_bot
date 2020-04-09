import logging
from quizzes_db import QuizzesDb
import telegram.ext
from typing import Dict, Set


class TelegramQuizError(Exception):
    pass


class TelegramQuiz:
    def __init__(self, *, id: str,
                 updater: telegram.ext.Updater,
                 quizzes_db: QuizzesDb,
                 question_set: Set[str],
                 handler_group: int,
                 logger: logging.Logger):
        self.id = id
        self.updater = updater
        self.quizzes_db = quizzes_db
        self.question_set = question_set
        self.logger = logger
        self.handler_group = handler_group
        self.teams: Dict[int, str] = quizzes_db.select_teams(quiz_id=id)
        self.answers: Dict[str, Dict[int, str]
                           ] = quizzes_db.select_all_answers(quiz_id=id)
        self.registration_handler: telegram.ext.MessageHandler = None
        self.question_handler: telegram.ext.MessageHandler = None
        self.question_id = None

    def _handle_registration_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        chat_id = update.message.chat_id
        name = update.message.text
        message: telegram.message.Message = update.message

        if context.chat_data.get('typing_name'):
            del context.chat_data['typing_name']
            name = update.message.text
            self.logger.info(
                f'Registration message. chat_id: {chat_id}, quiz_id: "{self.id}"", name: "{name}"')
            message.reply_text(f'Your team "{name}" has been registered.')
            self.quizzes_db.insert_team(
                chat_id=chat_id, quiz_id=self.id, name=name)
            self.teams[chat_id] = update.message.text
        else:
            self.logger.info(
                f'Requesting a team to send their name. chat_id: {chat_id}, quiz_id: "{self.id}"')
            context.chat_data['typing_name'] = True
            message.reply_text(
                'Registration for game is open. Send us your team name.')

    def start_registration(self):
        if self.registration_handler:
            self.logger.warning(
                f'Trying to start registration for game "{self.id}", but it is already running.')
            return
        self.registration_handler = telegram.ext.MessageHandler(
            telegram.ext.Filters.text, self._handle_registration_update)
        self.updater.dispatcher.add_handler(
            self.registration_handler, group=self.handler_group)
        self.logger.info(f'Registration for game "{self.id}" has started.')

    def stop_registration(self):
        if not self.registration_handler:
            self.logger.warning(
                f'Trying to top registration for game "{self.id}", but it was not running.')
            return
        self.updater.dispatcher.remove_handler(
            self.registration_handler, group=self.handler_group)
        self.registration_handler = None
        self.logger.info(f'Registration for game "{self.id}" has ended.')

    def is_registration(self) -> bool:
        return self.registration_handler is not None

    def _handle_answer_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        chat_id = update.message.chat_id
        answer = update.message.text
        team_name = self.teams.get(chat_id) or ''
        if not team_name:
            self.logger.warning(f'Empty team name. chat_id: {chat_id}, answer: {answer}, '
                                f'quiz_id: {self.id}, question_id: {self.question_id}.')
        self.logger.info(f'Answer received. '
                         f'question_id: {self.question_id}, quiz_id: {self.id}, chat_id: {chat_id}, '
                         f'team: "{team_name}", answer: "{answer}"')
        self.quizzes_db.insert_answer(chat_id=chat_id, quiz_id=self.id,
                                      question_id=self.question_id, team_name=team_name, answer=answer)
        update.message.reply_text(f'You answer received: "{answer}".')
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
            self.question_handler, group=self.handler_group)
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
            self.question_handler, group=self.handler_group)
        self.question_id = None
        self.question_handler = None
        self.logger.info(
            f'Question "{self.question_id}" for game "{self.id}" has ended.')
