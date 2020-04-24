import contextlib
from datetime import datetime
from dataclasses import dataclass, field
import logging
import sqlite3
import threading
from typing import Callable, List, Tuple, Optional, Set


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
    points: Optional[int] = field(default=None)
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
        self._lock = threading.Lock()
        self._db_lock = threading.Lock()
        self.create_if_not_exists()
        self._subscribers: Set[Callable[[], None]] = set()

    def _on_update(self):
        for sub in self._subscribers:
            try:
                sub()
            except Exception:
                logging.exception('Subscriber raised an error.')

    def add_updates_subscriber(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._subscribers.add(callback)

    def remove_updates_subscriber(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._subscribers.remove(callback)

    def get_answers(self, quiz_id: str, *, min_update_id: int = 0) -> List[Answer]:
        answers: List[Answer] = []
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                cursor = db.execute(
                    'SELECT update_id, quiz_id, question, team_id, answer, timestamp, points FROM answers '
                    'WHERE quiz_id = ? AND update_id >= ?',
                    (quiz_id, min_update_id))

                for (update_id, quiz_id, question, team_id, answer, timestamp, points) in cursor:
                    answers.append(Answer(update_id=update_id,
                                          quiz_id=quiz_id,
                                          question=question,
                                          team_id=team_id,
                                          answer=answer,
                                          timestamp=timestamp,
                                          points=points))
        return answers

    def _select_answer(self, *, db: sqlite3.Connection, quiz_id: str, question: int, team_id: int) -> Tuple[int, int]:
        return db.execute('SELECT update_id, timestamp '
                          'FROM answers '
                          'WHERE quiz_id = ? AND question = ? AND team_id = ?',
                          (quiz_id, question, team_id)).fetchone() or (0, 0)

    def _get_next_answer_update_id(self, db: sqlite3.Connection) -> int:
        (update_id,) = db.execute('SELECT MAX(update_id) FROM answers').fetchone()
        return update_id + 1 if update_id else 1

    def update_answer(self, *, quiz_id: str, question: int, team_id: int, answer: str, answer_time: int) -> int:
        with self._db_lock, contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                (update_id, timestamp,) = self._select_answer(
                    db=db, quiz_id=quiz_id, question=question, team_id=team_id)

                # Don't update the answer if it's older than the current one.
                if timestamp > answer_time:
                    return 0

                new_update_id = self._get_next_answer_update_id(db)

                if update_id:
                    db.execute('UPDATE answers '
                               'SET update_id = ?, answer = ?, timestamp = ?, points = NULL '
                               'WHERE update_id = ?',
                               (new_update_id, answer, answer_time, update_id))
                else:
                    db.execute('INSERT INTO answers (update_id, quiz_id, question, team_id, answer, timestamp) '
                               'VALUES (?, ?, ?, ?, ?, ?)',
                               (new_update_id, quiz_id, question, team_id, answer, answer_time))

                self._on_update()
                return new_update_id

    def set_answer_points(self, *, quiz_id: str, question: int, team_id: int, points: int) -> int:
        with self._db_lock, contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                (update_id, _) = self._select_answer(
                    db=db, quiz_id=quiz_id, question=question, team_id=team_id)

                new_update_id = self._get_next_answer_update_id(db)

                if update_id:
                    db.execute('UPDATE answers '
                               'SET update_id = ?, points = ? '
                               'WHERE update_id = ?',
                               (new_update_id, points, update_id))
                else:
                    db.execute('INSERT INTO answers (update_id, quiz_id, question, team_id, answer, timestamp, points) '
                               'VALUES (?, ?, ?, ?, "", 0, ?)',
                               (new_update_id, quiz_id, question, team_id, points))

                self._on_update()
                return new_update_id

    def update_team(self, quiz_id: str, team_id: int, name: str, registration_time: int) -> int:
        with self._db_lock, contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                (update_id, timestamp) = db.execute('SELECT update_id, timestamp FROM teams WHERE quiz_id = ? AND id = ?',
                                                    (quiz_id, team_id)).fetchone() or (0, 0)
                if timestamp > registration_time:
                    return 0

                (last_update_id,) = db.execute(
                    'SELECT MAX(update_id) FROM teams').fetchone()
                new_update_id = (last_update_id or 0) + 1

                if update_id:
                    db.execute('UPDATE teams SET update_id = ?, name = ?, timestamp = ? WHERE update_id = ?',
                               (new_update_id, name, registration_time, update_id))
                else:
                    db.execute('INSERT INTO teams'
                               '(update_id, quiz_id, id, name, timestamp)'
                               'VALUES (?, ?, ?, ?, ?)',
                               (new_update_id, quiz_id, team_id, name, registration_time))
                self._on_update()
                return new_update_id

    def get_teams(self, *, quiz_id: str, team_id: Optional[int] = None, min_update_id: int = 0) -> List[Team]:
        conditions = []
        params = []

        if quiz_id:
            conditions.append('quiz_id = ?')
            params.append(quiz_id)

        if min_update_id:
            conditions.append('update_id >= ?')
            params.append(min_update_id)

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

    def create_if_not_exists(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''CREATE TABLE IF NOT EXISTS teams (
                    update_id INTEGER PRIMARY KEY NOT NULL,
                    quiz_id TEXT NOT NULL,
                    id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    UNIQUE(quiz_id, id))''')
                db.execute('''CREATE TABLE IF NOT EXISTS answers (
                    update_id INTEGER PRIMARY KEY NOT NULL,
                    quiz_id TEXT NOT NULL,
                    question INTEGER NOT NULL,
                    team_id INTEGER NOT NULL,
                    answer TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    points INTEGER,
                    UNIQUE(quiz_id, question, team_id))''')
                db.execute('''CREATE TABLE IF NOT EXISTS messages (
                    insert_timestamp INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    update_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    text TEXT NOT NULL)''')
