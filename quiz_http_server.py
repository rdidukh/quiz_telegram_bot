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
            if self.request.body:
                request = json.loads(self.request.body, encoding='utf-8')
            else:
                request = {}
        except json.JSONDecodeError:
            self.set_status(400)
            self.write(json.dumps(
                {'error': 'Request is not a valid JSON object.'}))
            return

        try:
            response = self.handle_quiz_request(request)
            status_code = 400 if response.get('error') else 200
        except TelegramQuizError as e:
            response = {'error': str(e)}
            status_code = 400
        except Exception:
            logging.exception('Internal server error')
            response = {'error': 'Internal server error'}
            status_code = 501

        self.set_status(status_code)
        self.add_header('Content-Type', 'application/json')
        self.write(json.dumps(response))


class RootHandler(tornado.web.RequestHandler):
    def get(self):
        self.redirect('/index.html')


class StartRegistrationApiHandler(BaseQuizRequestHandler):
    def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        self.quiz.start_registration()
        return {}


class StopRegistrationApiHandler(BaseQuizRequestHandler):
    def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        self.quiz.stop_registration()
        return {}


class StartQuestionApiHandler(BaseQuizRequestHandler):
    def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        question_id = request.get('question_id')
        if not question_id:
            return {'ok': False, 'error': 'Question not provided.'}
        self.quiz.start_question(question_id=question_id)
        return {}


class StopQuestionApiHandler(BaseQuizRequestHandler):
    def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        self.quiz.stop_question()
        return {}


class GetStatusApiHandler(BaseQuizRequestHandler):
    def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'quiz_id': self.quiz.id,
            'teams': self.quiz.teams,
            'answers': self.quiz.answers,
            'question_set': sorted(list(self.quiz.question_set)),
            "number_of_questions": self.quiz.number_of_questions,
            "language": self.quiz.language,
            'question_id': self.quiz.question_id,
            'is_registration': self.quiz.is_registration()
        }


def create_quiz_tornado_app(*, quiz: TelegramQuiz) -> tornado.web.Application:
    return tornado.web.Application([
        ('/', RootHandler),
        ('/api/startRegistration', StartRegistrationApiHandler, dict(quiz=quiz)),
        ('/api/stopRegistration', StopRegistrationApiHandler, dict(quiz=quiz)),
        ('/api/startQuestion', StartQuestionApiHandler, dict(quiz=quiz)),
        ('/api/stopQuestion', StopQuestionApiHandler, dict(quiz=quiz)),
        ('/api/getStatus', GetStatusApiHandler, dict(quiz=quiz)),
        ('/(.*)', tornado.web.StaticFileHandler, {'path': 'static'}),
    ])
