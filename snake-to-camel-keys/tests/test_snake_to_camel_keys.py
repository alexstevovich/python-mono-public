import unittest

from snake_to_camel_keys import snake_to_camel_keys


class SnakeToCamelKeysTests(unittest.TestCase):
    def test_recursively_converts_keys(self):
        source = {"outer_key": [{"inner_key": 1}], "unchanged": True}
        self.assertEqual(
            snake_to_camel_keys(source),
            {"outerKey": [{"innerKey": 1}], "unchanged": True},
        )
        self.assertIn("outer_key", source)

    def test_leaves_scalars_unchanged(self):
        self.assertEqual(snake_to_camel_keys("snake_value"), "snake_value")
        self.assertIsNone(snake_to_camel_keys(None))
