import logging
from quizzes_db import Message, QuizzesDb
import tempfile
import unittest
import os
import sqlite3


def _select_messages(db_path: str):
    with sqlite3.connect(db_path) as db:
        return db.execute('SELECT insert_timestamp, timestamp, update_id, chat_id, text FROM messages').fetchall()


class TestQuizzesDb(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'messages.db')
        self.logger = logging.Logger('test')
        self.logger.addHandler(logging.NullHandler())

    def tearDown(self):
        self.test_dir.cleanup()

    def test_insert_message(self):
        quizzes_db = QuizzesDb(db_path=self.db_path)
        message = Message(timestamp=1234567, update_id=1001,
                          chat_id=2001, text='Apple', insert_timestamp=123)
        quizzes_db.insert_message(message)

        self.assertListEqual([
            (123, 1234567, 1001, 2001, 'Apple')
        ], _select_messages(self.db_path))

        message = Message(timestamp=1234568, update_id=1002,
                          chat_id=2002, text='Unicode Юнікод 😎', insert_timestamp=124)
        quizzes_db.insert_message(message)

        self.assertListEqual([
            (123, 1234567, 1001, 2001, 'Apple'),
            (124, 1234568, 1002, 2002, 'Unicode Юнікод 😎')
        ], _select_messages(self.db_path))


if __name__ == '__main__':
    unittest.main()
