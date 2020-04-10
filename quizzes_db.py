import contextlib
from datetime import datetime
from dataclasses import dataclass, field
import sqlite3
from typing import Dict, List


@dataclass
class Message:
    timestamp: int
    update_id: int
    chat_id: int
    text: str
    insert_timestamp: int = field(default=0, compare=False)


class QuizzesDb:
    def __init__(self, *, db_path: str):
        self.db_path = db_path
        self.create_if_not_exists()

    def insert_team(self, *, chat_id: int, quiz_id: str, name: str, timestamp: int):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''INSERT INTO teams
                     (timestamp, chat_id, quiz_id, name)
                     VALUES (?, ?, ?, ?)''', (timestamp, chat_id, quiz_id, name))

    def insert_answer(self, *,
                      chat_id: int,
                      quiz_id: str,
                      question_id: str,
                      team_name: str,
                      answer: str,
                      timestamp: int):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''INSERT INTO answers
                     (timestamp, chat_id, quiz_id, question_id, team_name, answer)
                     VALUES (?, ?, ?, ?, ?, ?)''', (timestamp, chat_id, quiz_id, question_id, team_name, answer))

    def insert_message(self, message: Message):
        insert_timestamp = message.insert_timestamp or int(
            datetime.utcnow().timestamp())
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''INSERT INTO messages
                           (insert_timestamp, timestamp, update_id, chat_id, text)
                           VALUES (?, ?, ?, ?, ?)''',
                           (insert_timestamp, message.timestamp, message.update_id, message.chat_id, message.text))

    def select_teams(self, *, quiz_id: str) -> Dict[int, str]:
        teams: Dict[int, str] = {}
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                cursor = db.execute('SELECT MAX(timestamp), chat_id, name '
                                    'FROM teams WHERE quiz_id = ? GROUP BY chat_id', (quiz_id,))
                for (_, chat_id, name) in cursor:
                    teams[chat_id] = name
        return teams

    def select_all_answers(self, *, quiz_id: str) -> Dict[str, Dict[int, str]]:
        answers: Dict[str, Dict[int, str]] = {}
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                cursor = db.execute('SELECT MAX(timestamp), chat_id, question_id, answer '
                                    'FROM answers WHERE quiz_id = ? GROUP BY chat_id, question_id', (quiz_id,))
                for (_, chat_id, question_id, answer) in cursor:
                    if question_id not in answers:
                        answers[question_id] = {}
                    answers[question_id][chat_id] = answer
        return answers

    def select_messages(self) -> List[Message]:
        messages: List[Message] = []
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            db.row_factory = sqlite3.Row
            with db:
                cursor = db.execute(
                    'SELECT insert_timestamp, timestamp, update_id, chat_id, text FROM messages')
                for row in cursor:
                    message = Message(insert_timestamp=row['insert_timestamp'],
                                      timestamp=row['timestamp'],
                                      update_id=row['update_id'],
                                      chat_id=row['chat_id'],
                                      text=row['text'])
                    messages.append(message)
        return messages

    def create_if_not_exists(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''CREATE TABLE IF NOT EXISTS teams (
                    timestamp INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    quiz_id TEXT NOT NULL,
                    name TEXT NOT NULL)''')
                db.execute('''CREATE TABLE IF NOT EXISTS answers (
                    timestamp INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    quiz_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    answer TEXT NOT NULL)''')
                db.execute('''CREATE TABLE IF NOT EXISTS messages (
                    insert_timestamp INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    update_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    text TEXT NOT NULL)''')
