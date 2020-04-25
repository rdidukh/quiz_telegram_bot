from quiz_db import Answer, Message, QuizDb, Team
import tempfile
from typing import Any, Dict, List
import unittest
from unittest.mock import MagicMock
import os
import sqlite3


_INITIAL_TEAMS = [
    dict(update_id=2, quiz_id='test', id=5001,
         name='Unicode Юнікод 😎', timestamp=123),
    dict(update_id=3, quiz_id='ignored',
         id=5001, name='Ignored', timestamp=124),
    dict(update_id=4, quiz_id='test', id=5000,
         name='Another team', timestamp=122),
]


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'messages.db')
        self.quiz_db = QuizDb(db_path=self.db_path)

    def tearDown(self):
        self.test_dir.cleanup()

    def _select_answers(self):
        with sqlite3.connect(self.db_path) as db:
            return db.execute(
                'SELECT update_id, quiz_id, question, team_id, answer, timestamp, points FROM answers').fetchall()

    def _insert_into_answers(self, values: List[Dict[str, Any]]):
        with sqlite3.connect(self.db_path) as db:
            with db:
                db.executemany('INSERT INTO answers '
                               'VALUES (:update_id, :quiz_id, :question, :team_id, :answer, :timestamp, :points)', values)

    def _select_teams(self):
        with sqlite3.connect(self.db_path) as db:
            return db.execute('SELECT update_id, quiz_id, id, name, timestamp FROM teams').fetchall()

    def _insert_into_teams(self, values: List[Dict[str, Any]]):
        with sqlite3.connect(self.db_path) as db:
            with db:
                db.executemany('INSERT INTO teams '
                               'VALUES (:update_id, :quiz_id, :id, :name, :timestamp)', values)

    def _select_messages(self):
        with sqlite3.connect(self.db_path) as db:
            return db.execute('SELECT insert_timestamp, timestamp, update_id, chat_id, text FROM messages').fetchall()

    def _get_last_answers_update_id(self):
        with sqlite3.connect(self.db_path) as db:
            return db.execute('SELECT MAX(update_id) FROM answers').fetchone()[0] or 0

    def _get_last_teams_update_id(self):
        with sqlite3.connect(self.db_path) as db:
            return db.execute('SELECT MAX(update_id) FROM teams').fetchone()[0] or 0


class QuizDbTest(BaseTestCase):
    def test_insert_message(self):
        message = Message(timestamp=1234567, update_id=1001,
                          chat_id=2001, text='Apple', insert_timestamp=123)
        self.quiz_db.insert_message(message)

        self.assertListEqual([
            (123, 1234567, 1001, 2001, 'Apple')
        ], self._select_messages())

        message = Message(timestamp=1234568, update_id=1002,
                          chat_id=2002, text='Unicode Юнікод 😎', insert_timestamp=124)
        self.quiz_db.insert_message(message)

        self.assertListEqual([
            (123, 1234567, 1001, 2001, 'Apple'),
            (124, 1234568, 1002, 2002, 'Unicode Юнікод 😎')
        ], self._select_messages())

    def test_get_teams_by_quiz_id(self):
        self._insert_into_teams(_INITIAL_TEAMS)
        teams = self.quiz_db.get_teams(quiz_id='test')

        self.assertListEqual(sorted([
            Team(update_id=2, quiz_id='test', id=5001,
                 name='Unicode Юнікод 😎', timestamp=123),
            Team(update_id=4, quiz_id='test', id=5000,
                 name='Another team', timestamp=122),
        ]), sorted(teams))

    def test_get_teams_by_team_id(self):
        self._insert_into_teams(_INITIAL_TEAMS)
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
        self._insert_into_teams(_INITIAL_TEAMS)
        teams = self.quiz_db.get_teams(
            quiz_id='test', min_update_id=3)

        self.assertListEqual(sorted([
            Team(update_id=4, quiz_id='test', id=5000,
                 name='Another team', timestamp=122),
        ]), sorted(teams))

        teams = self.quiz_db.get_teams(
            quiz_id='test', min_update_id=4)

        self.assertListEqual(sorted([
            Team(update_id=4, quiz_id='test', id=5000,
                 name='Another team', timestamp=122),
        ]), sorted(teams))

        teams = self.quiz_db.get_teams(
            quiz_id='test', min_update_id=5)
        self.assertListEqual(sorted([]), sorted(teams))


class GetAnswersSanityTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._insert_into_answers([
            dict(update_id=2, quiz_id='test', question=5, team_id=5001,
                 answer='Apple', timestamp=123, points=4),
            dict(update_id=3, quiz_id='ignored', question=5, team_id=5001,
                 answer='Ignored', timestamp=321, points=1),
            dict(update_id=4, quiz_id='test', question=9, team_id=5002,
                 answer='Unicode Юнікод 😎', timestamp=34, points=None),
        ])

    def test_gets_answers(self):
        answers = self.quiz_db.get_answers('test')

        self.assertListEqual(sorted([
            Answer(quiz_id='test', question=9, team_id=5002,
                   answer='Unicode Юнікод 😎', timestamp=34, points=None),
            Answer(quiz_id='test', question=5, team_id=5001,
                   answer='Apple', timestamp=123, points=4),
        ]), sorted(answers))

    def test_min_update_id(self):
        answers = self.quiz_db.get_answers('test', min_update_id=3)

        self.assertListEqual(sorted([
            Answer(quiz_id='test', question=9, team_id=5002,
                   answer='Unicode Юнікод 😎', timestamp=34),
        ]), sorted(answers))

    def test_team_id(self):
        answers = self.quiz_db.get_answers('test', team_id=5001)

        self.assertListEqual(sorted([
            Answer(update_id=2, quiz_id='test', question=5, team_id=5001,
                   answer='Apple', timestamp=123, points=4),
        ]), sorted(answers))


class GetAnswersManyItemsTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        update_id = 0
        answers: List[Answer] = []
        for quiz_id in range(1, 11):
            for team_id in range(1, 51):
                for question in range(1, 31):
                    update_id += 1
                    answers.append(dict(update_id=update_id, quiz_id=f'quiz{quiz_id}', question=question,
                                        team_id=5000+team_id, answer=f'Answer {quiz_id}', timestamp=1000+update_id,
                                        points=question % 2))
        self._insert_into_answers(answers)

    def test_all_answers(self):
        answers = self.quiz_db.get_answers(quiz_id='quiz5')
        self.assertEqual(1500, len(answers))
        self.assertEqual(
            1500, len([a for a in answers if a.quiz_id == 'quiz5']))
        self.assertEqual(30, len([a for a in answers if a.team_id == 5010]))
        self.assertEqual(50, len([a for a in answers if a.question == 7]))
        self.assertEqual(750, len([a for a in answers if a.points == 1]))

    def test_team_id(self):
        answers = self.quiz_db.get_answers(quiz_id='quiz9', team_id=5024)
        self.assertEqual(30, len(answers))
        self.assertEqual(
            30, len([a for a in answers if a.quiz_id == 'quiz9']))
        self.assertEqual(30, len([a for a in answers if a.team_id == 5024]))
        self.assertEqual(1, len([a for a in answers if a.question == 7]))
        self.assertEqual(15, len([a for a in answers if a.points == 1]))

    def test_min_update_id(self):
        answers = self.quiz_db.get_answers(quiz_id='quiz3', min_update_id=3751)
        self.assertEqual(750, len(answers))
        self.assertEqual(
            750, len([a for a in answers if a.quiz_id == 'quiz3']))
        self.assertEqual(0, len([a for a in answers if a.team_id == 5025]))
        self.assertEqual(30, len([a for a in answers if a.team_id == 5026]))
        self.assertEqual(25, len([a for a in answers if a.question == 7]))
        self.assertEqual(375, len([a for a in answers if a.points == 1]))


class UpdateAnswerTest(BaseTestCase):
    def test_inserts_new_answer(self):
        sub = MagicMock()
        self.quiz_db.add_updates_subscriber(sub)

        update_id = self.quiz_db.update_answer(quiz_id='test', question=3, team_id=5001,
                                               answer='Unicode Юнікод 😎', answer_time=123)

        self.assertEqual(1, update_id)
        self.assertListEqual([
            (1, 'test', 3, 5001, 'Unicode Юнікод 😎', 123, None),
        ], self._select_answers())
        self.assertEqual(1, self._get_last_answers_update_id())
        sub.assert_called_with()

    def test_updates_old_answer_and_resets_points(self):
        sub = MagicMock()
        self.quiz_db.add_updates_subscriber(sub)

        self._insert_into_answers([dict(update_id=2, quiz_id='test', question=5, team_id=5001,
                                        answer='Apple', timestamp=123, points=4)])
        update_id = self.quiz_db.update_answer(quiz_id='test', question=5, team_id=5001,
                                               answer='Unicode Юнікод 😎', answer_time=124)

        self.assertEqual(3, update_id)
        self.assertListEqual([
            (3, 'test', 5, 5001, 'Unicode Юнікод 😎', 124, None),
        ], self._select_answers())
        self.assertEqual(3, self._get_last_answers_update_id())
        sub.assert_called_with()

    def test_outdated_answer(self):
        sub = MagicMock()
        self.quiz_db.add_updates_subscriber(sub)
        self._insert_into_answers([dict(update_id=2, quiz_id='test', question=5, team_id=5001,
                                        answer='Apple', timestamp=123, points=4)])

        update_id = self.quiz_db.update_answer(quiz_id='test', question=5, team_id=5001,
                                               answer='Unicode Юнікод 😎', answer_time=122)

        self.assertEqual(0, update_id)
        self.assertListEqual([
            (2, 'test', 5, 5001, 'Apple', 123, 4),
        ], self._select_answers())
        self.assertEqual(2, self._get_last_answers_update_id())
        sub.assert_not_called()


class UpdateAnswerPointsTest(BaseTestCase):

    def test_updates_points(self):
        sub = MagicMock()
        self.quiz_db.add_updates_subscriber(sub)
        self._insert_into_answers([
            dict(update_id=1, quiz_id='test', question=5, team_id=5001,
                 answer='Apple', timestamp=123, points=9),
            dict(update_id=2, quiz_id='test', question=4, team_id=5002,
                 answer='Banana', timestamp=124, points=9),
            dict(update_id=3, quiz_id='other', question=4, team_id=5001,
                 answer='Carrot', timestamp=125, points=9),
        ])

        update_id = self.quiz_db.set_answer_points(
            quiz_id='test', question=5, team_id=5001, points=7)

        self.assertEqual(4, update_id)
        self.assertListEqual([
            (2, 'test', 4, 5002, 'Banana', 124, 9),
            (3, 'other', 4, 5001, 'Carrot', 125, 9),
            (4, 'test', 5, 5001, 'Apple', 123, 7),
        ], self._select_answers())
        sub.assert_called_with()

    def test_non_existing_answer(self):
        sub = MagicMock()
        self.quiz_db.add_updates_subscriber(sub)
        self._insert_into_answers([
            dict(update_id=1, quiz_id='test', question=5, team_id=5001,
                 answer='Apple', timestamp=123, points=9),
            dict(update_id=2, quiz_id='test', question=4, team_id=5002,
                 answer='Banana', timestamp=124, points=9),
            dict(update_id=3, quiz_id='other', question=4, team_id=5001,
                 answer='Carrot', timestamp=125, points=9),
        ])
        update_id = self.quiz_db.set_answer_points(
            quiz_id='test', question=4, team_id=5001, points=7)

        self.assertEqual(4, update_id)
        self.assertListEqual([
            (1, 'test', 5, 5001, 'Apple', 123, 9),
            (2, 'test', 4, 5002, 'Banana', 124, 9),
            (3, 'other', 4, 5001, 'Carrot', 125, 9),
            (4, 'test', 4, 5001, '', 0, 7),
        ], self._select_answers())
        sub.assert_called_with()


class UpdateTeamTest(BaseTestCase):
    def test_inserts_new_team(self):
        sub = MagicMock()
        self.quiz_db.add_updates_subscriber(sub)
        prev_update_id = self._get_last_teams_update_id()

        update_id = self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Unicode Юнікод 😎', registration_time=123)

        self.assertEqual(prev_update_id+1, update_id)
        self.assertListEqual([
            (update_id, 'test', 5001, 'Unicode Юнікод 😎', 123),
        ], self._select_teams())
        self.assertEqual(update_id, self._get_last_teams_update_id())
        sub.assert_called_with()

    def test_updates_team(self):
        sub = MagicMock()
        self.quiz_db.add_updates_subscriber(sub)
        self._insert_into_teams([
            dict(update_id=1, quiz_id='test',
                 id=5001, name='Apple', timestamp=12)
        ])
        prev_update_id = self._get_last_teams_update_id()

        update_id = self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Banana', registration_time=13)

        self.assertEqual(prev_update_id+1, update_id)
        self.assertListEqual([
            (update_id, 'test', 5001, 'Banana', 13),
        ], self._select_teams())
        sub.assert_called_with()

    def test_outdated_registration(self):
        sub = MagicMock()
        self.quiz_db.add_updates_subscriber(sub)
        self._insert_into_teams([
            dict(update_id=1, quiz_id='test',
                 id=5001, name='Apple', timestamp=12)
        ])
        prev_update_id = self._get_last_teams_update_id()

        update_id = self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Banana', registration_time=11)

        self.assertEqual(0, update_id)
        self.assertListEqual([
            (1, 'test', 5001, 'Apple', 12),
        ], self._select_teams())
        self.assertEqual(prev_update_id, self._get_last_teams_update_id())
        sub.assert_not_called()


if __name__ == '__main__':
    unittest.main()
