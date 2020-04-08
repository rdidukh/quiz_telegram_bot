import argparse
import logging
from messages_db import MessagesDb
from quizzes_db import QuizzesDb
from telegram_update_logger import TelegramUpdateLogger
import telegram
from telegram_quiz import TelegramQuiz
from typing import List
import sys


def _parse_args(args: List[str]):
    parser = argparse.ArgumentParser(
        description='Application for hosting a quiz.')
    parser.add_argument('--log_file', default='quiz_telegram_bot.log')
    parser.add_argument('--messages_db', default='messages.db')
    parser.add_argument('--quizzes_db', default='quizzes.db')
    parser.add_argument('--game_id', default='default')
    parser.add_argument('--telegram_bot_token', default='', required=True)
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

    messages_db = MessagesDb(db_path=args.messages_db)

    logger.info('Launching Telegram bot...')
    telegram_update_logger = TelegramUpdateLogger(messages_db=messages_db, logger=logger)
    updater = telegram.ext.Updater(args.telegram_bot_token, use_context=True)
    updater.dispatcher.add_handler(telegram.ext.MessageHandler(telegram.ext.Filters.text, telegram_update_logger.log_update))
    updater.dispatcher.add_error_handler(
        lambda update, context: logger.error('Update "%s" caused error "%s"', update, context.error))
    updater.start_polling()
    logger.info('Launching Telegram bot done.')

    quizzes_db = QuizzesDb(db_path=args.quizzes_db)

    quiz = TelegramQuiz(id=args.game_id, updater=updater, quizzes_db=quizzes_db, handler_group=1, logger=logger)

    quiz.start_registration()

    updater.idle()


if __name__ == "__main__":
    main(sys.argv)
