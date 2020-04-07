from datetime import datetime
import logging
from telegram_update_logger import TelegramUpdateLogger
import tempfile
import telegram
import unittest
import os
import sqlite3


def _create_update(*, update_id: int, date: datetime, chat_id: int, text: str) -> telegram.update.Update:
    chat = telegram.Chat(chat_id, 'private')
    message = telegram.message.Message(0, None, date, chat=chat, text=text)
    return telegram.update.Update(update_id, message=message)


class TestTelegramUpdateLogger(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'messages.db')
        self.logger = logging.Logger('test')
        self.logger.addHandler(logging.NullHandler())

    def tearDown(self):
        self.test_dir.cleanup()

    def test_init_creates_messages_table(self):
        TelegramUpdateLogger(db_path=self.db_path, logger=self.logger)
        self.assertTrue(os.path.isfile(self.db_path))

        db = sqlite3.connect(self.db_path)
        cursor = db.execute(
            'SELECT name FROM sqlite_master WHERE type = "table" AND name = "messages"')
        self.assertListEqual([('messages',)], cursor.fetchall())
        db.close()

    def test_log_update(self):
        update_logger = TelegramUpdateLogger(
            db_path=self.db_path, logger=logging.Logger('test'))

        db = sqlite3.connect(self.db_path)
        db.execute('''INSERT INTO messages
                          (insert_timestamp, timestamp, update_id, chat_id, text)
                          VALUES (?,?,?,?,?)''', (1, 2, 3, 4, 'existing'))
        db.commit()
        db.close()

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(1001001001),
            chat=telegram.Chat(5001, 'private'), text='Hello, Юнікод! 😎'))

        update_logger.log_update(update, context=None)

        db = sqlite3.connect(self.db_path)
        messages = db.execute(
            'SELECT timestamp, update_id, chat_id, text FROM messages').fetchall()
        db.close()
        self.assertListEqual([
            (2, 3, 4, 'existing'),
            (1001001001, 1001, 5001, 'Hello, Юнікод! 😎'),
        ], messages)


if __name__ == '__main__':
    unittest.main()
