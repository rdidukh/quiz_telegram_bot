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
    update_id: int = field(default=None, compare=False)


@dataclass(order=True)
class Team:
    quiz_id: str
    id: int
    name: str
    timestamp: int
    update_id: int = field(default=None, compare=False)


class QuizDb:
    def __init__(self, *, db_path: str):
        self.db_path = db_path
        self.create_if_not_exists()

    def get_answers(self, quiz_id: str, *, update_id_greater_than: int = 0) -> List[Answer]:
        answers: List[Answer] = []
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                cursor = db.execute(
                    'SELECT update_id, quiz_id, question, team_id, answer, timestamp FROM answers '
                    'WHERE quiz_id = ? AND update_id > ?',
                    (quiz_id, update_id_greater_than))

                for (update_id, quiz_id, question, team_id, answer, timestamp) in cursor:
                    answers.append(Answer(update_id=update_id,
                                          quiz_id=quiz_id,
                                          question=question,
                                          team_id=team_id,
                                          answer=answer,
                                          timestamp=timestamp))
        return answers

    def update_answer(self, *, quiz_id: str, question: int, team_id: int, answer: str, answer_time: int) -> int:
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                (timestamp,) = db.execute('SELECT timestamp '
                                          'FROM answers '
                                          'WHERE quiz_id = ? AND question = ? AND team_id = ?',
                                          (quiz_id, question, team_id)).fetchone() or (0,)

                if timestamp > answer_time:
                    return 0

                update_id = self._increment_update_id_counter(db)

                if timestamp:
                    db.execute('UPDATE answers '
                               'SET update_id = ?, answer = ?, timestamp = ? '
                               'WHERE quiz_id = ? AND question = ? AND team_id = ?',
                               (update_id, answer, answer_time, quiz_id, question, team_id))
                else:
                    db.execute('INSERT INTO answers (update_id, quiz_id, question, team_id, answer, timestamp) '
                               'VALUES (?, ?, ?, ?, ?, ?)',
                               (update_id, quiz_id, question, team_id, answer, answer_time))

                return update_id

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

    def update_team(self, quiz_id: str, team_id: int, name: str, registration_time: int) -> int:
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                (timestamp,) = db.execute('SELECT timestamp FROM teams WHERE quiz_id = ? AND id = ?',
                                          (quiz_id, team_id)).fetchone() or (0,)
                if timestamp > registration_time:
                    return 0
                update_id = self._increment_update_id_counter(db)

                if timestamp:
                    db.execute('UPDATE teams SET update_id = ?, name = ?, timestamp = ? WHERE quiz_id = ? AND id = ?',
                               (update_id, name, registration_time, quiz_id, team_id))
                else:
                    db.execute('INSERT INTO teams'
                               '(update_id, quiz_id, id, name, timestamp)'
                               'VALUES (?, ?, ?, ?, ?)',
                               (update_id, quiz_id, team_id, name, registration_time))
                return update_id

    def get_teams(self, *, quiz_id: str, team_id: Optional[int] = None, update_id_greater_than: int = 0) -> List[Team]:
        conditions = []
        params = []

        if quiz_id:
            conditions.append('quiz_id = ?')
            params.append(quiz_id)

        if update_id_greater_than:
            conditions.append('update_id > ?')
            params.append(update_id_greater_than)

        if team_id is not None:
            conditions.append('id = ?')
            params.append(team_id)

        condition = 'WHERE ' + ' AND '.join(conditions) if conditions else ''

        teams: List[Team] = []
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                cursor = db.execute('SELECT update_id, quiz_id, id, name, timestamp '
                                    f'FROM teams {condition} '
                                    'GROUP BY id', params)
                for (update_id, quiz_id, id, name, timestamp) in cursor:
                    teams.append(Team(
                        update_id=update_id,
                        quiz_id=quiz_id,
                        id=id,
                        name=name,
                        timestamp=timestamp
                    ))
        return teams

    def _increment_update_id_counter(self, db: sqlite3.Connection) -> int:
        (update_id,) = db.execute('SELECT next_update_id FROM counters').fetchone()
        db.execute('UPDATE counters SET next_update_id = next_update_id + 1')
        return update_id

    def create_if_not_exists(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''CREATE TABLE IF NOT EXISTS teams (
                    update_id INT NOT NULL,
                    quiz_id TEXT NOT NULL,
                    id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    UNIQUE(quiz_id, id))''')
                db.execute('''CREATE TABLE IF NOT EXISTS answers (
                    update_id INTEGER NOT NULL,
                    quiz_id TEXT NOT NULL,
                    question INT NOT NULL,
                    team_id INTEGER NOT NULL,
                    answer TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    UNIQUE(quiz_id, question, team_id))''')
                db.execute('''CREATE TABLE IF NOT EXISTS messages (
                    insert_timestamp INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    update_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    text TEXT NOT NULL)''')
                db.execute('''CREATE TABLE IF NOT EXISTS counters (
                    next_update_id INTEGER
                )''')
                db.execute(
                    'INSERT OR IGNORE INTO counters (rowid, next_update_id) VALUES (1, 1)')
