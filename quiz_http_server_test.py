import logging
import os
from quizzes_db import QuizzesDb
from quiz_http_server import QuizHttpServer
from telegram_quiz import TelegramQuiz
import tempfile
import threading
import requests
import telegram
import unittest


class TestQuizHttpServer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'quizzes.db')
        self.quizzes_db = QuizzesDb(db_path=self.db_path)
        self.logger = logging.Logger('test')
        self.logger.addHandler(logging.NullHandler())
        self.updater = telegram.ext.Updater(
            token='123:TOKEN', use_context=True)
        self.quiz = TelegramQuiz(id='test', updater=self.updater, question_set={'q1', 'q2'},
                                 quizzes_db=self.quizzes_db, handler_group=1, logger=self.logger)
        self.server = QuizHttpServer(
            host='localhost', port=0, quiz=self.quiz, logger=self.logger)
        self.url = f'http://localhost:{self.server.server_port}/'
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5.0)
        self.server.server_close()
        self.test_dir.cleanup()

    def test_invalid_json(self):
        response = requests.post(self.url, data='#$%')
        self.assertEqual(400, response.status_code)
        self.assertDictEqual({
            'ok': False,
            'error': 'Request is not a valid JSON object.'
        }, response.json())

    def test_internal_error(self):
        self.quiz.start_registration = None
        response = requests.post(
            self.url, json={'command': 'start_registration'})
        self.assertEqual(501, response.status_code)
        self.assertDictEqual({
            'ok': False,
            'error': 'Internal server error'
        }, response.json())

    def test_start_registration(self):
        response = requests.post(
            self.url, json={'command': 'start_registration'})
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({
            'ok': True,
        }, response.json())
        self.assertTrue(self.quiz.is_registration())

    def test_stop_registration(self):
        self.quiz.start_registration()
        response = requests.post(
            self.url, json={'command': 'stop_registration'})
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({
            'ok': True,
        }, response.json())
        self.assertFalse(self.quiz.is_registration())

    def test_start_question(self):
        response = requests.post(self.url, json={
            'command': 'start_question',
            'question_id': 'q1',
        })
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({
            'ok': True,
        }, response.json())
        self.assertEqual('q1', self.quiz.question_id)

    def test_start_wrong_question(self):
        response = requests.post(self.url, json={
            'command': 'start_question',
            'question_id': 'unexisting',
        })
        self.assertEqual(400, response.status_code)
        self.assertDictContainsSubset({
            'ok': False,
        }, response.json())
        self.assertIsNone(self.quiz.question_id)

    def test_stop_question(self):
        self.quiz.start_question('q1')
        response = requests.post(self.url, json={
            'command': 'stop_question',
        })
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({
            'ok': True,
        }, response.json())
        self.assertIsNone(self.quiz.question_id)

    def test_get_status(self):
        self.quiz.question_id = 'q2'
        self.quiz.teams = {
            1: 'Barcelona',
            2: 'Real Madrid',
            3: 'Liverpool',
        }
        self.quiz.answers = {
            'q1': {
                3: 'Apple',
                4: 'Юнікод',
            },
            'q2': {
                5: 'Mars',
                6: 'Jupiter',
            }
        }
        response = requests.post(self.url, json={
            'command': 'get_status',
        })
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({
            'ok': True,
            'quiz_id': 'test',
            'is_registration': False,
            'question_id': 'q2',
            'question_set': ['q1', 'q2'],
            'teams': {'1': 'Barcelona', '2': 'Real Madrid', '3': 'Liverpool'},
            'answers': {
                'q1': {
                    '3': 'Apple',
                    '4': 'Юнікод',
                },
                'q2': {
                    '5': 'Mars',
                    '6': 'Jupiter',
                }
            },
        }, response.json())


if __name__ == '__main__':
    unittest.main()
