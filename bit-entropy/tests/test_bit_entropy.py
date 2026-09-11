import unittest

from bit_entropy import bit_entropy


class BitEntropyTests(unittest.TestCase):
    def test_calculates_entropy(self):
        self.assertEqual(bit_entropy(2, 8), 8)
        self.assertEqual(bit_entropy(16, 32), 128)
        self.assertEqual(bit_entropy(1, 20), 0)

    def test_rejects_invalid_values(self):
        for arguments in ((0, 1), (2, -1), (2.5, 4)):
            with (
                self.subTest(arguments=arguments),
                self.assertRaises((TypeError, ValueError)),
            ):
                bit_entropy(*arguments)  # type: ignore[arg-type]
