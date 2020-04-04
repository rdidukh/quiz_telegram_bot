from datetime import datetime
import logging
import sqlite3
import telegram


class StatefulTelegramBot:
    def __init__(self, *, token: str, logger: logging.Logger, db_path: str, state: str = ''):
        self.updater = telegram.ext.Updater(token, use_context=True)
        self.logger = logger
        self.db_path = db_path
        self.state = state

    def _handle_update(self, update: telegram.update.Update, context):
        update_id = update.update_id or 0
        message: telegram.message.Message = update.message
        insert_timestamp = int(datetime.utcnow().timestamp())
        timestamp = int(message.date.timestamp()) if message.date else 0
        chat_id = message.chat_id or 0
        text = message.text or ''
        self.logger.info(
            f'message: timestamp:{timestamp}, chat_id:{chat_id}, state: "{self.state}", text: "{text}"')

        self.logger.info('Committing values to database...')
        db = sqlite3.connect(self.db_path)
        db.execute('''
            INSERT INTO messages (insert_timestamp, timestamp, update_id, chat_id, bot_state, text) VALUES (?, ?, ?, ?, ?, ?)
            ''', (insert_timestamp, timestamp, update_id, chat_id, self.state, text))
        db.commit()
        db.close()
        self.logger.info('Committing values to database done.')

    def _prepare_db(self):
        db = sqlite3.connect(self.db_path)
        db.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            insert_timestamp INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            update_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            bot_state TEXT NOT NULL,
            text TEXT NOT NULL)''')
        db.commit()
        db.close()

    def _error_handler(self, update, context):
        self.logger.error('Update "%s" caused error "%s"',
                          update, context.error)

    def start_polling(self):
        self._prepare_db()
        self.updater.dispatcher.add_handler(
            telegram.ext.MessageHandler(telegram.ext.Filters.text, self._handle_update))
        self.updater.dispatcher.add_error_handler(self._error_handler)
        return self.updater.start_polling()

    def stop(self):
        self.updater.stop()

    def set_state(self, state: str):
        self.state = state
