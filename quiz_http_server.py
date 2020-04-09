import http.server
import json
import logging
from telegram_quiz import TelegramQuiz, TelegramQuizError
from typing import Any, Dict


class QuizHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def _do_post(self, server: 'QuizHttpServer') -> Dict[str, Any]:
        length = int(self.headers.get('Content-Length'))
        data = self.rfile.read(length)
        try:
            request = json.loads(data, encoding='utf-8')
        except json.JSONDecodeError as e:
            server.logger.warning(f'Request parsing error: {e}')
            return {'ok': False, 'error': 'Request is not a valid JSON object.'}

        server.logger.info(f'request: {request}')

        command = request.get('command')

        if command == 'start_registration':
            server.quiz.start_registration()
        elif command == 'stop_registration':
            server.quiz.stop_registration()
        elif command == 'start_question':
            question_id = request.get('question_id')
            if not question_id:
                return {'ok': False, 'error': 'question_id for command start_question not provided.'}
            server.quiz.start_question(question_id=question_id)
        elif command == 'stop_question':
            server.quiz.stop_question()
        elif command == 'get_status':
            return {
                'ok': True,
                'quiz_id': server.quiz.id,
                'teams': server.quiz.teams,
                'answers': server.quiz.answers,
                'question_set': sorted(list(server.quiz.question_set)),
                'question_id': server.quiz.question_id,
                'is_registration': server.quiz.is_registration()
            }
        else:
            server.logger.warning(f'Request without command: {request}.')
            return {'ok': False, 'error': 'Command was not provided'}

        return {'ok': True}

    def do_POST(self):
        server: QuizHttpServer = self.server
        try:
            response = self._do_post(server)
            if response.get('ok'):
                status_code = 200
            else:
                status_code = 400
        except TelegramQuizError as e:
            server.logger.warning(f'quiz error: {e}')
            response = {'ok': False, 'error': str(e)}
            status_code = 400
        except Exception:
            server.logger.exception('_do_post error')
            response = {'ok': False, 'error': 'Internal server error'}
            status_code = 501
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format: str, *args):
        server: QuizHttpServer = self.server
        server.logger.info(format % tuple(args))


class QuizHttpServer(http.server.HTTPServer):
    def __init__(self, *, host: str, port: int, quiz: TelegramQuiz, logger: logging.Logger):
        super().__init__((host, port), QuizHttpRequestHandler)
        self.quiz = quiz
        self.logger = logger
