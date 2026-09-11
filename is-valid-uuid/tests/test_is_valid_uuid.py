import unittest

from is_valid_uuid import is_valid_uuid


class IsValidUuidTests(unittest.TestCase):
    def test_accepts_versions_one_through_eight(self):
        self.assertTrue(is_valid_uuid("6f9619ff-8b86-11d1-b42d-00c04fc964ff"))
        self.assertTrue(is_valid_uuid("550e8400-e29b-41d4-a716-446655440000"))
        self.assertTrue(is_valid_uuid("018f8e7b-7d31-7c2d-8c7a-3f6c4f9f9132"))
        self.assertTrue(is_valid_uuid("018f8e7b-7d31-8c2d-8c7a-3f6c4f9f9132"))

    def test_version_and_case_options(self):
        value = "550E8400-e29b-41D4-a716-446655440000"
        self.assertTrue(is_valid_uuid(value, version=4))
        self.assertFalse(is_valid_uuid(value, version=7))
        self.assertFalse(is_valid_uuid(value, strict_case=True))

    def test_rejects_invalid_values(self):
        values = (
            None,
            "not-a-uuid",
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
        )
        for value in values:
            with self.subTest(value=value):
                self.assertFalse(is_valid_uuid(value))
