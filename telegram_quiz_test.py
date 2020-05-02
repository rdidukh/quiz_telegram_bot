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
            "answer_confirmation": "Confirmed #{question}: {answer}.",
            "send_results_zero_correct_answers": "Zero answers.",
            "send_results_correct_answers": "Correct answers: {correctly_answered_questions}. Total: {total_score}."
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
        self.quiz = TelegramQuiz(strings_file=self.strings_file, quiz_db=self.quiz_db)

    def tearDown(self):
        self.test_dir.cleanup()


def _updater_factory(bot_api_token: str) -> telegram.ext.Updater:
    updater = telegram.ext.Updater(bot_api_token, use_context=True)
    updater.start_polling = MagicMock()
    updater.stop = MagicMock()
    return updater


class StartedQuizBaseTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.quiz.start(quiz_id='test', bot_api_token='123:TOKEN', language='lang', updater_factory=_updater_factory)


class StartTest(BaseTestCase):
    def test_starts(self):
        sub = MagicMock()
        self.quiz.add_updates_subscriber(sub)
        update_id = self.quiz.status_update_id

        self.quiz.start(quiz_id='test', bot_api_token='123:TOKEN', language='lang',
                        updater_factory=_updater_factory)

        self.assertIn(self.quiz._handle_error, self.quiz._updater.dispatcher.error_handlers)
        self.assertEqual(self.quiz._handle_log_update, self.quiz._updater.dispatcher.handlers[0][0].callback)
        self.quiz._updater.start_polling.assert_called_with()
        self.assertEqual('test', self.quiz._id)
        self.assertEqual('lang', self.quiz._language)
        self.assertEqual('Hello!', self.quiz._strings.registration_invitation)
        self.assertEqual(update_id+1, self.quiz.status_update_id)
        sub.assert_called_with()

    def test_raises_when_already_started(self):
        self.quiz.start(quiz_id='test', bot_api_token='123:TOKEN', language='lang',
                        updater_factory=_updater_factory)
        sub = MagicMock()
        self.quiz.add_updates_subscriber(sub)
        update_id = self.quiz.status_update_id

        self.assertRaises(TelegramQuizError, self.quiz.start, quiz_id='test', bot_api_token='123:TOKEN', language='lang')

        self.assertEqual(update_id, self.quiz.status_update_id)
        sub.assert_not_called()

    def test_drops_old_handlers_on_restart(self):
        self.quiz.start(quiz_id='test', bot_api_token='123:TOKEN', language='lang',
                        updater_factory=_updater_factory)
        self.quiz.start_question(1)
        self.quiz.stop()
        self.quiz.start(quiz_id='test', bot_api_token='123:TOKEN', language='lang',
                        updater_factory=_updater_factory)

        self.assertNotIn(1, self.quiz._updater.dispatcher.handlers)


class StopTest(StartedQuizBaseTestCase):
    def test_stops(self):
        sub = MagicMock()
        self.quiz.add_updates_subscriber(sub)
        update_id = self.quiz.status_update_id
        old_updater = self.quiz._updater

        self.quiz.stop()

        old_updater.stop.assert_called_with()
        self.assertIsNone(self.quiz._id)
        self.assertIsNone(self.quiz._language)
        self.assertIsNone(self.quiz._strings)
        self.assertIsNone(self.quiz._updater)
        self.assertEqual(update_id+1, self.quiz.status_update_id)
        sub.assert_called_with()

    def test_raises_when_already_stopped(self):
        self.quiz.stop()
        sub = MagicMock()
        self.quiz.add_updates_subscriber(sub)
        update_id = self.quiz.status_update_id

        self.assertRaises(TelegramQuizError, self.quiz.stop)

        self.assertEqual(update_id, self.quiz.status_update_id)
        sub.assert_not_called()

    def test_stops_registration(self):
        self.quiz.stop()
        self.assertIsNone(self.quiz._registration_handler)

    def test_stops_question(self):
        self.quiz.stop()
        self.assertIsNone(self.quiz._question_handler)


class StartRegistrationTest(StartedQuizBaseTestCase):
    def test_starts_registration(self):
        update_id = self.quiz.status_update_id
        self.quiz.start_registration()
        self.assertEqual(self.quiz._handle_registration_update,
                         self.quiz._updater.dispatcher.handlers[1][0].callback)
        self.assertGreater(self.quiz.status_update_id, update_id)

    def test_raises_when_starting_twice(self):
        self.quiz.start_registration()
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError, self.quiz.start_registration)
        self.assertEqual(self.quiz._handle_registration_update,
                         self.quiz._updater.dispatcher.handlers[1][0].callback)
        self.assertEqual(update_id, self.quiz.status_update_id)

    def test_raises_when_question_is_on(self):
        self.quiz.start_question(question=1)
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError, self.quiz.start_registration)
        self.assertEqual(update_id, self.quiz.status_update_id)

    def test_raises_when_quiz_not_started(self):
        self.quiz.stop()
        self.assertRaisesRegex(TelegramQuizError, 'not started', self.quiz.start_registration)


class StopRegistrationTest(StartedQuizBaseTestCase):
    def test_stops_registration(self):
        self.quiz.start_registration()
        update_id = self.quiz.status_update_id
        self.quiz.stop_registration()
        self.assertNotIn(1, self.quiz._updater.dispatcher.handlers)
        self.assertGreater(self.quiz.status_update_id, update_id)

    def test_raises_when_stopping_twice(self):
        self.quiz.start_registration()
        self.quiz.stop_registration()
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError, self.quiz.stop_registration)
        self.assertEqual(update_id, self.quiz.status_update_id)

    def test_raises_when_quiz_not_started(self):
        self.quiz.stop()
        self.assertRaisesRegex(TelegramQuizError, 'not started', self.quiz.stop_registration)


class StartQuestionTest(StartedQuizBaseTestCase):
    def test_starts_question(self):
        update_id = self.quiz.status_update_id
        self.quiz.start_question(question=1)
        self.assertEqual(self.quiz._handle_answer_update,
                         self.quiz._updater.dispatcher.handlers[1][0].callback)
        self.assertEqual(1, self.quiz._question)
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

    def test_raises_when_quiz_not_started(self):
        self.quiz.stop()
        self.assertRaisesRegex(TelegramQuizError, 'not started', self.quiz.start_question, 1)


class StopQuestionTest(StartedQuizBaseTestCase):
    def test_stops_question(self):
        self.quiz.start_question(question=1)
        update_id = self.quiz.status_update_id
        self.quiz.stop_question()
        self.assertNotIn(1, self.quiz._updater.dispatcher.handlers)
        self.assertIsNone(self.quiz._question)
        self.assertGreater(self.quiz.status_update_id, update_id)

    def test_stop_question_twice_raises(self):
        self.quiz.start_question(question=1)
        self.quiz.stop_question()
        update_id = self.quiz.status_update_id
        self.assertRaises(TelegramQuizError,
                          self.quiz.stop_question)
        self.assertEqual(update_id, self.quiz.status_update_id)

    def test_raises_when_quiz_not_started(self):
        self.quiz.stop()
        self.assertRaisesRegex(TelegramQuizError, 'not started', self.quiz.stop_question)


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


class HandleRegistrationUpdateTest(StartedQuizBaseTestCase):

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
            chat=telegram.Chat(5001, 'private'), text='\n  Unicode   \n    \n\n Юнікод\n 😎  \n \n'))
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


class HandleAnswerUpdateTest(StartedQuizBaseTestCase):
    @patch('telegram.ext.CallbackContext')
    def test_inserts_answer(self, mock_callback_context):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=1)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(4),
            chat=telegram.Chat(5001, 'private'), text=' \nUnicode\n Юнікод  😎   \n\n  '))
        update.message.reply_text = MagicMock()
        self.quiz._updater.dispatcher.run_async = MagicMock()

        self.quiz.start_question(question=1)
        self.quiz._handle_answer_update(update, context=None)
        self.quiz.stop_question()

        self.assertListEqual([
            Answer(quiz_id='test', question=1, team_id=5001,
                   answer='Unicode Юнікод 😎', timestamp=4),
        ], self.quiz_db.get_answers(quiz_id='test'))

        self.quiz._updater.dispatcher.run_async.assert_called_with(
            update.message.reply_text, 'Confirmed #1: Unicode Юнікод 😎.')

    @patch('telegram.ext.CallbackContext')
    def test_updates_answer(self, mock_callback_context):
        self.quiz_db.update_team(
            quiz_id='test', team_id=5001, name='Liverpool', registration_time=1)
        self.quiz_db.update_answer(
            quiz_id='test', question=4, team_id=5001, answer='Apple', answer_time=1)

        update = telegram.update.Update(1001, message=telegram.message.Message(
            2001, None,
            datetime.fromtimestamp(4),
            chat=telegram.Chat(5001, 'private'), text='Banana'))
        update.message.reply_text = MagicMock()
        self.quiz._updater.dispatcher.run_async = MagicMock()

        self.quiz.start_question(question=4)
        self.quiz._handle_answer_update(update, context=None)
        self.quiz.stop_question()

        expected_answers = [
            Answer(quiz_id='test', question=4, team_id=5001,
                   answer='Banana', timestamp=4),
        ]

        self.assertListEqual(
            expected_answers, self.quiz_db.get_answers(quiz_id='test'))
        self.quiz._updater.dispatcher.run_async.assert_called_with(
            update.message.reply_text, 'Confirmed #4: Banana.')

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


class GetStatusTest(StartedQuizBaseTestCase):
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

    def test_stop(self):
        self.quiz.stop()
        status = self.quiz.get_status()
        self.assertIsNone(status.quiz_id)
        self.assertIsNone(status.language)


class SendResultsTest(StartedQuizBaseTestCase):

    def test_answers(self):
        self.quiz_db.get_teams = MagicMock(return_value=[
            Team(quiz_id='test', id=5001,
                 name='Liverpool', timestamp=123),
        ])
        self.quiz_db.get_answers = MagicMock(return_value=[
            Answer(quiz_id='test', question=3, team_id=5001,
                   answer='Apple', timestamp=123, points=1),
            Answer(quiz_id='test', question=5, team_id=5001,
                   answer='Banana', timestamp=123, points=1)
        ])
        self.quiz._updater.bot.send_message = MagicMock()

        self.quiz.send_results(team_id=5001)

        self.quiz_db.get_teams.assert_called_with(quiz_id='test', team_id=5001)
        self.quiz_db.get_answers.assert_called_with(
            quiz_id='test', team_id=5001)
        self.quiz._updater.bot.send_message.assert_called_with(
            5001, 'Correct answers: 3, 5. Total: 2.')

    def test_zero_answers(self):
        self.quiz_db.get_teams = MagicMock(return_value=[
            Team(quiz_id='test', id=5001,
                 name='Liverpool', timestamp=123),
        ])
        self.quiz_db.get_answers = MagicMock(return_value=[
            Answer(quiz_id='test', question=3, team_id=5001,
                   answer='Apple', timestamp=123),
            Answer(quiz_id='test', question=5, team_id=5001,
                   answer='Banana', timestamp=123, points=0)
        ])
        self.quiz._updater.bot.send_message = MagicMock()

        self.quiz.send_results(team_id=5001)

        self.quiz_db.get_teams.assert_called_with(quiz_id='test', team_id=5001)
        self.quiz_db.get_answers.assert_called_with(
            quiz_id='test', team_id=5001)
        self.quiz._updater.bot.send_message.assert_called_with(
            5001, 'Zero answers.')

    def test_one_answer(self):
        self.quiz_db.get_teams = MagicMock(return_value=[
            Team(quiz_id='test', id=5001,
                 name='Liverpool', timestamp=123),
        ])
        self.quiz_db.get_answers = MagicMock(return_value=[
            Answer(quiz_id='test', question=3, team_id=5001,
                   answer='Apple', timestamp=123, points=1),
        ])
        self.quiz._updater.bot.send_message = MagicMock()

        self.quiz.send_results(team_id=5001)

        self.quiz._updater.bot.send_message.assert_called_with(
            5001, 'Correct answers: 3. Total: 1.')

    def test_send_message_raises(self):
        self.quiz_db.get_teams = MagicMock(return_value=[
            Team(quiz_id='test', id=5001,
                 name='Liverpool', timestamp=123),
        ])
        self.quiz_db.get_answers = MagicMock(return_value=[
            Answer(quiz_id='test', question=3, team_id=5001,
                   answer='Apple', timestamp=123, points=1),
        ])
        self.quiz._updater.bot.send_message = MagicMock(
            side_effect=telegram.error.TelegramError('Error.'))

        self.assertRaisesRegex(TelegramQuizError, 'Could not send',
                               self.quiz.send_results, team_id=5001)

    def test_team_does_not_exist(self):
        self.quiz_db.get_teams = MagicMock(return_value=[
        ])
        self.quiz_db.get_answers = MagicMock(return_value=[
            Answer(quiz_id='test', question=3, team_id=5001,
                   answer='Apple', timestamp=123, points=1),
        ])
        self.quiz._updater.bot.send_message = MagicMock()

        self.assertRaisesRegex(TelegramQuizError, 'does not exist',
                               self.quiz.send_results, team_id=5001)

    def test_raises_when_quiz_not_started(self):
        self.quiz.stop()
        self.assertRaisesRegex(TelegramQuizError, 'not started', self.quiz.send_results, team_id=5001)


if __name__ == '__main__':
    unittest.main()
