import logging
from quiz_http_server import QuizHttpServer
import threading
import requests
import unittest


class TestQuizHttpServer(unittest.TestCase):
    def test_http_server(self):
        logger = logging.Logger('test')
        logger.addHandler(logging.NullHandler())
        server = QuizHttpServer(host='localhost', port=0, logger=logger)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        url = f'http://localhost:{server.server_port}/'

        response = requests.post(url, json={})

        self.assertEqual(200, response.status_code)
        self.assertDictEqual({
            'ok': True,
        }, response.json())

        server.shutdown()
        thread.join(timeout=5.0)
        server.server_close()


if __name__ == '__main__':
    unittest.main()
