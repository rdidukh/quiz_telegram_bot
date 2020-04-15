from dataclasses import dataclass
import json
import logging
from quiz_db import Answer, Message, QuizDb, Team
import telegram.ext
import telegram.update
import time
from typing import Dict, Set


class TelegramQuizError(Exception):
    pass


@dataclass
class Strings:
    registration_invitation: str = ''
    registration_confirmation: str = ''
    answer_confirmation: str = ''


def _create_team_index(*, quiz_id: str, quiz_db: QuizDb) -> Dict[int, Team]:
    teams = quiz_db.get_teams_for_quiz(quiz_id)
    return {team.id: team for team in teams}


class TelegramQuiz:
    def __init__(self, *, id: str,
                 bot_token: str,
                 quiz_db: QuizDb,
                 number_of_questions: int,
                 strings_file: str,
                 language: str):
        self.id = id
        self.quiz_db = quiz_db
        self.registration_handler: telegram.ext.MessageHandler = None
        self.question_handler: telegram.ext.MessageHandler = None
        self.question_set: Set[str] = {f'{i:02}' for i in range(
            1, number_of_questions + 1)}
        self.number_of_questions = number_of_questions
        self.question_id: str = None
        self.updater = telegram.ext.Updater(bot_token, use_context=True)
        self.language = language
        self.strings: Strings = self._get_strings(strings_file, language)
        # DEPRECATED: Used to support old tests.
        self._answers_for_testing = None
        self._teams_for_testing = None

    def _get_strings(self, strings_file: str, language: str) -> Strings:
        try:
            with open(strings_file) as file:
                content = file.read()
        except Exception as e:
            raise TelegramQuizError(f'Could not read file {strings_file}: {e}')

        try:
            obj = json.loads(content)
        except json.JSONDecodeError as e:
            raise TelegramQuizError(
                f'Could not parse file {strings_file}: {e}')

        if language not in obj:
            raise TelegramQuizError(
                f'Language {language} is not supported in file {strings_file}')

        strings = Strings()
        for string in ("registration_invitation", "registration_confirmation", "answer_confirmation"):
            if string not in obj[language]:
                raise TelegramQuizError(
                    f'String {string} for language {language} not specified in file {strings_file}')
            setattr(strings, string, obj[language][string])

        return strings

    # DEPRECATED: Left for backward compatibility only.
    @property
    def answers(self) -> Dict[str, Dict[int, str]]:
        # This is a hack, but the method is going to be removed soon anyway.
        if self._answers_for_testing:
            return self._answers_for_testing
        result: Dict[str, Dict[int, str]] = {}
        answers = self.quiz_db.get_answers(quiz_id=self.id)
        for answer in answers:
            question = f'{answer.question:02}'
            if question not in result:
                result[question] = {}
            result[question][answer.team_id] = answer.answer
        return result

    # DEPRECATED: Left for testing only.
    @answers.setter
    def answers(self, value):
        self._answers_for_testing = value

    # DEPRECATED: Left for backward compatibility only.
    @property
    def teams(self) -> Dict[int, str]:
        if self._teams_for_testing:
            return self._teams_for_testing
        teams = self.quiz_db.get_teams_for_quiz(self.id)
        return {team.id: team.name for team in teams}

    # DEPRECATED: Left for testing only.
    @teams.setter
    def teams(self, value):
        self._teams_for_testing = value

    def _handle_registration_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        chat_id = update.message.chat_id
        message: telegram.message.Message = update.message

        if context.chat_data.get('typing_name'):
            del context.chat_data['typing_name']
            text = update.message.text
            timestamp = update.message.date.timestamp()
            logging.info(
                f'Registration message. chat_id: {chat_id}, quiz_id: "{self.id}", name: "{text}"')
            message.reply_text(
                self.strings.registration_confirmation.format(team=text))
            self.quiz_db.insert_team(
                Team(quiz_id=self.id, id=chat_id, name=text, timestamp=timestamp))
        else:
            logging.info(
                f'Requesting a team to send their name. chat_id: {chat_id}, quiz_id: "{self.id}"')
            context.chat_data['typing_name'] = True
            message.reply_text(self.strings.registration_invitation)

    def start_registration(self):
        if self.question_id:
            logging.warning(f'Trying to start registration for quiz "{self.id}", '
                            f'but question "{self.question_id}" is already started.')
            raise TelegramQuizError(
                f'Can not start registration of quiz "{self.id}" when question "{self.question_id}" is running.')
        if self.registration_handler:
            logging.warning(
                f'Trying to start registration for game "{self.id}", but registration is already running.')
            raise TelegramQuizError(
                f'Can not start registration of quiz "{self.id}" because registration is already on.')
        self.registration_handler = telegram.ext.MessageHandler(
            telegram.ext.Filters.text, self._handle_registration_update)
        self.updater.dispatcher.add_handler(
            self.registration_handler, group=1)
        logging.info(f'Registration for game "{self.id}" has started.')

    def stop_registration(self):
        if not self.registration_handler:
            logging.warning(
                f'Trying to stop registration for quiz "{self.id}", but registration was not running.')
            raise TelegramQuizError(
                f'Can not stop registration of quiz "{self.id}" because registration is not running.')
        self.updater.dispatcher.remove_handler(
            self.registration_handler, group=1)
        self.registration_handler = None
        logging.info(f'Registration for game "{self.id}" has ended.')

    def is_registration(self) -> bool:
        return self.registration_handler is not None

    def _handle_answer_update(self, update: telegram.update.Update, context: telegram.ext.CallbackContext):
        start_time = time.time()
        chat_id = update.message.chat_id
        answer = update.message.text
        timestamp = update.message.date.timestamp()
        team = self.quiz_db.get_team(quiz_id=self.id, team_id=chat_id)
        if team is None:
            return
        logging.info(f'Answer received. '
                     f'question_id: {self.question_id}, quiz_id: {self.id}, team_id: {team.id}, '
                     f'team: "{team.name}", answer: "{answer}"')

        self.quiz_db.insert_answer(Answer(
            quiz_id=self.id,
            question=int(self.question_id),
            team_id=chat_id,
            answer=answer,
            timestamp=timestamp,
        ))

        update.message.reply_text(
            self.strings.answer_confirmation.format(answer=answer))
        logging.info(f'Answer update handler took {(time.time() - start_time):.6f} sec.')

    def start_question(self, question_id: str):
        if self.registration_handler:
            logging.warning(f'Trying to start question "{question_id}" for game "{self.id}", '
                            f'but the registration is not finished.')
            raise TelegramQuizError(
                'Can not start a question during registration.')
        if self.question_id:
            logging.warning(f'Trying to start question "{question_id}" for game "{self.id}", '
                            f'but question "{self.question_id}" is already started.')
            raise TelegramQuizError(
                'Can not start a question during another question.')
        if question_id not in self.question_set:
            logging.warning(f'Trying to start question "{question_id}" for game "{self.id}", '
                            f'but it is not in the question set.')
            raise TelegramQuizError(
                f'Can not start question "{question_id}" which is not in the question set.')
        self.question_handler = telegram.ext.MessageHandler(
            telegram.ext.Filters.text, self._handle_answer_update)
        self.updater.dispatcher.add_handler(
            self.question_handler, group=1)
        self.question_id = question_id
        logging.info(
            f'Question "{question_id}" for game "{self.id}" has started.')

    def stop_question(self):
        if not self.question_id:
            logging.warning(
                f'Attempt to stop a question, but no question was running. quiz_id: "{self.id}".')
            raise TelegramQuizError(
                'Can not stop a question, when no question is running.')
        self.updater.dispatcher.remove_handler(
            self.question_handler, group=1)
        self.question_id = None
        self.question_handler = None
        logging.info(
            f'Question "{self.question_id}" for game "{self.id}" has ended.')

    def _handle_log_update(self, update: telegram.update.Update, context):
        update_id = update.update_id or 0
        message: telegram.message.Message = update.message
        if not message:
            logging.warning(
                f'Telegram update with no message. update_id: {update_id}.')
            return
        timestamp = int(message.date.timestamp()) if message.date else 0
        chat_id = message.chat_id or 0
        text = message.text or ''

        logging.info(
            f'message: timestamp:{timestamp}, chat_id:{chat_id}, text: "{text}"')
        logging.info('Committing values to database...')
        self.quiz_db.insert_message(Message(
            timestamp=timestamp, update_id=update_id, chat_id=chat_id, text=text))
        logging.info('Committing values to database done.')

    def _handle_error(self, update, context):
        logging.error('Update "%s" caused error "%s"',
                      update, context.error)

    def start(self):
        self.updater.dispatcher.add_error_handler(self._handle_error)
        self.updater.dispatcher.add_handler(telegram.ext.MessageHandler(
            telegram.ext.Filters.text, self._handle_log_update))
        self.updater.start_polling()

    def stop(self):
        self.updater.stop()
