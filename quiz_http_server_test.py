import logging
import os
from quizzes_db import QuizzesDb
from quiz_http_server import QuizHttpServer
from telegram_quiz import TelegramQuiz
from telegram_quiz_test import STRINGS
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
        self.strings_file = os.path.join(self.test_dir.name, 'strings.json')
        with open(self.strings_file, 'w') as file:
            file.write(STRINGS)
        self.quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', number_of_questions=2,
                                 language='lang', strings_file=self.strings_file, quizzes_db=self.quizzes_db,
                                 logger=self.logger)
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
            'question_id': '01',
        })
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({
            'ok': True,
        }, response.json())
        self.assertEqual('01', self.quiz.question_id)

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
        self.quiz.start_question('01')
        response = requests.post(self.url, json={
            'command': 'stop_question',
        })
        self.assertEqual(200, response.status_code)
        self.assertDictEqual({
            'ok': True,
        }, response.json())
        self.assertIsNone(self.quiz.question_id)

    def test_get_status(self):
        self.quiz.question_id = '02'
        self.quiz.teams = {
            1: 'Barcelona',
            2: 'Real Madrid',
            3: 'Liverpool',
        }
        self.quiz.answers = {
            '01': {
                3: 'Apple',
                4: 'Юнікод',
            },
            '02': {
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
            'question_id': '02',
            'number_of_questions': 2,
            'question_set': ['01', '02'],
            'teams': {'1': 'Barcelona', '2': 'Real Madrid', '3': 'Liverpool'},
            'answers': {
                '01': {
                    '3': 'Apple',
                    '4': 'Юнікод',
                },
                '02': {
                    '5': 'Mars',
                    '6': 'Jupiter',
                }
            },
        }, response.json())


if __name__ == '__main__':
    unittest.main()
