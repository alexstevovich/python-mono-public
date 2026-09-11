import unittest

from reduce_fraction import reduce_fraction


class ReduceFractionTests(unittest.TestCase):
    def test_reduces_and_normalizes(self):
        self.assertEqual(reduce_fraction(8, 12), "2/3")
        self.assertEqual(reduce_fraction(7, 5), "7/5")
        self.assertEqual(reduce_fraction(0, 25), "0/1")
        self.assertEqual(reduce_fraction(8, -12), "-2/3")
        self.assertEqual(reduce_fraction(-8, -12), "2/3")

    def test_rejects_invalid_values(self):
        with self.assertRaises(TypeError):
            reduce_fraction(1.5, 2)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            reduce_fraction(1, 0)
