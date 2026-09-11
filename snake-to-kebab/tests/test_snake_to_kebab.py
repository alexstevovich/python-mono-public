import unittest

from snake_to_kebab import snake_to_kebab


class SnakeToKebabTests(unittest.TestCase):
    def test_converts_every_underscore(self):
        self.assertEqual(snake_to_kebab("one_two_three"), "one-two-three")

    def test_rejects_non_string_values(self):
        with self.assertRaises(TypeError):
            snake_to_kebab(None)  # type: ignore[arg-type]
