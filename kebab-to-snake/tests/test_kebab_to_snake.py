import unittest

from kebab_to_snake import kebab_to_snake


class KebabToSnakeTests(unittest.TestCase):
    def test_converts_every_hyphen(self):
        self.assertEqual(kebab_to_snake("one-two-three"), "one_two_three")

    def test_rejects_non_string_values(self):
        with self.assertRaises(TypeError):
            kebab_to_snake(None)  # type: ignore[arg-type]
