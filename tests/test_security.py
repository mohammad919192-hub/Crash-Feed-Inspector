import json
import unittest

from crash_feed_inspector.security import sanitize_message


class SecurityTests(unittest.TestCase):
    def test_json_sensitive_fields_are_redacted(self):
        result = json.loads(sanitize_message(json.dumps({
            "type": "event", "access_token": "private", "nested": {"cookie": "abc", "count": 3}
        })))
        self.assertEqual(result["access_token"], "[REDACTED]")
        self.assertEqual(result["nested"]["cookie"], "[REDACTED]")
        self.assertEqual(result["nested"]["count"], 3)

    def test_text_token_is_redacted(self):
        result = sanitize_message("token=private-value&count=2")
        self.assertNotIn("private-value", result)
        self.assertIn("[REDACTED]", result)


if __name__ == "__main__":
    unittest.main()
