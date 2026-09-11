import unittest

from cardinal_power import cardinal_power


class CardinalPowerTests(unittest.TestCase):
    def test_calculates_exactly(self):
        self.assertEqual(cardinal_power(62, 10), 839299365868340224)
        self.assertEqual(cardinal_power(2, 128), 2**128)
        self.assertEqual(cardinal_power(10, 0), 1)

    def test_rejects_invalid_values(self):
        for arguments in ((0, 2), (2, -1), (2.5, 3), (True, 3)):
            with (
                self.subTest(arguments=arguments),
                self.assertRaises((TypeError, ValueError)),
            ):
                cardinal_power(*arguments)  # type: ignore[arg-type]
