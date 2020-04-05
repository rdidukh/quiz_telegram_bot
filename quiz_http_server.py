import http.server
import json
import logging
from typing import Any, Dict


class QuizHttpRequestHandler(http.server.BaseHTTPRequestHandler):
    def _do_post(self, server: 'QuizHttpServer') -> Dict[str, Any]:
        length = int(self.headers.get('Content-Length'))
        data = self.rfile.read(length)
        request = json.loads(data, encoding='utf-8')
        server.logger.info(f'request: {request}')

        return {'ok': True}

    def do_POST(self):
        server: QuizHttpServer = self.server
        try:
            response = self._do_post(server)
            status_code = 200
        except Exception:
            server.logger.exception('_do_post error')
            response = {'ok': False, 'error': 'Internal server error'}
            status_code = 501
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format: str, *args):
        server: QuizHttpServer = self.server
        server.logger.info(format % tuple(args))


class QuizHttpServer(http.server.HTTPServer):
    def __init__(self, *, host: str, port: int, logger: logging.Logger):
        super().__init__((host, port), QuizHttpRequestHandler)
        self.logger = logger
