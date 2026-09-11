import unittest

from cap_product_volume import cap_product_volume


class CapProductVolumeTests(unittest.TestCase):
    def test_proportionally_scales_dimensions(self):
        dimensions = cap_product_volume([20, 10], 50)
        self.assertAlmostEqual(dimensions[0] * dimensions[1], 50)
        self.assertEqual(dimensions[0] / dimensions[1], 2)

    def test_returns_a_copy_when_volume_fits(self):
        source = [2, 3, 4]
        result = cap_product_volume(source, 24)
        self.assertEqual(result, source)
        self.assertIsNot(result, source)

    def test_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            cap_product_volume([], 1)
        with self.assertRaises(ValueError):
            cap_product_volume([2, -1], 4)
        with self.assertRaises(ValueError):
            cap_product_volume([2, 2], 0)
