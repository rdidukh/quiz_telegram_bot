from datetime import datetime
import contextlib
import sqlite3


class MessagesDb:
    def __init__(self, *, db_path: str):
        self.db_path = db_path

    def insert_message(self, *, timestamp: int, update_id: int, chat_id: int, text: str):
        insert_timestamp = int(datetime.utcnow().timestamp())
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            db.execute('''INSERT INTO messages
                     (insert_timestamp, timestamp, update_id, chat_id, text)
                     VALUES (?, ?, ?, ?, ?)''',
                       (insert_timestamp, timestamp, update_id, chat_id, text))
            db.commit()

    def create_if_not_exists(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                db.execute('''CREATE TABLE IF NOT EXISTS messages (
                    insert_timestamp INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    update_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    text TEXT NOT NULL)''')
