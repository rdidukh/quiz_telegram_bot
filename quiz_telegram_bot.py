import argparse
import logging
from quiz_http_server import QuizHttpServer
from quizzes_db import QuizzesDb
import telegram
from telegram_quiz import TelegramQuiz
from typing import List
import sys


def _parse_args(args: List[str]):
    parser = argparse.ArgumentParser(
        description='Application for hosting a quiz.')
    parser.add_argument('--log_file', default='quiz_telegram_bot.log')
    parser.add_argument('--quizzes_db', default='quizzes.db')
    parser.add_argument('--game_id', default='default')
    parser.add_argument('--telegram_bot_token', default='', required=True)
    parser.add_argument('--warmup_questions', default=2)
    parser.add_argument('--questions', default=30)
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

    updater = telegram.ext.Updater(args.telegram_bot_token, use_context=True)
    updater.dispatcher.add_error_handler(
        lambda update, context: logger.error('Update "%s" caused error "%s"', update, context.error))

    quizzes_db = QuizzesDb(db_path=args.quizzes_db)

    question_set = {f'{i:02}' for i in range(1, args.questions + 1)}
    question_set = question_set.union(
        {f'{i:02}' for i in range(-args.warmup_questions, 0)})

    logger.info(f'Question set: {question_set}')

    quiz = TelegramQuiz(id=args.game_id, updater=updater, question_set=question_set,
                        quizzes_db=quizzes_db, handler_group=1, logger=logger)

    updater.dispatcher.add_handler(telegram.ext.MessageHandler(
        telegram.ext.Filters.text, quiz._handle_log_update))

    updater.start_polling()

    server = QuizHttpServer(host='localhost', port=8000,
                            quiz=quiz, logger=logger)
    server.serve_forever()
    updater.stop()


if __name__ == "__main__":
    main(sys.argv)
