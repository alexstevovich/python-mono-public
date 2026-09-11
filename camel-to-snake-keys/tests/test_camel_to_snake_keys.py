import unittest

from camel_to_snake_keys import camel_to_snake_keys


class CamelToSnakeKeysTests(unittest.TestCase):
    def test_recursively_converts_keys(self):
        source = {
            "userID": 1,
            "profileData": {"displayName": "Alex"},
            "APIValues": [{"URLValue": True}],
        }
        self.assertEqual(
            camel_to_snake_keys(source),
            {
                "user_id": 1,
                "profile_data": {"display_name": "Alex"},
                "api_values": [{"url_value": True}],
            },
        )
        self.assertIn("profileData", source)

    def test_leaves_scalars_unchanged(self):
        self.assertEqual(camel_to_snake_keys("alreadyCamel"), "alreadyCamel")
        self.assertIsNone(camel_to_snake_keys(None))
