import json
import os
from quiz_db import Answer, Team, QuizDb
from quiz_http_server import create_quiz_tornado_app
from telegram_quiz import QuizStatus, Updates, TelegramQuiz
from telegram_quiz_test import STRINGS
import tempfile
import tornado.testing
import telegram
from typing import Any, Dict
import unittest
from unittest.mock import MagicMock


def _remove_key(d: Dict, key) -> Dict:
    d.pop(key)
    return d


def _json_to_updates(obj: Dict[str, Any]) -> Updates:
    status = QuizStatus(**obj.get('status'))
    teams = [Team(**t) for t in obj['teams']]
    answers = [Answer(**a) for a in obj['answers']]
    return Updates(status=status, teams=teams, answers=answers)


class BaseTestCase(tornado.testing.AsyncHTTPTestCase):
    def get_app(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'quiz.db')
        self.quiz_db = QuizDb(db_path=self.db_path)
        self.updater = telegram.ext.Updater(
            token='123:TOKEN', use_context=True)
        self.strings_file = os.path.join(self.test_dir.name, 'strings.json')
        with open(self.strings_file, 'w') as file:
            file.write(STRINGS)
        self.quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', language='lang',
                                 strings_file=self.strings_file, quiz_db=self.quiz_db)
        return create_quiz_tornado_app(quiz=self.quiz)

    def tearDown(self):
        self.test_dir.cleanup()
        super().tearDown()


class TestQuizHttpServer(BaseTestCase):
    def test_root(self):
        response = self.fetch('/')
        self.assertEqual(200, response.code)

    def test_index_html(self):
        response = self.fetch('/index.html')
        self.assertEqual(200, response.code)

    def test_index_js(self):
        response = self.fetch('/index.js')
        self.assertEqual(200, response.code)

    def test_invalid_json(self):
        response = self.fetch('/api/getUpdates', method='POST', body='#$%')
        self.assertEqual(400, response.code)
        self.assertDictEqual({
            'error': 'Request is not a valid JSON object.'
        }, json.loads(response.body))

    def test_internal_error(self):
        self.quiz.start_registration = None
        response = self.fetch('/api/startRegistration', method='POST', body='')
        self.assertEqual(501, response.code)
        self.assertDictEqual({
            'error': 'Internal server error'
        }, json.loads(response.body))

    def test_start_registration(self):
        response = self.fetch('/api/startRegistration', method='POST', body='')
        self.assertEqual(200, response.code)
        self.assertDictEqual({}, json.loads(response.body))
        self.assertTrue(self.quiz.is_registration())

        response = self.fetch('/api/startRegistration', method='POST', body='')
        self.assertEqual(400, response.code)
        self.assertIn('error', json.loads(response.body))
        self.assertTrue(self.quiz.is_registration())

    def test_stop_registration(self):
        self.quiz.start_registration()
        response = self.fetch('/api/stopRegistration', method='POST', body='')
        self.assertEqual(200, response.code)
        self.assertDictEqual({}, json.loads(response.body))
        self.assertFalse(self.quiz.is_registration())

    def test_start_question(self):
        request = {'question': 1}
        response = self.fetch('/api/startQuestion',
                              method='POST', body=json.dumps(request))
        self.assertEqual(200, response.code)
        self.assertDictEqual({}, json.loads(response.body))
        self.assertEqual(1, self.quiz.question)

    def test_start_wrong_question(self):
        request = {'question': 'unexisting'}
        response = self.fetch('/api/startQuestion',
                              method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertListEqual(['error'],
                             list(json.loads(response.body).keys()))
        self.assertIsNone(self.quiz.question)

    def test_stop_question(self):
        self.quiz.start_question(1)
        response = self.fetch('/api/stopQuestion', method='POST', body='')
        self.assertEqual(200, response.code)
        self.assertDictEqual({}, json.loads(response.body))
        self.assertIsNone(self.quiz.question)


class GetUpdatesApiTest(BaseTestCase):
    def test_returns_updates(self):
        update_id = self.quiz.status_update_id
        self.quiz.get_status = MagicMock(return_value=QuizStatus(
            update_id=101,
            quiz_id='test',
            language='lang',
            question=None,
            registration=False,
            time='2020-02-03 04:05:06',
        ))
        self.quiz.quiz_db.get_answers = MagicMock(return_value=[
            Answer(quiz_id='test', question=5, team_id=5001,
                   answer='Apple', timestamp=1234, update_id=201, points=3),
            Answer(quiz_id='test', question=8, team_id=5002,
                   answer='Unicode Юнікод', timestamp=1236, update_id=202, points=None),
        ])
        self.quiz.quiz_db.get_teams = MagicMock(return_value=[
            Team(quiz_id='test', id=5001, name='Liverpool',
                 timestamp=1235, update_id=301),
            Team(quiz_id='test', id=5002, name='Tottenham',
                 timestamp=1237, update_id=302),
        ])
        request = {
            'min_status_update_id': update_id,
            'min_teams_update_id': 456,
            'min_answers_update_id': 789,
        }
        response = self.fetch('/api/getUpdates', method='POST',
                              body=json.dumps(request))
        self.assertEqual(200, response.code)
        self.assertDictEqual({
            'status': {
                'update_id': 101,
                'quiz_id': 'test',
                'language': 'lang',
                'question': None,
                'registration': False,
                'time': '2020-02-03 04:05:06'
            },
            'teams': [
                dict(quiz_id='test', id=5001, name='Liverpool',
                     timestamp=1235, update_id=301),
                dict(quiz_id='test', id=5002, name='Tottenham',
                     timestamp=1237, update_id=302),
            ],
            'answers': [
                dict(quiz_id='test', question=5, team_id=5001,
                     answer='Apple', timestamp=1234, update_id=201, points=3),
                dict(quiz_id='test', question=8, team_id=5002,
                     answer='Unicode Юнікод', timestamp=1236, update_id=202, points=None),
            ],
        }, json.loads(response.body))
        self.quiz.get_status.assert_called_once()
        self.quiz.quiz_db.get_teams.assert_called_with(
            quiz_id='test', min_update_id=456)
        self.quiz.quiz_db.get_answers.assert_called_with(
            quiz_id='test', min_update_id=789)

    def test_ignores_status(self):
        update_id = self.quiz.status_update_id
        self.quiz.get_status = MagicMock()
        self.quiz.quiz_db.get_answers = MagicMock(return_value=[])
        self.quiz.quiz_db.get_teams = MagicMock(return_value=[])
        request = {
            'min_status_update_id': update_id+1,
            'min_teams_update_id': 456,
            'min_answers_update_id': 789,
        }
        response = self.fetch('/api/getUpdates', method='POST',
                              body=json.dumps(request))
        self.assertEqual(200, response.code)
        self.assertDictEqual({
            'status': None,
            'teams': [],
            'answers': [],
        }, json.loads(response.body))
        self.quiz.get_status.assert_not_called()
        self.quiz.quiz_db.get_teams.assert_called_with(
            quiz_id='test', min_update_id=456)
        self.quiz.quiz_db.get_answers.assert_called_with(
            quiz_id='test', min_update_id=789)

    def test_no_min_status_update_id_given(self):
        request = {
            'min_teams_update_id': 456,
            'min_answers_update_id': 789,
        }
        response = self.fetch(
            '/api/getUpdates', method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertIn('error', json.loads(response.body))

    def test_no_min_teams_update_id_given(self):
        request = {
            'min_status_update_id': 123,
            'min_answers_update_id': 789,
        }
        response = self.fetch(
            '/api/getUpdates', method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertIn('error', json.loads(response.body))

    def test_no_min_answers_update_id_given(self):
        request = {
            'min_status_update_id': 123,
            'min_teams_update_id': 456,
        }
        response = self.fetch(
            '/api/getUpdates', method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertIn('error', json.loads(response.body))

###

    def test_no_min_status_update_id_not_int(self):
        request = {
            'min_status_update_id': '123',
            'min_teams_update_id': 456,
            'min_answers_update_id': 789,
        }
        response = self.fetch(
            '/api/getUpdates', method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertIn('error', json.loads(response.body))

    def test_no_min_teams_update_id_not_int(self):
        request = {
            'min_status_update_id': 123,
            'min_teams_update_id': '456',
            'min_answers_update_id': 789,
        }
        response = self.fetch(
            '/api/getUpdates', method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertIn('error', json.loads(response.body))

    def test_no_min_answers_update_id_not_int(self):
        request = {
            'min_status_update_id': 123,
            'min_teams_update_id': 456,
            'min_answers_update_id': '789',
        }
        response = self.fetch(
            '/api/getUpdates', method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertIn('error', json.loads(response.body))


if __name__ == '__main__':
    unittest.main()
