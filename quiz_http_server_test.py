import json
import os
from quiz_db import Answer, Team, QuizDb
from quiz_http_server import create_quiz_tornado_app
from telegram_quiz import QuizStatus, Updates, TelegramQuiz
from telegram_quiz_test import STRINGS
import telegram
import tempfile
import threading
import time
import tornado.testing
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
        self.quiz = TelegramQuiz(strings_file=self.strings_file, quiz_db=self.quiz_db)
        return create_quiz_tornado_app(quiz=self.quiz)

    def tearDown(self):
        self.test_dir.cleanup()
        super().tearDown()


class StartedQuizBaseTestCase(BaseTestCase):
    def _updater_factory(self, bot_api_token: str) -> telegram.ext.Updater:
        updater = telegram.ext.Updater(bot_api_token, use_context=True)
        updater.start_polling = MagicMock()
        return updater

    def get_app(self):
        app = super().get_app()
        self.quiz.start(quiz_id='test', bot_api_token='123:TOKEN', language='lang',
                        updater_factory=self._updater_factory)
        return app


class TestQuizHttpServer(StartedQuizBaseTestCase):
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
        self.assertEqual(1, self.quiz._question)

    def test_start_wrong_question(self):
        request = {'question': 'unexisting'}
        response = self.fetch('/api/startQuestion',
                              method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertListEqual(['error'],
                             list(json.loads(response.body).keys()))
        self.assertIsNone(self.quiz._question)

    def test_stop_question(self):
        self.quiz.start_question(1)
        response = self.fetch('/api/stopQuestion', method='POST', body='')
        self.assertEqual(200, response.code)
        self.assertDictEqual({}, json.loads(response.body))
        self.assertIsNone(self.quiz._question)


class StartQuizApiTest(BaseTestCase):
    def test_starts_quiz(self):
        self.quiz.start = MagicMock()
        request = {
            'quiz_id': 'test',
            'bot_api_token': '123:TOKEN',
            'language': 'lang',
        }
        response = self.fetch('/api/startQuiz', method='POST',
                              body=json.dumps(request))
        self.assertDictEqual({}, json.loads(response.body))
        self.assertEqual(200, response.code)
        self.quiz.start.assert_called_with(
            quiz_id='test', bot_api_token='123:TOKEN', language='lang')

    def test_quiz_id_param(self):
        request = {
            'bot_api_token': '123:TOKEN',
            'language': 'lang',
        }
        response = self.fetch('/api/startQuiz', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)

    def test_no_bot_api_token_param(self):
        request = {
            'quiz_id': 'test',
            'language': 'lang',
        }
        response = self.fetch('/api/startQuiz', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)

    def test_no_language_param(self):
        request = {
            'quiz_id': 'test',
            'bot_api_token': '123:TOKEN',
        }
        response = self.fetch('/api/startQuiz', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)

    def test_stops_quiz(self):
        self.quiz.stop = MagicMock()
        request = {}
        response = self.fetch('/api/stopQuiz', method='POST',
                              body=json.dumps(request))
        self.assertDictEqual({}, json.loads(response.body))
        self.assertEqual(200, response.code)
        self.quiz.stop.assert_called_with()


class SetAnswerPointsApiTest(StartedQuizBaseTestCase):
    def test_updates_points(self):
        self.quiz_db.set_answer_points = MagicMock(return_value=4)
        request = {
            'question': 4,
            'team_id': 5001,
            'points': 17,
        }
        response = self.fetch('/api/setAnswerPoints', method='POST',
                              body=json.dumps(request))
        self.assertDictEqual({}, json.loads(response.body))
        self.assertEqual(200, response.code)
        self.quiz_db.set_answer_points.assert_called_with(
            quiz_id='test', question=4, team_id=5001, points=17)

    def test_non_existing_answer(self):
        self.quiz_db.set_answer_points = MagicMock(return_value=0)
        request = {
            'question': 4,
            'team_id': 5001,
            'points': 17,
        }
        response = self.fetch('/api/setAnswerPoints', method='POST',
                              body=json.dumps(request))
        self.assertIn('does not exist', json.loads(response.body)['error'])
        self.assertEqual(400, response.code)
        self.quiz_db.set_answer_points.assert_called_with(
            quiz_id='test', question=4, team_id=5001, points=17)

    def test_no_question_param(self):
        request = {
            'team_id': 5001,
            'points': 17,
        }
        response = self.fetch('/api/setAnswerPoints', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)

    def test_no_team_id_param(self):
        request = {
            'question': 4,
            'points': 17,
        }
        response = self.fetch('/api/setAnswerPoints', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)

    def test_no_points_param(self):
        request = {
            'question': 4,
            'team_id': 5001,
        }
        response = self.fetch('/api/setAnswerPoints', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)

    def test_question_param_not_int(self):
        request = {
            'question': '4',
            'team_id': 5001,
            'points': 17,
        }
        response = self.fetch('/api/setAnswerPoints', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)

    def test_team_id_param_not_int(self):
        request = {
            'question': 4,
            'team_id': '5001',
            'points': 17,
        }
        response = self.fetch('/api/setAnswerPoints', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)

    def test_points_param_not_int(self):
        request = {
            'question': 4,
            'team_id': 5001,
            'points': '17',
        }
        response = self.fetch('/api/setAnswerPoints', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)


class GetUpdatesApiTest(StartedQuizBaseTestCase):
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
        self.quiz._quiz_db.get_answers = MagicMock(return_value=[
            Answer(quiz_id='test', question=5, team_id=5001,
                   answer='Apple', timestamp=1234, update_id=201, points=3),
            Answer(quiz_id='test', question=8, team_id=5002,
                   answer='Unicode Юнікод', timestamp=1236, update_id=202, points=None),
        ])
        self.quiz._quiz_db.get_teams = MagicMock(return_value=[
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
        self.quiz._quiz_db.get_teams.assert_called_with(
            quiz_id='test', min_update_id=456)
        self.quiz._quiz_db.get_answers.assert_called_with(
            quiz_id='test', min_update_id=789)

    def test_ignores_status(self):
        update_id = self.quiz.status_update_id
        self.quiz.get_status = MagicMock()
        self.quiz._quiz_db.get_answers = MagicMock(return_value=[])
        self.quiz._quiz_db.get_teams = MagicMock(return_value=[])
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
        self.quiz._quiz_db.get_teams.assert_called_with(
            quiz_id='test', min_update_id=456)
        self.quiz._quiz_db.get_answers.assert_called_with(
            quiz_id='test', min_update_id=789)

    def test_long_polling_status_change(self):
        request = {
            'min_status_update_id': 1,
            'min_teams_update_id': 1,
            'min_answers_update_id': 1,
            'timeout': 3,
        }

        def _change_status():
            time.sleep(0.5)
            self.quiz.start_registration()

        start_time = time.time()

        thread = threading.Thread(target=_change_status)
        thread.start()

        response = self.fetch('/api/getUpdates', method='POST',
                              body=json.dumps(request))

        thread.join()

        self.assertGreater(time.time(), start_time+0.5)
        self.assertLess(time.time(), start_time + 3.0)
        self.assertIsNotNone(json.loads(response.body)['status'])
        self.assertEqual(200, response.code)
        self.assertSetEqual(set(), self.quiz_db._subscribers)

    def test_long_polling_db_change(self):
        request = {
            'min_status_update_id': self.quiz.status_update_id + 1,
            'min_teams_update_id': 1,
            'min_answers_update_id': 1,
            'timeout': 3,
        }

        def _change_status():
            time.sleep(0.5)
            self.quiz_db.update_team(
                quiz_id='test', team_id=5001, name='Liverpool', registration_time=123)

        start_time = time.time()

        thread = threading.Thread(target=_change_status)
        thread.start()

        response = self.fetch('/api/getUpdates', method='POST',
                              body=json.dumps(request))

        thread.join()

        self.assertGreater(time.time(), start_time+0.5)
        self.assertLess(time.time(), start_time + 3.0)
        self.assertDictEqual({
            'status': None,
            'teams': [{
                'quiz_id': 'test',
                'update_id': 1,
                'id': 5001,
                'name': 'Liverpool',
                'timestamp': 123,
            }],
            'answers': [],
        }, json.loads(response.body))
        self.assertEqual(200, response.code)
        self.assertSetEqual(set(), self.quiz_db._subscribers)

    def test_long_polling_instant_status_update(self):
        request = {
            'min_status_update_id': 1,
            'min_teams_update_id': 1,
            'min_answers_update_id': 1,
            'timeout': 3.0,
        }

        self.quiz.start_registration()

        start_time = time.time()

        response = self.fetch('/api/getUpdates', method='POST',
                              body=json.dumps(request))

        self.assertLess(time.time(), start_time + 0.5)
        updates = json.loads(response.body)
        self.assertListEqual(
            ['status', 'teams', 'answers'], list(updates.keys()))
        self.assertEqual(True, updates['status']['registration'])
        self.assertListEqual([], updates['teams'])
        self.assertListEqual([], updates['answers'])
        self.assertEqual(200, response.code)
        self.assertSetEqual(set(), self.quiz_db._subscribers)

    def test_long_polling_instant_db_update(self):
        request = {
            'min_status_update_id': self.quiz.status_update_id + 1,
            'min_teams_update_id': 1,
            'min_answers_update_id': 1,
            'timeout': 3,
        }

        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=123)

        start_time = time.time()

        response = self.fetch('/api/getUpdates', method='POST',
                              body=json.dumps(request))

        self.assertLess(time.time(), start_time + 0.5)
        self.assertDictEqual({
            'status': None,
            'teams': [{
                'quiz_id': 'test',
                'update_id': 1,
                'id': 5001,
                'name': 'Liverpool',
                'timestamp': 123,
            }],
            'answers': [],
        }, json.loads(response.body))
        self.assertEqual(200, response.code)
        self.assertSetEqual(set(), self.quiz_db._subscribers)

    def test_long_polling_timeout(self):
        request = {
            'min_status_update_id': self.quiz.status_update_id + 2,
            'min_teams_update_id': 1,
            'min_answers_update_id': 1,
            'timeout': 0.5,
        }

        self.quiz.start_registration()

        start_time = time.time()
        response = self.fetch('/api/getUpdates', method='POST',
                              body=json.dumps(request))
        self.assertGreater(time.time(), start_time+0.5)
        self.assertDictEqual({
            'status': None,
            'teams': [],
            'answers': [],
        }, json.loads(response.body))
        self.assertEqual(200, response.code)
        self.assertSetEqual(set(), self.quiz_db._subscribers)

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

    def test_timeout_not_float_or_int(self):
        request = {
            'min_status_update_id': 123,
            'min_teams_update_id': 456,
            'min_answers_update_id': 789,
            'timeout': '0.5',
        }
        response = self.fetch(
            '/api/getUpdates', method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertIn('error', json.loads(response.body))


class SendResultsApiTest(StartedQuizBaseTestCase):
    def test_sends_results(self):
        self.quiz.send_results = MagicMock()
        request = {'team_id': 5001}
        response = self.fetch('/api/sendResults', method='POST',
                              body=json.dumps(request))
        self.assertDictEqual({}, json.loads(response.body))
        self.assertEqual(200, response.code)
        self.quiz.send_results.assert_called_with(team_id=5001)

    def test_no_team_id(self):
        self.quiz.send_results = MagicMock()
        request = {}
        response = self.fetch('/api/sendResults', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)
        self.quiz.send_results.assert_not_called()

    def test_team_id_not_int(self):
        self.quiz.send_results = MagicMock()
        request = {'team_id': '5001'}
        response = self.fetch('/api/sendResults', method='POST',
                              body=json.dumps(request))
        self.assertIn('error', json.loads(response.body))
        self.assertEqual(400, response.code)
        self.quiz.send_results.assert_not_called()


if __name__ == '__main__':
    unittest.main()
