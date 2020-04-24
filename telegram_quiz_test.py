from datetime import datetime
from telegram_quiz import QuizStatus, TelegramQuiz, TelegramQuizError
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
        self.quiz = TelegramQuiz(id='test', bot_token='123:TOKEN', language='lang',
                                 strings_file=self.strings_file, quiz_db=self.quiz_db)

    def tearDown(self):
        self.test_dir.cleanup()


class StartRegistrationTest(BaseTestCase):
    def test_starts_registration(self):
        update_id = self.quiz.status_update_id
        self.assertDictEqual({}, self.quiz.updater.dispatcher.handlers)
        self.quiz.start_registration()
        self.assertEqual(self.quiz._handle_registration_update,
                         self.quiz.updater.dispatcher.handlers[1][0].callback)
        self.assertGreater(self.quiz.status_update_id, update_id)

    def test_raises_when_starting_twice(self):
        self.quiz.start_registration()
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError, self.quiz.start_registration)
        self.assertEqual(self.quiz._handle_registration_update,
                         self.quiz.updater.dispatcher.handlers[1][0].callback)
        self.assertEqual(update_id, self.quiz.status_update_id)

    def test_raises_when_question_is_on(self):
        self.quiz.start_question(question=1)
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError, self.quiz.start_registration)
        self.assertEqual(update_id, self.quiz.status_update_id)


class StopRegistrationTest(BaseTestCase):
    def test_stops_registration(self):
        self.quiz.start_registration()
        update_id = self.quiz.status_update_id
        self.quiz.stop_registration()
        self.assertDictEqual({}, self.quiz.updater.dispatcher.handlers)
        self.assertGreater(self.quiz.status_update_id, update_id)

    def test_raises_when_stopping_twice(self):
        self.quiz.start_registration()
        self.quiz.stop_registration()
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError, self.quiz.stop_registration)
        self.assertEqual(update_id, self.quiz.status_update_id)


class StartQuestionTest(BaseTestCase):
    def test_starts_question(self):
        update_id = self.quiz.status_update_id
        self.assertDictEqual({}, self.quiz.updater.dispatcher.handlers)
        self.quiz.start_question(question=1)
        self.assertEqual(self.quiz._handle_answer_update,
                         self.quiz.updater.dispatcher.handlers[1][0].callback)
        self.assertEqual(1, self.quiz.question)
        self.assertGreater(self.quiz.status_update_id, update_id)

    def test_start_question_twice_raises(self):
        self.quiz.start_question(question=1)
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError,
                          self.quiz.start_question, question=1)
        self.assertEqual(update_id, self.quiz.status_update_id)

    def test_start_raises_when_registration_is_on(self):
        self.quiz.start_registration()
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError,
                          self.quiz.start_question, question=1)
        self.assertEqual(update_id, self.quiz.status_update_id)


class StopQuestionTest(BaseTestCase):
    def test_stops_question(self):
        self.quiz.start_question(question=1)
        update_id = self.quiz.status_update_id
        self.quiz.stop_question()
        self.assertDictEqual({}, self.quiz.updater.dispatcher.handlers)
        self.assertIsNone(self.quiz.question)
        self.assertGreater(self.quiz.status_update_id, update_id)

    def test_stop_question_twice_raises(self):
        self.quiz.start_question(question=1)
        self.quiz.stop_question()
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError,
                          self.quiz.stop_question)
        self.assertEqual(update_id, self.quiz.status_update_id)


class HandleLogUpdateTest(BaseTestCase):
    def test_logs_update(self):
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

        self.quiz.start_registration()
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

        self.quiz.start_registration()
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

        self.quiz.start_registration()
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

        self.quiz.start_registration()
        self.quiz._handle_registration_update(update, context)

        self.assertListEqual([
            Team(quiz_id='test', id=5001, name='Apple',
                 timestamp=124)
        ], self.quiz_db.get_teams(quiz_id='test'))
        self.assertNotIn('typing_name', context.chat_data)
        update.message.reply_text.assert_not_called()

    def test_registration_not_started(self):
        self.quiz._handle_registration_update(None, None)
        self.assertListEqual([], self.quiz_db.get_teams(quiz_id='test'))


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
        self.quiz.updater.dispatcher.run_async = MagicMock()

        self.quiz.start_question(question=1)
        self.quiz._handle_answer_update(update, context=None)
        self.quiz.stop_question()

        self.assertListEqual([
            Answer(quiz_id='test', question=1, team_id=5001,
                   answer='Banana', timestamp=4),
        ], self.quiz_db.get_answers(quiz_id='test'))

        self.quiz.updater.dispatcher.run_async.assert_called_with(
            update.message.reply_text, 'Confirmed: Banana.')

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
        self.quiz.updater.dispatcher.run_async = MagicMock()

        self.quiz.start_question(question=1)
        self.quiz._handle_answer_update(update, context=None)
        self.quiz.stop_question()

        expected_answers = [
            Answer(quiz_id='test', question=1, team_id=5001,
                   answer='Banana', timestamp=4),
        ]

        self.assertListEqual(
            expected_answers, self.quiz_db.get_answers(quiz_id='test'))
        self.quiz.updater.dispatcher.run_async.assert_called_with(
            update.message.reply_text, 'Confirmed: Banana.')

    @patch('telegram.ext.CallbackContext')
    def test_non_registered_team(self, mock_callback_context):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=1)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(4),
            chat=telegram.Chat(5002, 'private'), text='Banana'))
        update.message.reply_text = MagicMock()

        self.quiz.start_question(question=1)
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

        self.quiz.start_question(question=1)
        self.quiz._handle_answer_update(update, context=None)
        self.quiz.stop_question()

        self.assertListEqual([
            Answer(quiz_id='test', question=1,
                   team_id=5001, answer='Banana', timestamp=5),
        ], self.quiz_db.get_answers(quiz_id='test'))
        update.message.reply_text.assert_not_called()

    def test_question_not_started(self):
        self.quiz._handle_answer_update(update=None, context=None)
        self.assertListEqual([], self.quiz_db.get_answers(quiz_id='test'))


class GetStatusTest(BaseTestCase):
    def test_returns_status(self):
        status = self.quiz.get_status()

        self.assertEqual(
            QuizStatus(
                update_id=self.quiz.status_update_id,
                quiz_id='test',
                language='lang',
                question=None,
                registration=False,
            ), status
        )

        self.assertIsInstance(status.time, str)
        self.assertGreater(len(status.time), 0)

    def test_registration(self):
        self.quiz.start_registration()
        status = self.quiz.get_status()
        self.assertTrue(status.registration)

    def test_question(self):
        self.quiz.start_question(question=1)
        status = self.quiz.get_status()
        self.assertEqual(1, status.question)


if __name__ == '__main__':
    unittest.main()
