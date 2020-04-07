import logging
from messages_db import MessagesDb
import telegram
import telegram.ext


class TelegramUpdateLogger:
    def __init__(self, *, messages_db: MessagesDb, logger: logging.Logger):
        self.logger = logger
        self.messages_db = messages_db
        messages_db.create_if_not_exists()

    def log_update(self, update: telegram.update.Update, context):
        update_id = update.update_id or 0
        message: telegram.message.Message = update.message
        if not message:
            self.logger.warning(f'Telegram update with no message. update_id: {update_id}.')
            return
        timestamp = int(message.date.timestamp()) if message.date else 0
        chat_id = message.chat_id or 0
        text = message.text or ''

        self.logger.info(
            f'message: timestamp:{timestamp}, chat_id:{chat_id}, text: "{text}"')
        self.logger.info('Committing values to database...')
        self.messages_db.insert_message(
            timestamp=timestamp, update_id=update_id, chat_id=chat_id, text=text)
        self.logger.info('Committing values to database done.')
