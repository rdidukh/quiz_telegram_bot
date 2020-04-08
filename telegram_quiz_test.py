from datetime import datetime
import logging
from telegram_quiz import TelegramQuiz
from quizzes_db import QuizzesDb
import tempfile
import telegram
import telegram.ext
import unittest
import os
from unittest.mock import patch, MagicMock


class TestTelegramQuiz(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'quizzes.db')
        self.quizzes_db = QuizzesDb(db_path=self.db_path)
        self.logger = logging.Logger('test')
        self.logger.addHandler(logging.NullHandler())
        self.updater = telegram.ext.Updater(
            token='123:TOKEN', use_context=True)

    def tearDown(self):
        self.test_dir.cleanup()

    @patch('telegram.ext.CallbackContext')
    def test_handle_registration_update(self, mock_callback_context):
        self.quizzes_db.insert_team(chat_id=1, quiz_id='test', name='Foo')
        self.quizzes_db.insert_team(chat_id=1, quiz_id='other', name='Foo')
        self.quizzes_db.insert_team(chat_id=2, quiz_id='test', name='Bar')
        self.quizzes_db.insert_team(
            chat_id=5001, quiz_id='test', name='OldName', timestamp=100)

        quiz = TelegramQuiz(id='test', updater=self.updater,
                            quizzes_db=self.quizzes_db, handler_group=1, logger=self.logger)

        self.assertDictEqual({1: 'Foo', 2: 'Bar', 5001: 'OldName'}, quiz.teams)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(1001001001),
            chat=telegram.Chat(5001, 'private'), text='/start'))
        update.message.reply_text = MagicMock()
        context = mock_callback_context()
        context.chat_data = {'typing_name': False}

        quiz._handle_registration_update(update, context)

        self.assertDictEqual({1: 'Foo', 2: 'Bar', 5001: 'OldName'}, quiz.teams)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(1001002001),
            chat=telegram.Chat(5001, 'private'), text='NewName'))
        update.message.reply_text = MagicMock()
        context = mock_callback_context()
        context.chat_data = {'typing_name': True}

        quiz._handle_registration_update(update, context)

        self.assertDictEqual({1: 'Foo', 2: 'Bar', 5001: 'NewName'}, quiz.teams)
        self.assertDictEqual({1: 'Foo', 2: 'Bar', 5001: 'NewName'},
                             self.quizzes_db.select_teams(quiz_id='test'))

    def test_start_stop_registration(self):
        quiz = TelegramQuiz(id='test', updater=self.updater,
                            quizzes_db=self.quizzes_db, handler_group=1, logger=self.logger)
        self.assertDictEqual({}, self.updater.dispatcher.handlers)
        quiz.start_registration()
        self.assertEqual(quiz._handle_registration_update,
                         self.updater.dispatcher.handlers[1][0].callback)

        # Test second call has not effect.
        quiz.start_registration()
        self.assertEqual(quiz._handle_registration_update,
                         self.updater.dispatcher.handlers[1][0].callback)

        quiz.stop_registration()
        self.assertDictEqual({}, self.updater.dispatcher.handlers)

    @patch('telegram.ext.CallbackContext')
    def test_handle_answer_update(self, mock_callback_context):
        self.quizzes_db.insert_answer(
            chat_id=5001, quiz_id='test', question_id='q1', team_name='', answer='Apple', timestamp=1)
        self.quizzes_db.insert_answer(
            chat_id=5002, quiz_id='test', question_id='q1', team_name='', answer='Orange', timestamp=2)
        self.quizzes_db.insert_answer(
            chat_id=5001, quiz_id='test2', question_id='q1', team_name='', answer='Pear', timestamp=3)
        quiz = TelegramQuiz(id='test', updater=self.updater,
                            quizzes_db=self.quizzes_db, handler_group=1, logger=self.logger)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(1001001001),
            chat=telegram.Chat(5001, 'private'), text='Banana'))

        quiz.start_question(question_id='q1')
        quiz._handle_answer_update(update, context=None)
        quiz.stop_question()

        expected_answers = {'q1': {5001: 'Banana', 5002: 'Orange'}}
        self.assertDictEqual(expected_answers, quiz.answers)
        self.assertDictEqual(
            expected_answers, self.quizzes_db.select_all_answers(quiz_id='test'))

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(1001001001),
            chat=telegram.Chat(5001, 'private'), text='London'))

        quiz.start_question(question_id='q2')
        quiz._handle_answer_update(update, context=None)
        quiz.stop_question()

        expected_answers = {'q1': {5001: 'Banana', 5002: 'Orange'}, 'q2': {5001: 'London'}}
        self.assertDictEqual(expected_answers, quiz.answers)
        self.assertDictEqual(
            expected_answers, self.quizzes_db.select_all_answers(quiz_id='test'))


if __name__ == '__main__':
    unittest.main()
