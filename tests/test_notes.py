import tempfile
import unittest
from pathlib import Path

from notes import Notes


class NotesTest(unittest.TestCase):
    def test_duplicates_search_edit_delete_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.db"
            notes = Notes(path)
            body = "  Git status\n\t下一行\n"
            first = notes.add(body)
            second = notes.add(body)
            notes.rename(first, "工作项目")
            notes.close()
            notes = Notes(path)
            try:
                self.assertEqual([n.id for n in notes.search("git")], [second, first])
                self.assertEqual([n.id for n in notes.search("项目")], [first])
                self.assertEqual(notes.search("  Git")[0].body, body)
                notes.delete(first)
                self.assertEqual([n.id for n in notes.search("")], [second])
            finally:
                notes.close()
