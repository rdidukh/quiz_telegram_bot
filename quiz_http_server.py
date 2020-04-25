import functools
import json
import logging
from telegram_quiz import TelegramQuiz, TelegramQuizError
import threading
import tornado.httpserver
import tornado.ioloop
import tornado.netutil
import tornado.web
from typing import Any, Dict, Optional, Tuple, Type, Union


class RequestParameterError(Exception):
    pass


class RootHandler(tornado.web.RequestHandler):
    def get(self):
        self.redirect('/index.html')


class BaseQuizRequestHandler(tornado.web.RequestHandler):
    def initialize(self, quiz: TelegramQuiz):
        self.quiz = quiz

    def get_param_value(self,
                        request: Dict[str, Any],
                        param: str,
                        param_type: Union[Type, Tuple[Type, ...]],
                        default: Optional[Any] = None) -> Any:

        if not isinstance(param_type, tuple):
            param_type = (param_type,)

        if param not in request:
            if default is None:
                raise RequestParameterError(
                    f'Parameter {param} must be provided.')
            return default
        value = request[param]
        if not isinstance(value, param_type):
            str_types = ' or '.join((t.__name__ for t in param_type))
            raise RequestParameterError(
                f'Parameter {param} must be of type {str_types}.')
        return value

    async def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    async def post(self):
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
            response = await self.handle_quiz_request(request)
            status_code = 400 if response.get('error') else 200
        except (RequestParameterError, TelegramQuizError) as e:
            response = {'error': str(e)}
            status_code = 400
        except Exception:
            logging.exception('Internal server error')
            response = {'error': 'Internal server error'}
            status_code = 501

        self.set_status(status_code)
        self.add_header('Content-Type', 'application/json')
        self.write(json.dumps(response))


class GetUpdatesApiHandler(BaseQuizRequestHandler):

    def _wait(self, *, timeout: float) -> bool:
        with self.cond:
            return self.cond.wait(timeout=timeout)

    def _notify(self):
        with self.cond:
            self.cond.notify()

    def _get_updates(self, min_status_update_id: int, min_teams_update_id: int, min_answers_update_id: int) -> Dict[str, Any]:
        if self.quiz.status_update_id >= min_status_update_id:
            status = self.quiz.get_status()
        else:
            status = None
        teams = self.quiz.quiz_db.get_teams(
            quiz_id=self.quiz.id, min_update_id=min_teams_update_id)
        answers = self.quiz.quiz_db.get_answers(
            quiz_id=self.quiz.id, min_update_id=min_answers_update_id)

        return {
            'status': status.__dict__ if status else None,
            'teams': [t.__dict__ for t in teams],
            'answers': [a.__dict__ for a in answers],
        }

    def _updates_empty(self, updates: Dict[str, Any]) -> bool:
        return not updates.get('status') and not updates.get('teams') and not updates.get('answers')

    async def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        min_status_update_id = self.get_param_value(
            request, 'min_status_update_id', int)
        min_teams_update_id = self.get_param_value(
            request, 'min_teams_update_id', int)
        min_answers_update_id = self.get_param_value(
            request, 'min_answers_update_id', int)
        timeout = self.get_param_value(request, 'timeout', (float, int), 0.0)
        timeout = min(timeout, 30.0)

        updates = self._get_updates(
            min_status_update_id, min_teams_update_id, min_answers_update_id)
        if not self._updates_empty(updates) or timeout <= 0:
            return updates

        self.cond = threading.Condition()

        try:
            self.quiz.add_updates_subscriber(self._notify)
            self.quiz.quiz_db.add_updates_subscriber(self._notify)

            await tornado.ioloop.IOLoop.current().run_in_executor(None,
                                                                  functools.partial(self._wait, timeout=timeout))

            updates = self._get_updates(
                min_status_update_id, min_teams_update_id, min_answers_update_id)

            return updates
        finally:
            self.quiz.remove_updates_subscriber(self._notify)
            self.quiz.quiz_db.remove_updates_subscriber(self._notify)

    def on_connection_close(self):
        logging.warning('Connection closed by the client.')
        self._notify()


class SendResultsApiHandler(BaseQuizRequestHandler):
    async def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        team_id = self.get_param_value(request, 'team_id', int)
        self.quiz.send_results(team_id=team_id)
        return {}


class SetAnswerPointsApiHandler(BaseQuizRequestHandler):
    async def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        question = self.get_param_value(request, 'question', int)
        team_id = self.get_param_value(request, 'team_id', int)
        points = self.get_param_value(request, 'points', int)

        update_id = self.quiz.quiz_db.set_answer_points(
            quiz_id=self.quiz.id,
            question=question,
            team_id=team_id,
            points=points)

        if not update_id:
            return {'error': f'Answer for quiz "{self.quiz.id}", question {question}, team {team_id} does not exist.'}

        return {}


class StartRegistrationApiHandler(BaseQuizRequestHandler):
    async def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        self.quiz.start_registration()
        return {}


class StopRegistrationApiHandler(BaseQuizRequestHandler):
    async def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        self.quiz.stop_registration()
        return {}


class StartQuestionApiHandler(BaseQuizRequestHandler):
    async def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        question = request.get('question')
        if question is None:
            return {'error': 'Parameter question was not provided.'}
        if not isinstance(question, int):
            return {'error': 'Parameter question must be integer.'}
        self.quiz.start_question(question=question)
        return {}


class StopQuestionApiHandler(BaseQuizRequestHandler):
    async def handle_quiz_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        self.quiz.stop_question()
        return {}


def create_quiz_tornado_app(*, quiz: TelegramQuiz) -> tornado.web.Application:
    args = dict(quiz=quiz)
    return tornado.web.Application([
        ('/', RootHandler),
        ('/api/getUpdates', GetUpdatesApiHandler, args),
        ('/api/sendResults', SendResultsApiHandler, args),
        ('/api/setAnswerPoints', SetAnswerPointsApiHandler, args),
        ('/api/startRegistration', StartRegistrationApiHandler, args),
        ('/api/stopRegistration', StopRegistrationApiHandler, args),
        ('/api/startQuestion', StartQuestionApiHandler, args),
        ('/api/stopQuestion', StopQuestionApiHandler, args),
        ('/(.*)', tornado.web.StaticFileHandler, {'path': 'static'}),
    ])
