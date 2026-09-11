import unittest

from trim_http import trim_http


class TrimHttpTests(unittest.TestCase):
    def test_removes_http_and_https(self):
        self.assertEqual(trim_http("http://example.com"), "example.com")
        self.assertEqual(trim_http("https://example.com"), "example.com")

    def test_leaves_other_strings_unchanged(self):
        self.assertEqual(trim_http("example.com"), "example.com")

    def test_rejects_non_string_values(self):
        with self.assertRaises(TypeError):
            trim_http(None)  # type: ignore[arg-type]
