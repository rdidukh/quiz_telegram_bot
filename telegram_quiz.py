import logging
from quizzes_db import QuizzesDb
import telegram.ext
from typing import Dict


class TelegramQuiz:
    def __init__(self, *, id: str,
                 updater: telegram.ext.Updater,
                 quizzes_db: QuizzesDb,
                 handler_group: int,
                 logger: logging.Logger):
        self.id = id
        self.updater = updater
        self.quizzes_db = quizzes_db
        self.logger = logger
        self.handler_group = handler_group
        self.teams: Dict[int, str] = quizzes_db.select_teams(quiz_id=id)
        self.registration_handler: telegram.ext.MessageHandler = None

    def _handle_registration_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        chat_id = update.message.chat_id
        name = update.message.text
        message: telegram.message.Message = update.message

        if context.chat_data.get('typing_name'):
            del context.chat_data['typing_name']
            name = update.message.text
            self.logger.info(
                f'Registered team. chat_id: {chat_id}, quiz_id: "{self.id}"", name: "{name}"')
            self.quizzes_db.insert_team(
                chat_id=chat_id, quiz_id=self.id, name=name)
            self.teams[chat_id] = update.message.text
            message.reply_text(f'Your team "{name}" has been registered.')
        else:
            self.logger.info(
                f'Requesting a team to send their name. chat_id: {chat_id}, quiz_id: "{self.id}"')
            context.chat_data['typing_name'] = True
            message.reply_text(
                'Registration for game is open. Send us your team name.')

    def start_registration(self):
        if self.registration_handler:
            self.logger.warning(f'Trying to start registration for game "{self.id}", but it is already running.')
            return
        self.registration_handler = telegram.ext.MessageHandler(
            telegram.ext.Filters.text, self._handle_registration_update)
        self.updater.dispatcher.add_handler(
            self.registration_handler, group=self.handler_group)
        self.logger.info(f'Registration for game {self.id} has started.')

    def stop_registration(self):
        if not self.registration_handler:
            self.logger.warning(f'Trying to top registration for game "{self.id}", but it was not running.')
            return
        self.updater.dispatcher.remove_handler(
            self.registration_handler, group=self.handler_group)
        self.registration_handler = None
        self.logger.info(f'Registration for game "{self.id}" has ended.')
