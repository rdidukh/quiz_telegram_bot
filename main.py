import argparse
import logging
import quiz_http_server
from quiz_db import QuizDb
from telegram_quiz import TelegramQuiz
import tornado
from typing import List
import sys


def _parse_args(args: List[str]):
    parser = argparse.ArgumentParser(
        description='Application for hosting a quiz.')
    parser.add_argument('--log-file', default='main.log')
    parser.add_argument('--quiz-db', default='quiz.db')
    parser.add_argument('--quiz-id', required=True)
    parser.add_argument('--telegram-bot-token', required=True)
    parser.add_argument('--strings-file', default='strings.json')
    parser.add_argument('--language', default='uk')
    return parser.parse_args()


def main(args: List[str]):
    args = _parse_args(args)

    log_format = '%(asctime)s: %(process)s: %(levelname)s: %(filename)s:%(lineno)d - %(message)s'
    logging.basicConfig(filename=args.log_file,
                        format=log_format, level=logging.INFO)

    logging.info('')
    logging.info('Hello!')

    quiz_db = QuizDb(db_path=args.quiz_db)

    quiz = TelegramQuiz(quiz_db=quiz_db, strings_file=args.strings_file)
    quiz.start(quiz_id=args.quiz_id, bot_api_token=args.telegram_bot_token, language=args.language)

    app = quiz_http_server.create_quiz_tornado_app(quiz=quiz)
    app.listen(8000)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main(sys.argv)
