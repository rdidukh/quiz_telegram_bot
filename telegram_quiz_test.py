from datetime import datetime
import logging
from telegram_quiz import TelegramQuiz, TelegramQuizError
from quiz_db import Answer, Message, QuizDb
import tempfile
import telegram
import telegram.ext
import textwrap
import unittest
import os
from unittest.mock import patch, MagicMock

STRINGS = textwrap.dedent('''
    {
        "lang": {
            "registration_invitation": "Hello!",
            "registration_confirmation": "Good luck!",
            "answer_confirmation": "Confirmed."
        }
    }
''')


class TestTelegramQuiz(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'quiz.db')
        self.strings_file = os.path.join(self.test_dir.name, 'strings.json')
        with open(self.strings_file, 'w') as file:
            file.write(STRINGS)
        self.quiz_db = QuizDb(db_path=self.db_path)
        self.logger = logging.Logger('test')
        self.logger.addHandler(logging.NullHandler())

    def tearDown(self):
        self.test_dir.cleanup()

    @patch('telegram.ext.CallbackContext')
    def test_handle_registration_update(self, mock_callback_context):
        self.quiz_db.insert_team(
            chat_id=1, quiz_id='test', name='Foo', timestamp=1)
        self.quiz_db.insert_team(
            chat_id=1, quiz_id='other', name='Foo', timestamp=2)
        self.quiz_db.insert_team(
            chat_id=2, quiz_id='test', name='Bar', timestamp=2)
        self.quiz_db.insert_team(
            chat_id=5001, quiz_id='test', name='OldName', timestamp=100)

        quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', number_of_questions=1, language='lang',
                            strings_file=self.strings_file, quiz_db=self.quiz_db, logger=self.logger)

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
        update.message.reply_text.assert_called_with('Hello!')

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
                             self.quiz_db.select_teams(quiz_id='test'))
        update.message.reply_text.assert_called_with('Good luck!')

    def test_start_stop_registration(self):
        quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', number_of_questions=1, language='lang',
                            strings_file=self.strings_file, quiz_db=self.quiz_db, logger=self.logger)
        self.assertDictEqual({}, quiz.updater.dispatcher.handlers)
        quiz.start_registration()
        self.assertEqual(quiz._handle_registration_update,
                         quiz.updater.dispatcher.handlers[1][0].callback)

        self.assertRaises(TelegramQuizError, quiz.start_registration)
        self.assertEqual(quiz._handle_registration_update,
                         quiz.updater.dispatcher.handlers[1][0].callback)

        quiz.stop_registration()
        self.assertDictEqual({}, quiz.updater.dispatcher.handlers)

        self.assertRaises(TelegramQuizError, quiz.stop_registration)

        quiz.start_question(question_id='01')
        self.assertRaises(TelegramQuizError, quiz.start_registration)

    @patch('telegram.ext.CallbackContext')
    def test_handle_answer_update(self, mock_callback_context):
        self.quiz_db.insert_team(
            chat_id=5001, quiz_id='test', name='Liverpool', timestamp=1)
        self.quiz_db.insert_team(
            chat_id=5002, quiz_id='test', name='Tottenham', timestamp=1)

        self.quiz_db.insert_answer(
            Answer(quiz_id='test', question=1, team_id=5001, answer='Apple', timestamp=1))
        self.quiz_db.insert_answer(
            Answer(quiz_id='test', question=1, team_id=5002, answer='Orange', timestamp=2))
        self.quiz_db.insert_answer(
            Answer(quiz_id='test2', question=1, team_id=5001, answer='Pear', timestamp=3))

        quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', number_of_questions=2, language='lang',
                            strings_file=self.strings_file, quiz_db=self.quiz_db, logger=self.logger)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(4),
            chat=telegram.Chat(5001, 'private'), text='Banana'))
        update.message.reply_text = MagicMock()

        quiz.start_question(question_id='01')
        quiz._handle_answer_update(update, context=None)
        quiz.stop_question()

        expected_answers = [
            Answer(quiz_id='test', question=1, team_id=5001,
                   answer='Banana', timestamp=4),
            Answer(quiz_id='test', question=1, team_id=5002,
                   answer='Orange', timestamp=2),
        ]

        expected_answers_dict = {'01': {5001: 'Banana', 5002: 'Orange'}}
        self.assertDictEqual(expected_answers_dict, quiz.answers)
        self.assertListEqual(
            expected_answers, self.quiz_db.get_answers_for_quiz(quiz_id='test'))
        update.message.reply_text.assert_called_with('Confirmed.')

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(9),
            chat=telegram.Chat(13, 'private'), text='Non-registered'))
        update.message.reply_text = MagicMock()

        quiz.start_question(question_id='01')
        quiz._handle_answer_update(update, context=None)
        quiz.stop_question()

        expected_answers = [
            Answer(quiz_id='test', question=1, team_id=5001,
                   answer='Banana', timestamp=4),
            Answer(quiz_id='test', question=1, team_id=5002,
                   answer='Orange', timestamp=2),
        ]
        expected_answers_dict = {'01': {5001: 'Banana', 5002: 'Orange'}}
        self.assertDictEqual(expected_answers_dict, quiz.answers)
        self.assertListEqual(
            expected_answers, self.quiz_db.get_answers_for_quiz(quiz_id='test'))
        update.message.reply_text.assert_not_called()

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(7),
            chat=telegram.Chat(5001, 'private'), text='London'))
        update.message.reply_text = MagicMock()

        quiz.start_question(question_id='02')
        quiz._handle_answer_update(update, context=None)
        quiz.stop_question()

        expected_answers = [
            Answer(quiz_id='test', question=1, team_id=5001,
                   answer='Banana', timestamp=4),
            Answer(quiz_id='test', question=1, team_id=5002,
                   answer='Orange', timestamp=2),
            Answer(quiz_id='test', question=2, team_id=5001,
                   answer='London', timestamp=7),
        ]

        expected_answers_dict = {'01': {5001: 'Banana',
                                        5002: 'Orange'}, '02': {5001: 'London'}}

        self.assertDictEqual(expected_answers_dict, quiz.answers)
        self.assertListEqual(
            expected_answers, self.quiz_db.get_answers_for_quiz(quiz_id='test'))
        update.message.reply_text.assert_called_once()

    def test_start_stop_question(self):
        quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', number_of_questions=1, language='lang',
                            strings_file=self.strings_file, quiz_db=self.quiz_db, logger=self.logger)
        self.assertDictEqual({}, quiz.updater.dispatcher.handlers)
        quiz.start_question(question_id='01')
        self.assertEqual(quiz._handle_answer_update,
                         quiz.updater.dispatcher.handlers[1][0].callback)
        self.assertEqual('01', quiz.question_id)

        self.assertRaises(TelegramQuizError,
                          quiz.start_question, question_id='01')

        quiz.stop_question()
        self.assertDictEqual({}, quiz.updater.dispatcher.handlers)
        self.assertIsNone(quiz.question_id)

        self.assertRaises(TelegramQuizError, quiz.stop_question)

    def test_handle_log_update(self):
        quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', number_of_questions=1, language='lang',
                            strings_file=self.strings_file, quiz_db=self.quiz_db, logger=self.logger)

        self.quiz_db.insert_message(
            Message(timestamp=1, update_id=2, chat_id=3, text='existing'))

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(1001001001),
            chat=telegram.Chat(5001, 'private'), text='Hello, Юнікод! 😎'))

        quiz._handle_log_update(update, context=None)

        self.assertListEqual([
            Message(timestamp=1, update_id=2, chat_id=3, text='existing'),
            Message(timestamp=1001001001, update_id=1001,
                    chat_id=5001, text='Hello, Юнікод! 😎'),
        ], self.quiz_db.select_messages())


if __name__ == '__main__':
    unittest.main()
