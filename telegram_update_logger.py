from datetime import datetime
import logging
import sqlite3
import telegram
import telegram.ext


class TelegramUpdateLogger:
    def __init__(self, *, db_path: str, logger: logging.Logger):
        self.db_path = db_path
        self.logger = logger
        self._ensure_db()

    def log_update(self, update: telegram.update.Update, context):
        update_id = update.update_id or 0
        message: telegram.message.Message = update.message
        if not message:
            self.logger.warning(f'Telegram update with no message. update_id: {update_id}.')
            return
        insert_timestamp = int(datetime.utcnow().timestamp())
        timestamp = int(message.date.timestamp()) if message.date else 0
        chat_id = message.chat_id or 0
        text = message.text or ''

        self.logger.info(
            f'message: timestamp:{timestamp}, chat_id:{chat_id}, text: "{text}"')

        self.logger.info('Committing values to database...')
        db = sqlite3.connect(self.db_path)
        db.execute('''INSERT INTO messages
                     (insert_timestamp, timestamp, update_id, chat_id, text)
                     VALUES (?, ?, ?, ?, ?)''',
                   (insert_timestamp, timestamp, update_id, chat_id, text))
        db.commit()
        db.close()
        self.logger.info('Committing values to database done.')

    def _ensure_db(self):
        db = sqlite3.connect(self.db_path)
        db.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            insert_timestamp INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            update_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL)''')
        db.commit()
        db.close()
