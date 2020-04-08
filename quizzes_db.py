import contextlib
from datetime import datetime
import sqlite3
from typing import Dict


class QuizzesDb:
    def __init__(self, *, db_path: str):
        self.db_path = db_path
        self.create_if_not_exists()

    def insert_team(self, *, chat_id: int, quiz_id: str, name: str, timestamp=None):
        timestamp = timestamp or int(datetime.utcnow().timestamp())
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''INSERT INTO teams
                     (timestamp, chat_id, quiz_id, name)
                     VALUES (?, ?, ?, ?)''', (timestamp, chat_id, quiz_id, name))

    def select_teams(self, *, quiz_id: str) -> Dict[int, str]:
        teams: Dict[int, str] = {}
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                cursor = db.execute('SELECT MAX(timestamp), chat_id, name '
                                    'FROM teams WHERE quiz_id = ? GROUP BY chat_id', (quiz_id,))
                for (_, chat_id, name) in cursor:
                    teams[chat_id] = name
        return teams

    def create_if_not_exists(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''CREATE TABLE IF NOT EXISTS teams (
                    timestamp INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    quiz_id TEXT NOT NULL,
                    name TEXT NOT NULL)''')
