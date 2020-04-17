from quiz_db import Answer, Message, QuizDb, Team
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
        return db.execute('SELECT update_id, quiz_id, question, team_id, answer, timestamp FROM answers').fetchall()


def _select_teams(db_path: str):
    with sqlite3.connect(db_path) as db:
        return db.execute('SELECT update_id, quiz_id, id, name, timestamp FROM teams').fetchall()


def _insert_into_teams(db_path: str, values: List[Dict[str, Any]]):
    with sqlite3.connect(db_path) as db:
        with db:
            db.executemany('INSERT INTO teams '
                           'VALUES (:update_id, :quiz_id, :id, :name, :timestamp)', values)


def _select_update_id(db_path: str):
    with sqlite3.connect(db_path) as db:
        with db:
            return db.execute('SELECT next_update_id FROM counters').fetchall()


def _update_update_id(db_path: str, value: int):
    with sqlite3.connect(db_path) as db:
        with db:
            return db.execute('UPDATE counters SET next_update_id = ?', (value,))


_INITIAL_TEAMS = [
    dict(update_id=1, quiz_id='test', id=5001,
         name='Ignored', timestamp=122),
    dict(update_id=2, quiz_id='test', id=5001,
         name='Unicode Юнікод 😎', timestamp=123),
    dict(update_id=3, quiz_id='ignored',
         id=5001, name='Ignored', timestamp=124),
    dict(update_id=4, quiz_id='test', id=5000,
         name='Another team', timestamp=122),
]


class QuizDbTest(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'messages.db')
        self.quiz_db = QuizDb(db_path=self.db_path)

    def tearDown(self):
        self.test_dir.cleanup()

    def _select_answers(self):
        with sqlite3.connect(self.db_path) as db:
            return db.execute('SELECT update_id, quiz_id, question, team_id, answer, timestamp FROM answers').fetchall()

    def _insert_into_answers(self, values: List[Dict[str, Any]]):
        with sqlite3.connect(self.db_path) as db:
            with db:
                db.executemany('INSERT INTO answers '
                               'VALUES (:update_id, :quiz_id, :question, :team_id, :answer, :timestamp)', values)

    def test_insert_message(self):
        message = Message(timestamp=1234567, update_id=1001,
                          chat_id=2001, text='Apple', insert_timestamp=123)
        self.quiz_db.insert_message(message)

        self.assertListEqual([
            (123, 1234567, 1001, 2001, 'Apple')
        ], _select_messages(self.db_path))

        message = Message(timestamp=1234568, update_id=1002,
                          chat_id=2002, text='Unicode Юнікод 😎', insert_timestamp=124)
        self.quiz_db.insert_message(message)

        self.assertListEqual([
            (123, 1234567, 1001, 2001, 'Apple'),
            (124, 1234568, 1002, 2002, 'Unicode Юнікод 😎')
        ], _select_messages(self.db_path))

    def test_insert_team(self):
        team = Team(quiz_id='test', id=5001,
                    name='Unicode Юнікод 😎', timestamp=123)
        self.quiz_db.insert_team(team)

        self.assertListEqual([
            (1, 'test', 5001, 'Unicode Юнікод 😎', 123),
        ], _select_teams(self.db_path))
        self.assertListEqual([(2,)], _select_update_id(self.db_path))

        team = Team(quiz_id='other', id=5002, name='Apple', timestamp=321)
        self.quiz_db.insert_team(team)

        self.assertListEqual([
            (1, 'test', 5001, 'Unicode Юнікод 😎', 123),
            (2, 'other', 5002, 'Apple', 321),
        ], _select_teams(self.db_path))
        self.assertListEqual([(3,)], _select_update_id(self.db_path))

    def test_get_teams_by_quiz_id(self):
        _insert_into_teams(self.db_path, _INITIAL_TEAMS)
        teams = self.quiz_db.get_teams(quiz_id='test')

        self.assertListEqual(sorted([
            Team(update_id=2, quiz_id='test', id=5001,
                 name='Unicode Юнікод 😎', timestamp=123),
            Team(update_id=4, quiz_id='test', id=5000,
                 name='Another team', timestamp=122),
        ]), sorted(teams))

    def test_get_teams_by_team_id(self):
        _insert_into_teams(self.db_path, _INITIAL_TEAMS)
        teams = self.quiz_db.get_teams(quiz_id='test', team_id=5001)
        self.assertListEqual([
            Team(update_id=2, quiz_id='test', id=5001,
                 name='Unicode Юнікод 😎', timestamp=123)
        ], teams)

        teams = self.quiz_db.get_teams(quiz_id='test', team_id=5000)
        self.assertListEqual([
            Team(update_id=4, quiz_id='test', id=5000,
                 name='Another team', timestamp=122)
        ], teams)

        teams = self.quiz_db.get_teams(quiz_id='test', team_id=111)
        self.assertListEqual([], teams)

    def test_get_teams_by_update_id(self):
        _insert_into_teams(self.db_path, _INITIAL_TEAMS)
        teams = self.quiz_db.get_teams(
            quiz_id='test', update_id_greater_than=2)

        self.assertListEqual(sorted([
            Team(update_id=4, quiz_id='test', id=5000,
                 name='Another team', timestamp=122),
        ]), sorted(teams))

        teams = self.quiz_db.get_teams(
            quiz_id='test', update_id_greater_than=3)

        self.assertListEqual(sorted([
            Team(update_id=4, quiz_id='test', id=5000,
                 name='Another team', timestamp=122),
        ]), sorted(teams))

        teams = self.quiz_db.get_teams(
            quiz_id='test', update_id_greater_than=4)
        self.assertListEqual(sorted([]), sorted(teams))

    def test_update_answer(self):
        _update_update_id(self.db_path, 100)
        update_id = self.quiz_db.update_answer(quiz_id='test', question=3, team_id=5001,
                                               answer='Unicode Юнікод 😎', answer_time=123)

        self.assertEqual(100, update_id)
        self.assertListEqual([
            (100, 'test', 3, 5001, 'Unicode Юнікод 😎', 123),
        ], self._select_answers())
        self.assertListEqual([(101,)], _select_update_id(self.db_path))

        update_id = self.quiz_db.update_answer(quiz_id='other', question=12, team_id=5002,
                                               answer='Apple', answer_time=321)

        self.assertEqual(101, update_id)
        self.assertListEqual([
            (100, 'test', 3, 5001, 'Unicode Юнікод 😎', 123),
            (101, 'other', 12, 5002, 'Apple', 321),
        ], self._select_answers())
        self.assertListEqual([(102,)], _select_update_id(self.db_path))

        update_id = self.quiz_db.update_answer(quiz_id='test', question=3, team_id=5001,
                                               answer='Banana', answer_time=124)

        self.assertEqual(102, update_id)
        self.assertListEqual([
            (102, 'test', 3, 5001, 'Banana', 124),
            (101, 'other', 12, 5002, 'Apple', 321),
        ], self._select_answers())
        self.assertListEqual([(103,)], _select_update_id(self.db_path))

        update_id = self.quiz_db.update_answer(quiz_id='test', question=3, team_id=5001,
                                               answer='Carrot', answer_time=123)

        self.assertEqual(0, update_id)
        self.assertListEqual([
            (102, 'test', 3, 5001, 'Banana', 124),
            (101, 'other', 12, 5002, 'Apple', 321),
        ], self._select_answers())
        self.assertListEqual([(103,)], _select_update_id(self.db_path))

    def test_get_answers(self):
        self._insert_into_answers([
            dict(update_id=2, quiz_id='test', question=5, team_id=5001,
                 answer='Apple', timestamp=123),
            dict(update_id=3, quiz_id='ignored', question=5, team_id=5001,
                 answer='Ignored', timestamp=321),
            dict(update_id=3, quiz_id='test', question=9, team_id=5002,
                 answer='Unicode Юнікод 😎', timestamp=34),
        ])
        answers = self.quiz_db.get_answers('test')

        self.assertListEqual(sorted([
            Answer(quiz_id='test', question=9, team_id=5002,
                   answer='Unicode Юнікод 😎', timestamp=34),
            Answer(quiz_id='test', question=5, team_id=5001,
                   answer='Apple', timestamp=123),
        ]), sorted(answers))

        answers = self.quiz_db.get_answers('test', update_id_greater_than=2)
        self.assertListEqual(sorted([
            Answer(quiz_id='test', question=9, team_id=5002,
                   answer='Unicode Юнікод 😎', timestamp=34),
        ]), sorted(answers))


if __name__ == '__main__':
    unittest.main()
