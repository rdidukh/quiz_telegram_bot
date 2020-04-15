import contextlib
from datetime import datetime
from dataclasses import dataclass, field
import sqlite3
from typing import List, Optional


@dataclass
class Message:
    timestamp: int
    update_id: int
    chat_id: int
    text: str
    insert_timestamp: int = field(default=0, compare=False)


@dataclass(order=True)
class Answer:
    quiz_id: str
    question: int
    team_id: int
    answer: str
    timestamp: int
    checked: bool = field(default=False)
    points: int = field(default=0)
    id: int = field(default=None, compare=False)


@dataclass(order=True)
class Team:
    quiz_id: str
    id: int
    name: str
    timestamp: int


class QuizDb:
    def __init__(self, *, db_path: str):
        self.db_path = db_path
        self.create_if_not_exists()

    def get_answers(self, quiz_id: str, *, id_greater_than: int = 0) -> List[Answer]:
        answers: List[Answer] = []
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                cursor = db.execute(
                    'SELECT rowid, quiz_id, question, team_id, answer, MAX(timestamp), checked, points FROM answers '
                    'WHERE quiz_id = ? AND rowid > ? GROUP BY quiz_id, question, team_id', (quiz_id, id_greater_than))

                for (id, quiz_id, question, team_id, answer, timestamp, checked, points) in cursor:
                    answers.append(Answer(id=id,
                                          quiz_id=quiz_id,
                                          question=question,
                                          team_id=team_id,
                                          answer=answer,
                                          timestamp=timestamp,
                                          checked=bool(checked),
                                          points=points))
        return answers

    def insert_answer(self, answer: Answer):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                a = answer
                db.execute('INSERT INTO answers (quiz_id, question, team_id, answer, timestamp, checked, points) '
                           'VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (a.quiz_id, a.question, a.team_id, a.answer, a.timestamp, a.checked, a.points))

    def insert_message(self, message: Message):
        insert_timestamp = message.insert_timestamp or int(
            datetime.utcnow().timestamp())
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''INSERT INTO messages
                           (insert_timestamp, timestamp, update_id, chat_id, text)
                           VALUES (?, ?, ?, ?, ?)''',
                           (insert_timestamp, message.timestamp, message.update_id, message.chat_id, message.text))

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

    def insert_team(self, team: Team) -> None:
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''INSERT INTO teams
                     (quiz_id, id, name, timestamp)
                     VALUES (?, ?, ?, ?)''', (team.quiz_id, team.id, team.name, team.timestamp))

    def get_teams_for_quiz(self, quiz_id: str) -> List[Team]:
        teams: List[Team] = []
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                cursor = db.execute('SELECT quiz_id, id, name, MAX(timestamp) '
                                    'FROM teams WHERE quiz_id = ? GROUP BY id', (quiz_id,))
                for (quiz_id, id, name, timestamp) in cursor:
                    teams.append(Team(
                        quiz_id=quiz_id,
                        id=id,
                        name=name,
                        timestamp=timestamp
                    ))
        return teams

    def get_team(self, *, quiz_id: str, team_id: int) -> Optional[Team]:
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                cursor = db.execute('SELECT quiz_id, id, name, MAX(timestamp) '
                                    'FROM teams WHERE quiz_id = ? AND id = ? '
                                    'GROUP BY quiz_id, id', (quiz_id, team_id))
                row = cursor.fetchone()
                if not row:
                    return None
                (quiz_id, id, name, timestamp) = row
                return Team(quiz_id=quiz_id, id=id, name=name, timestamp=timestamp)

    def create_if_not_exists(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''CREATE TABLE IF NOT EXISTS teams (
                    quiz_id TEXT NOT NULL,
                    id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    timestamp INTEGER NOT NULL)''')
                db.execute('''CREATE TABLE IF NOT EXISTS answers (
                    quiz_id TEXT NOT NULL,
                    question INT NOT NULL,
                    team_id INTEGER NOT NULL,
                    answer TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    checked INTEGER NOT NULL DEFAULT 0,
                    points INTEGER NOT NULL DEFAULT 0)''')
                db.execute('''CREATE TABLE IF NOT EXISTS messages (
                    insert_timestamp INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    update_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    text TEXT NOT NULL)''')
