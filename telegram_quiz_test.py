from datetime import datetime
from telegram_quiz import QuizStatus, TelegramQuiz, TelegramQuizError, Updates
from quiz_db import Answer, Message, QuizDb, Team
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
            "registration_confirmation": "Good luck, {team}!",
            "answer_confirmation": "Confirmed: {answer}."
        }
    }
''')


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, 'quiz.db')
        self.strings_file = os.path.join(self.test_dir.name, 'strings.json')
        with open(self.strings_file, 'w') as file:
            file.write(STRINGS)
        self.quiz_db = QuizDb(db_path=self.db_path)
        self.quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', number_of_questions=2, language='lang',
                                 strings_file=self.strings_file, quiz_db=self.quiz_db)

    def tearDown(self):
        self.test_dir.cleanup()


class TestTelegramQuiz(BaseTestCase):

    def test_start_stop_registration(self):
        self.assertDictEqual({}, self.quiz.updater.dispatcher.handlers)
        self.quiz.start_registration()
        self.assertEqual(self.quiz._handle_registration_update,
                         self.quiz.updater.dispatcher.handlers[1][0].callback)

        self.assertRaises(TelegramQuizError, self.quiz.start_registration)
        self.assertEqual(self.quiz._handle_registration_update,
                         self.quiz.updater.dispatcher.handlers[1][0].callback)

        self.quiz.stop_registration()
        self.assertDictEqual({}, self.quiz.updater.dispatcher.handlers)

        self.assertRaises(TelegramQuizError, self.quiz.stop_registration)

        self.quiz.start_question(question_id='01')
        self.assertRaises(TelegramQuizError, self.quiz.start_registration)

    def test_start_stop_question(self):
        self.assertDictEqual({}, self.quiz.updater.dispatcher.handlers)
        self.quiz.start_question(question_id='01')
        self.assertEqual(self.quiz._handle_answer_update,
                         self.quiz.updater.dispatcher.handlers[1][0].callback)
        self.assertEqual('01', self.quiz.question_id)

        self.assertRaises(TelegramQuizError,
                          self.quiz.start_question, question_id='01')

        self.quiz.stop_question()
        self.assertDictEqual({}, self.quiz.updater.dispatcher.handlers)
        self.assertIsNone(self.quiz.question_id)

        self.assertRaises(TelegramQuizError, self.quiz.stop_question)

    def test_handle_log_update(self):
        self.quiz_db.insert_message(
            Message(timestamp=1, update_id=2, chat_id=3, text='existing'))

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(1001001001),
            chat=telegram.Chat(5001, 'private'), text='Hello, Юнікод! 😎'))

        self.quiz._handle_log_update(update, context=None)

        self.assertListEqual([
            Message(timestamp=1, update_id=2, chat_id=3, text='existing'),
            Message(timestamp=1001001001, update_id=1001,
                    chat_id=5001, text='Hello, Юнікод! 😎'),
        ], self.quiz_db.select_messages())


class HandleRegistrationUpdateTest(BaseTestCase):

    @patch('telegram.ext.CallbackContext')
    def test_sends_invitation(self, mock_callback_context):
        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(1001001001),
            chat=telegram.Chat(5001, 'private'), text='/start'))
        update.message.reply_text = MagicMock()
        context = mock_callback_context()
        context.chat_data = {'typing_name': False}

        self.quiz._handle_registration_update(update, context)

        self.assertListEqual([], self.quiz_db.get_teams(quiz_id='test'))
        self.assertEqual(True, context.chat_data['typing_name'])
        update.message.reply_text.assert_called_with('Hello!')

    @patch('telegram.ext.CallbackContext')
    def test_registers_team(self, mock_callback_context):
        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(123),
            chat=telegram.Chat(5001, 'private'), text='Unicode Юнікод 😎'))
        update.message.reply_text = MagicMock()
        context = mock_callback_context()
        context.chat_data = {'typing_name': True}

        self.quiz._handle_registration_update(update, context)

        self.assertListEqual([
            Team(update_id=2, quiz_id='test', id=5001, name='Unicode Юнікод 😎',
                 timestamp=123)
        ], self.quiz_db.get_teams(quiz_id='test'))
        self.assertNotIn('typing_name', context.chat_data)
        update.message.reply_text.assert_called_with(
            'Good luck, Unicode Юнікод 😎!')

    @patch('telegram.ext.CallbackContext')
    def test_updates_team(self, mock_callback_context):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Apple', registration_time=122)
        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(123),
            chat=telegram.Chat(5001, 'private'), text='Banana'))
        update.message.reply_text = MagicMock()
        context = mock_callback_context()
        context.chat_data = {'typing_name': True}

        self.quiz._handle_registration_update(update, context)

        self.assertListEqual([
            Team(quiz_id='test', id=5001, name='Banana',
                 timestamp=123)
        ], self.quiz_db.get_teams(quiz_id='test'))
        self.assertNotIn('typing_name', context.chat_data)
        update.message.reply_text.assert_called_with('Good luck, Banana!')

    @patch('telegram.ext.CallbackContext')
    def test_outdated_registration(self, mock_callback_context):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Apple', registration_time=124)
        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(123),
            chat=telegram.Chat(5001, 'private'), text='Banana'))
        update.message.reply_text = MagicMock()
        context = mock_callback_context()
        context.chat_data = {'typing_name': True}

        self.quiz._handle_registration_update(update, context)

        self.assertListEqual([
            Team(quiz_id='test', id=5001, name='Apple',
                 timestamp=124)
        ], self.quiz_db.get_teams(quiz_id='test'))
        self.assertNotIn('typing_name', context.chat_data)
        update.message.reply_text.assert_not_called()


class HandleAnswerUpdateTest(BaseTestCase):
    @patch('telegram.ext.CallbackContext')
    def test_inserts_answer(self, mock_callback_context):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=1)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(4),
            chat=telegram.Chat(5001, 'private'), text='Banana'))
        update.message.reply_text = MagicMock()

        self.quiz.start_question(question_id='01')
        self.quiz._handle_answer_update(update, context=None)
        self.quiz.stop_question()

        self.assertListEqual([
            Answer(quiz_id='test', question=1, team_id=5001,
                   answer='Banana', timestamp=4),
        ], self.quiz_db.get_answers(quiz_id='test'))
        update.message.reply_text.assert_called_with('Confirmed: Banana.')

    @patch('telegram.ext.CallbackContext')
    def test_updates_answer(self, mock_callback_context):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=1)
        self.quiz_db.update_answer(
            quiz_id='test', question=1, team_id=5001, answer='Apple', answer_time=1)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(4),
            chat=telegram.Chat(5001, 'private'), text='Banana'))
        update.message.reply_text = MagicMock()

        self.quiz.start_question(question_id='01')
        self.quiz._handle_answer_update(update, context=None)
        self.quiz.stop_question()

        expected_answers = [
            Answer(quiz_id='test', question=1, team_id=5001,
                   answer='Banana', timestamp=4),
        ]

        expected_answers_dict = {'01': {5001: 'Banana'}}
        self.assertDictEqual(expected_answers_dict, self.quiz.answers)
        self.assertListEqual(
            expected_answers, self.quiz_db.get_answers(quiz_id='test'))
        update.message.reply_text.assert_called_with('Confirmed: Banana.')

    @patch('telegram.ext.CallbackContext')
    def test_non_registered_team(self, mock_callback_context):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=1)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(4),
            chat=telegram.Chat(5002, 'private'), text='Banana'))
        update.message.reply_text = MagicMock()

        self.quiz.start_question(question_id='01')
        self.quiz._handle_answer_update(update, context=None)
        self.quiz.stop_question()

        self.assertListEqual([], self.quiz_db.get_answers(quiz_id='test'))
        update.message.reply_text.assert_not_called()

    @patch('telegram.ext.CallbackContext')
    def test_outdated_answer(self, mock_callback_context):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=1)
        self.quiz_db.update_answer(
            quiz_id='test', question=1, team_id=5001, answer='Banana', answer_time=5)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(4),
            chat=telegram.Chat(5001, 'private'), text='Apple'))
        update.message.reply_text = MagicMock()

        self.quiz.start_question(question_id='01')
        self.quiz._handle_answer_update(update, context=None)
        self.quiz.stop_question()

        self.assertListEqual([
            Answer(quiz_id='test', question=1,
                   team_id=5001, answer='Banana', timestamp=5),
        ], self.quiz_db.get_answers(quiz_id='test'))
        update.message.reply_text.assert_not_called()


class HandleGetUpdatesTest(BaseTestCase):
    def test_init(self):
        updates = self.quiz.get_updates(update_id_greater_than=0)
        self.assertEqual(Updates(
            status=QuizStatus(
                quiz_id='test',
                number_of_questions=2,
                language='lang',
                question=None,
                registration=False,
            ),
            teams=[],
            answers=[],
        ), updates)

    def test_start_registration(self):
        self.quiz.start_registration()
        updates = self.quiz.get_updates(update_id_greater_than=0)
        self.assertEqual(Updates(
            status=QuizStatus(
                quiz_id='test',
                number_of_questions=2,
                language='lang',
                question=None,
                registration=True,
            ),
            teams=[],
            answers=[],
        ), updates)

    def test_stop_registration(self):
        self.quiz.start_registration()
        self.quiz.stop_registration()
        updates = self.quiz.get_updates(update_id_greater_than=0)
        self.assertEqual(Updates(
            status=QuizStatus(
                quiz_id='test',
                number_of_questions=2,
                language='lang',
                question=None,
                registration=False,
            ),
            teams=[],
            answers=[],
        ), updates)

    def test_start_question(self):
        self.quiz.start_question('01')
        updates = self.quiz.get_updates(
            update_id_greater_than=0)
        self.assertEqual(Updates(
            status=QuizStatus(
                quiz_id='test',
                number_of_questions=2,
                language='lang',
                question=1,
                registration=False,
            ),
            teams=[],
            answers=[],
        ), updates)

    def test_stop_question(self):
        self.quiz.start_question('01')
        self.quiz.stop_question()
        updates = self.quiz.get_updates(
            update_id_greater_than=0)
        self.assertEqual(Updates(
            status=QuizStatus(
                quiz_id='test',
                number_of_questions=2,
                language='lang',
                question=None,
                registration=False,
            ),
            teams=[],
            answers=[],
        ), updates)

    def test_teams_and_answers(self):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=123)
        self.quiz_db.update_answer(
            quiz_id='test', question=2, team_id=5002, answer='Apple', answer_time=125)
        updates = self.quiz.get_updates(update_id_greater_than=0)
        self.assertEqual(Updates(
            status=QuizStatus(
                quiz_id='test',
                number_of_questions=2,
                language='lang',
                question=None,
                registration=False,
            ),
            teams=[
                Team(quiz_id='test', id=5001,
                     name='Liverpool', timestamp=123)
            ],
            answers=[
                Answer(quiz_id='test', question=2, team_id=5002,
                       answer='Apple', timestamp=125)
            ],
        ), updates)

    def test_recent_teams_and_answers(self):
        update_id = self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=123)
        self.quiz_db.update_answer(
            quiz_id='test', question=2, team_id=5002, answer='Apple', answer_time=125)
        updates = self.quiz.get_updates(update_id_greater_than=update_id)
        self.assertEqual(Updates(
            status=QuizStatus(
                quiz_id='test',
                number_of_questions=2,
                language='lang',
                question=None,
                registration=False,
            ),
            teams=[],
            answers=[
                Answer(quiz_id='test', question=2, team_id=5002,
                       answer='Apple', timestamp=125)
            ],
        ), updates)


if __name__ == '__main__':
    unittest.main()
