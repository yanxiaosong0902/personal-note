import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Note:
    id: int
    body: str
    remark: str


class Notes:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    body TEXT NOT NULL,
                    remark TEXT NOT NULL DEFAULT ''
                )
            """)

    def add(self, body, remark=""):
        with self.db:
            return self.db.execute(
                "INSERT INTO notes(body, remark) VALUES (?, ?)", (body, remark)
            ).lastrowid

    def search(self, query):
        needle = query.casefold()
        rows = self.db.execute("SELECT id, body, remark FROM notes ORDER BY id DESC")
        return [Note(*row) for row in rows
                if needle in row[1].casefold() or needle in row[2].casefold()]

    def rename(self, note_id, remark):
        with self.db:
            self.db.execute("UPDATE notes SET remark = ? WHERE id = ?", (remark, note_id))

    def update(self, note_id, body, remark):
        with self.db:
            self.db.execute(
                "UPDATE notes SET body = ?, remark = ? WHERE id = ?",
                (body, remark, note_id),
            )

    def delete(self, note_id):
        with self.db:
            self.db.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def close(self):
        self.db.close()
