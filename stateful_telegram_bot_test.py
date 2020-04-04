from datetime import datetime
import logging
from stateful_telegram_bot import StatefulTelegramBot
import tempfile
import telegram
import telegram.ext
import unittest
import os
import sqlite3


def _create_update(*, update_id: int, date: datetime, chat_id: int, text: str) -> telegram.update.Update:
    chat = telegram.Chat(chat_id, 'private')
    message = telegram.message.Message(0, None, date, chat=chat, text=text)
    return telegram.update.Update(update_id, message=message)


class TestStatefulTelegramBotHandleUpdate(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'messages.db')
        self.logger = logging.Logger('test')
        self.logger.addHandler(logging.NullHandler())

    def tearDown(self):
        self.test_dir.cleanup()

    def test_foo(self):
        bot = StatefulTelegramBot(
            token='123:ABCDEF', logger=self.logger, db_path=self.db_path)

        bot._prepare_db()

        existing_values = [
            (1, 2, 3, 4, 'a', 'existing a'),
            (5, 6, 7, 8, 'b', 'existing b'),
        ]

        db = sqlite3.connect(self.db_path)
        db.executemany(
            'INSERT INTO messages VALUES (?,?,?,?,?,?)', existing_values)
        db.commit()
        db.close()

        updates = [
            _create_update(update_id=1101, date=datetime.fromtimestamp(
                100200300), chat_id=51001, text='Hello'),
            _create_update(update_id=1202, date=datetime.fromtimestamp(
                100200305), chat_id=52002, text='World')
        ]
        context = None

        for update in updates:
            bot._handle_update(update, context)

        foo_updates = [
            _create_update(update_id=1303, date=datetime.fromtimestamp(
                100200310), chat_id=53003, text='Юнікод'),
            _create_update(update_id=1404, date=datetime.fromtimestamp(
                100200315), chat_id=54004, text='Emoji: 😎')
        ]

        bot.set_state('foo')

        for update in foo_updates:
            bot._handle_update(update, context)

        empty_update = _create_update(
            update_id=0, date=None, chat_id=0, text=None)
        bot.set_state('empty')
        bot._handle_update(empty_update, context)

        db = sqlite3.connect(self.db_path)
        messages = db.execute(
            'SELECT timestamp, update_id, chat_id, bot_state, text FROM messages').fetchall()
        self.assertListEqual([
            (2, 3, 4, 'a', 'existing a'),
            (6, 7, 8, 'b', 'existing b'),
            (100200300, 1101, 51001, '', 'Hello'),
            (100200305, 1202, 52002, '', 'World'),
            (100200310, 1303, 53003, 'foo', 'Юнікод'),
            (100200315, 1404, 54004, 'foo', 'Emoji: 😎'),
            (0, 0, 0, 'empty', ''),
        ], messages)
        db.close()


if __name__ == '__main__':
    unittest.main()
