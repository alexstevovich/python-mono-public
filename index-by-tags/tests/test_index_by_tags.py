import unittest

from index_by_tags import index_by_tags


class IndexByTagsTests(unittest.TestCase):
    def test_indexes_each_item_under_all_tags(self):
        first = {"tags": ["a", "b"]}
        second = {"tags": ["b"]}
        self.assertEqual(
            index_by_tags([first, second]), {"a": [first], "b": [first, second]}
        )

    def test_supports_custom_getter(self):
        item = {"labels": ["custom"]}
        self.assertEqual(
            index_by_tags([item], lambda value: value["labels"]), {"custom": [item]}
        )
