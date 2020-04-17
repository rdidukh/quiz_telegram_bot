import json
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
        self.updater = telegram.ext.Updater(
            token='123:TOKEN', use_context=True)
        self.strings_file = os.path.join(self.test_dir.name, 'strings.json')
        with open(self.strings_file, 'w') as file:
            file.write(STRINGS)
        self.quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', number_of_questions=2,
                                 language='lang', strings_file=self.strings_file, quiz_db=self.quiz_db)
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
        response = self.fetch('/api/getStatus', method='POST', body='#$%')
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
        request = {'question_id': '01'}
        response = self.fetch('/api/startQuestion',
                              method='POST', body=json.dumps(request))
        self.assertEqual(200, response.code)
        self.assertDictEqual({}, json.loads(response.body))
        self.assertEqual('01', self.quiz.question_id)

    def test_start_wrong_question(self):
        request = {'question_id': 'unexisting'}
        response = self.fetch('/api/startQuestion',
                              method='POST', body=json.dumps(request))
        self.assertEqual(400, response.code)
        self.assertListEqual(['error'],
                             list(json.loads(response.body).keys()))
        self.assertIsNone(self.quiz.question_id)

    def test_stop_question(self):
        self.quiz.start_question('01')
        response = self.fetch('/api/stopQuestion', method='POST', body='')
        self.assertEqual(200, response.code)
        self.assertDictEqual({}, json.loads(response.body))
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
        response = self.fetch('/api/getStatus', method='POST', body='')
        self.assertEqual(200, response.code)
        self.assertDictEqual({
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

    def test_get_answers(self):
        self.quiz_db.update_answer(
            quiz_id='test', question=1, team_id=5001, answer='Apple', answer_time=123)
        self.quiz_db.update_answer(
            quiz_id='test', question=1, team_id=5002, answer='Banana', answer_time=121)
        self.quiz_db.update_answer(
            quiz_id='ignored', question=2, team_id=5001, answer='Avocado', answer_time=125)
        self.quiz_db.update_answer(
            quiz_id='test', question=2, team_id=5001, answer='Andorra', answer_time=126)

        response = self.fetch('/api/getAnswers', method='POST',
                              body='{"update_id_greater_than": 0}')

        self.assertEqual(200, response.code)
        self.assertListEqual([
            {
                'quiz_id': 'test',
                'question': 1,
                'team_id': 5001,
                'answer': 'Apple',
                'timestamp': 123,
                'update_id': 1,
            }, {
                'quiz_id': 'test',
                'question': 1,
                'team_id': 5002,
                'answer': 'Banana',
                'timestamp': 121,
                'update_id': 2,
            }, {
                'quiz_id': 'test',
                'question': 2,
                'team_id': 5001,
                'answer': 'Andorra',
                'timestamp': 126,
                'update_id': 4,
            },
        ], json.loads(response.body)['answers'])

        response = self.fetch('/api/getAnswers', method='POST',
                              body='{"update_id_greater_than": 3}')

        self.assertEqual(200, response.code)
        self.assertListEqual([
            {
                'quiz_id': 'test',
                'question': 2,
                'team_id': 5001,
                'answer': 'Andorra',
                'timestamp': 126,
                'update_id': 4,
            },
        ], json.loads(response.body)['answers'])

        response = self.fetch('/api/getAnswers', method='POST',
                              body='{"update_id_greater_than": 5}')

        self.assertEqual(200, response.code)
        self.assertDictEqual({'answers': []}, json.loads(response.body))

    def test_get_answers_no_id_given(self):
        response = self.fetch('/api/getAnswers', method='POST', body='{}')
        self.assertEqual(400, response.code)
        self.assertIn('error', json.loads(response.body))


if __name__ == '__main__':
    unittest.main()
