import argparse
import logging
from quiz_http_server import QuizHttpServer
from quizzes_db import QuizzesDb
from telegram_quiz import TelegramQuiz
from typing import List
import sys


def _parse_args(args: List[str]):
    parser = argparse.ArgumentParser(
        description='Application for hosting a quiz.')
    parser.add_argument('--log-file', default='main.log')
    parser.add_argument('--quizzes-db', default='quizzes.db')
    parser.add_argument('--quiz-id', required=True)
    parser.add_argument('--telegram-bot-token', required=True)
    parser.add_argument('--number-of-questions', default=30)
    parser.add_argument('--strings-file', default='strings.json')
    parser.add_argument('--language', default='uk')
    return parser.parse_args()


def _create_logger(*, name: str, log_file: str):
    logger = logging.getLogger(name)
    logger_handler = logging.FileHandler(log_file)
    logger_formatter = logging.Formatter(
        '%(asctime)s: %(process)s: %(levelname)s: %(filename)s:%(lineno)d - %(message)s')
    logger_handler.setFormatter(logger_formatter)
    logger.addHandler(logger_handler)
    logger.setLevel(logging.INFO)
    return logger


def main(args: List[str]):
    args = _parse_args(args)

    logger = _create_logger(name='quiz_telegram_bot', log_file=args.log_file)
    logger.info('')
    logger.info('Hello!')

    quizzes_db = QuizzesDb(db_path=args.quizzes_db)

    quiz = TelegramQuiz(id=args.quiz_id, bot_token=args.telegram_bot_token,
                        number_of_questions=args.number_of_questions,
                        quizzes_db=quizzes_db, strings_file=args.strings_file,
                        language=args.language, logger=logger)

    server = QuizHttpServer(host='localhost', port=8000,
                            quiz=quiz, logger=logger)

    quiz.start()
    server.serve_forever()


if __name__ == "__main__":
    main(sys.argv)
