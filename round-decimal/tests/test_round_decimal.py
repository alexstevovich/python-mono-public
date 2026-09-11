import unittest

from round_decimal import round_decimal


class RoundDecimalTests(unittest.TestCase):
    def test_rounds_positive_and_negative_places(self):
        self.assertEqual(round_decimal(1.005, 2), 1.01)
        self.assertEqual(round_decimal(1499, -2), 1500)

    def test_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            round_decimal(float("inf"))
        with self.assertRaises(TypeError):
            round_decimal(1, 1.5)  # type: ignore[arg-type]
