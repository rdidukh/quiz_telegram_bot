import argparse
import logging
from quiz_http_server import QuizHttpServer
from stateful_telegram_bot import StatefulTelegramBot
import sys
from typing import List


def _parse_args(args: List[str]):
    parser = argparse.ArgumentParser(
        description='Application for hosting a quiz.')
    parser.add_argument('--log_file', default='quiz_telegram_bot.log')
    parser.add_argument('--message_db', default='message.db')
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

    logger.info('Launching Telegram bot...')
    bot = StatefulTelegramBot(token=args.telegram_bot_token,
                              logger=logger, db_path=args.message_db)
    bot.init_from_db()
    bot.start_polling()
    logger.info('Launching Telegram bot done.')

    logger.info('Starting HTTP server...')
    server = QuizHttpServer(host='localhost', port=8000, logger=logger)
    server.serve_forever()


if __name__ == "__main__":
    main(sys.argv)
