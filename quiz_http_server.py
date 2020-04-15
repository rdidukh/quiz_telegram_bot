import json
import logging
from telegram_quiz import TelegramQuiz, TelegramQuizError
import tornado.httpserver
import tornado.ioloop
import tornado.netutil
import tornado.web
from typing import Any, Dict


class RootHandler(tornado.web.RequestHandler):
    def get(self):
        self.redirect('/index.html')


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


class GetAnswersApiHandler(BaseQuizRequestHandler):
    def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        id_greater_than = request.get('id_greater_than')
        if id_greater_than is None:
            return {'error': 'Parameter id_greater_than was not provided.'}
        answers = self.quiz.quiz_db.get_answers(
            quiz_id=self.quiz.id, id_greater_than=id_greater_than)
        return {"answers": [a.__dict__ for a in answers]}


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
            return {'error': 'Question not provided.'}
        self.quiz.start_question(question_id=question_id)
        return {}


class StopQuestionApiHandler(BaseQuizRequestHandler):
    def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        self.quiz.stop_question()
        return {}


def create_quiz_tornado_app(*, quiz: TelegramQuiz) -> tornado.web.Application:
    args = dict(quiz=quiz)
    return tornado.web.Application([
        ('/', RootHandler),
        ('/api/getAnswers', GetAnswersApiHandler, args),
        ('/api/getStatus', GetStatusApiHandler, args),
        ('/api/startRegistration', StartRegistrationApiHandler, args),
        ('/api/stopRegistration', StopRegistrationApiHandler, args),
        ('/api/startQuestion', StartQuestionApiHandler, args),
        ('/api/stopQuestion', StopQuestionApiHandler, args),
        ('/(.*)', tornado.web.StaticFileHandler, {'path': 'static'}),
    ])
