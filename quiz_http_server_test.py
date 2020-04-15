import json
import logging
import os
from quiz_db import QuizDb
from quiz_http_server import create_quiz_tornado_app
from telegram_quiz import TelegramQuiz
from telegram_quiz_test import STRINGS
import tempfile
import tornado.testing
import telegram
import unittest


class TestQuizHttpServer(tornado.testing.AsyncHTTPTestCase):
    def get_app(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'quiz.db')
        self.quiz_db = QuizDb(db_path=self.db_path)
        self.logger = logging.Logger('test')
        self.logger.addHandler(logging.NullHandler())
        self.updater = telegram.ext.Updater(
            token='123:TOKEN', use_context=True)
        self.strings_file = os.path.join(self.test_dir.name, 'strings.json')
        with open(self.strings_file, 'w') as file:
            file.write(STRINGS)
        self.quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', number_of_questions=2,
                                 language='lang', strings_file=self.strings_file, quiz_db=self.quiz_db,
                                 logger=self.logger)
        return create_quiz_tornado_app(quiz=self.quiz)

    def tearDown(self):
        self.test_dir.cleanup()
        super().tearDown()

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
        response = self.fetch('/', method='POST', body='#$%')
        self.assertEqual(400, response.code)
        self.assertDictEqual({
            'ok': False,
            'error': 'Request is not a valid JSON object.'
        }, json.loads(response.body))

    def test_internal_error(self):
        self.quiz.start_registration = None
        request = {'command': 'start_registration'}
        response = self.fetch('/', method='POST', body=json.dumps(request))
        self.assertEqual(501, response.code)
        self.assertDictEqual({
            'ok': False,
            'error': 'Internal server error'
        }, json.loads(response.body))

    def test_start_registration(self):
        request = {'command': 'start_registration'}
        response = self.fetch('/', method='POST', body=json.dumps(request))
        self.assertEqual(200, response.code)
        self.assertDictEqual({
            'ok': True,
        }, json.loads(response.body))
        self.assertTrue(self.quiz.is_registration())

    def test_stop_registration(self):
        self.quiz.start_registration()
        request = {'command': 'stop_registration'}
        response = self.fetch('/', method='POST', body=json.dumps(request))
        self.assertEqual(200, response.code)
        self.assertDictEqual({
            'ok': True,
        }, json.loads(response.body))
        self.assertFalse(self.quiz.is_registration())

    def test_start_question(self):
        request = {
            'command': 'start_question',
            'question_id': '01',
        }
        response = self.fetch('/', method='POST', body=json.dumps(request))
        self.assertEqual(200, response.code)
        self.assertDictEqual({
            'ok': True,
        }, json.loads(response.body))
        self.assertEqual('01', self.quiz.question_id)

    def test_start_wrong_question(self):
        request = {
            'command': 'start_question',
            'question_id': 'unexisting',
        }
        response = self.fetch('/', method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertDictContainsSubset({
            'ok': False,
        }, json.loads(response.body))
        self.assertIsNone(self.quiz.question_id)

    def test_stop_question(self):
        self.quiz.start_question('01')
        request = {
            'command': 'stop_question',
        }
        response = self.fetch('/', method='POST', body=json.dumps(request))
        self.assertEqual(200, response.code)
        self.assertDictEqual({
            'ok': True,
        }, json.loads(response.body))
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
        request = {
            'command': 'get_status',
        }
        response = self.fetch('/', method='POST', body=json.dumps(request))
        self.assertEqual(200, response.code)
        self.assertDictEqual({
            'ok': True,
            'quiz_id': 'test',
            'is_registration': False,
            'question_id': '02',
            'number_of_questions': 2,
            'language': 'lang',
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
        }, json.loads(response.body))


if __name__ == '__main__':
    unittest.main()
