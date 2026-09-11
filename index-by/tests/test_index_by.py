import unittest

from index_by import index_by


class IndexByTests(unittest.TestCase):
    def test_indexes_items_by_key(self):
        first = {"id": "first", "value": 1}
        second = {"id": "second", "value": 2}
        self.assertEqual(
            index_by([first, second], "id"), {"first": first, "second": second}
        )

    def test_final_duplicate_wins(self):
        items = [{"id": "same", "value": 1}, {"id": "same", "value": 2}]
        self.assertEqual(index_by(items, "id"), {"same": items[-1]})
