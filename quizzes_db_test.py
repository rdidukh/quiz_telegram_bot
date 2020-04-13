from quizzes_db import Answer, Message, QuizzesDb
import tempfile
from typing import Any, Dict, List
import unittest
import os
import sqlite3


def _select_messages(db_path: str):
    with sqlite3.connect(db_path) as db:
        return db.execute('SELECT insert_timestamp, timestamp, update_id, chat_id, text FROM messages').fetchall()


def _select_answers(db_path: str):
    with sqlite3.connect(db_path) as db:
        return db.execute('SELECT quiz_id, question, team_id, answer, timestamp, checked, points FROM answers').fetchall()


def _insert_into_answers(db_path, values: List[Dict[str, Any]]):
    with sqlite3.connect(db_path) as db:
        with db:
            db.executemany('INSERT INTO answers '
                           'VALUES (:quiz_id, :question, :team_id, :answer, :timestamp, :checked, :points)', values)


class TestQuizzesDb(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'messages.db')
        self.quizzes_db = QuizzesDb(db_path=self.db_path)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_insert_message(self):
        message = Message(timestamp=1234567, update_id=1001,
                          chat_id=2001, text='Apple', insert_timestamp=123)
        self.quizzes_db.insert_message(message)

        self.assertListEqual([
            (123, 1234567, 1001, 2001, 'Apple')
        ], _select_messages(self.db_path))

        message = Message(timestamp=1234568, update_id=1002,
                          chat_id=2002, text='Unicode Юнікод 😎', insert_timestamp=124)
        self.quizzes_db.insert_message(message)

        self.assertListEqual([
            (123, 1234567, 1001, 2001, 'Apple'),
            (124, 1234568, 1002, 2002, 'Unicode Юнікод 😎')
        ], _select_messages(self.db_path))

    def test_insert_answer(self):
        answer = Answer(quiz_id='test', question=3, team_id=5001,
                        answer='Unicode Юнікод 😎', timestamp=123, checked=True, points=7)
        self.quizzes_db.insert_answer(answer)

        self.assertListEqual([
            ('test', 3, 5001, 'Unicode Юнікод 😎', 123, True, 7),
        ], _select_answers(self.db_path))

        answer = Answer(quiz_id='other', question=12, team_id=5002,
                        answer='Apple', timestamp=321, id=7654)
        self.quizzes_db.insert_answer(answer)

        self.assertListEqual([
            ('test', 3, 5001, 'Unicode Юнікод 😎', 123, True, 7),
            ('other', 12, 5002, 'Apple', 321, False, 0),
        ], _select_answers(self.db_path))

    def test_get_answers_for_quiz(self):
        _insert_into_answers(self.db_path, [{
            'quiz_id': 'test', 'question': 5, 'team_id': 5001,
            'answer': 'Ignored', 'timestamp': 122, 'checked': True, 'points': 11,
        }, {
            'quiz_id': 'test', 'question': 5, 'team_id': 5001,
            'answer': 'Apple', 'timestamp': 123, 'checked': True, 'points': 11,
        }, {
            'quiz_id': 'ignored', 'question': 1, 'team_id': 5001,
            'answer': 'Ignored', 'timestamp': 321, 'checked': False, 'points': 18,
        }, {
            'quiz_id': 'test', 'question': 9, 'team_id': 5002,
            'answer': 'Unicode Юнікод 😎', 'timestamp': 34, 'checked': False, 'points': 0,
        }])
        answers = self.quizzes_db.get_answers_for_quiz('test')

        self.assertListEqual(sorted([
            Answer(quiz_id='test', question=9, team_id=5002,
                   answer='Unicode Юнікод 😎', timestamp=34, checked=False, points=0),
            Answer(quiz_id='test', question=5, team_id=5001,
                   answer='Apple', timestamp=123, checked=True, points=11),
        ]), sorted(answers))


if __name__ == '__main__':
    unittest.main()
