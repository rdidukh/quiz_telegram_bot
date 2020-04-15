import json
import logging
from telegram_quiz import TelegramQuiz, TelegramQuizError
import tornado.httpserver
import tornado.ioloop
import tornado.netutil
import tornado.web
from typing import Any, Dict


class BaseQuizRequestHandler(tornado.web.RequestHandler):
    def initialize(self, quiz: TelegramQuiz):
        self.quiz = quiz

    def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def post(self):
        try:
            request = json.loads(self.request.body, encoding='utf-8')
        except json.JSONDecodeError:
            self.set_status(400)
            self.write(json.dumps(
                {'ok': False, 'error': 'Request is not a valid JSON object.'}))
            return

        try:
            response = self.handle_quiz_request(request)
            if response.get('ok'):
                status_code = 200
            else:
                status_code = 400
        except TelegramQuizError as e:
            response = {'ok': False, 'error': str(e)}
            status_code = 400
        except Exception:
            logging.exception('Internal server error')
            response = {'ok': False, 'error': 'Internal server error'}
            status_code = 501

        self.set_status(status_code)
        self.add_header('Content-Type', 'application/json')
        self.write(json.dumps(response))


class RootHandler(BaseQuizRequestHandler):

    def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        command = request.get('command')

        if command == 'start_registration':
            self.quiz.start_registration()
        elif command == 'stop_registration':
            self.quiz.stop_registration()
        elif command == 'start_question':
            question_id = request.get('question_id')
            if not question_id:
                return {'ok': False, 'error': 'question_id for command start_question not provided.'}
            self.quiz.start_question(question_id=question_id)
        elif command == 'stop_question':
            self.quiz.stop_question()
        elif command == 'get_status':
            return {
                'ok': True,
                'quiz_id': self.quiz.id,
                'teams': self.quiz.teams,
                'answers': self.quiz.answers,
                'question_set': sorted(list(self.quiz.question_set)),
                "number_of_questions": self.quiz.number_of_questions,
                "language": self.quiz.language,
                'question_id': self.quiz.question_id,
                'is_registration': self.quiz.is_registration()
            }
        else:
            return {'ok': False, 'error': 'Command was not provided'}

        return {'ok': True}

    def get(self):
        self.redirect('/index.html')


def create_quiz_tornado_app(*, quiz: TelegramQuiz) -> tornado.web.Application:
    return tornado.web.Application([
        ('/', RootHandler, dict(quiz=quiz)),
        ('/(.*)', tornado.web.StaticFileHandler, {'path': 'static'}),
    ])
