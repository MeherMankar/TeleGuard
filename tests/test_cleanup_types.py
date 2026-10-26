import unittest

from teleguard.core.cleanup_types import CLEANUP_TYPE_SETTINGS, parse_cleanup_types


class TestCleanupTypes(unittest.TestCase):
    def test_all_includes_every_action(self):
        selected, settings = parse_cleanup_types("all")

        self.assertEqual(selected, list(CLEANUP_TYPE_SETTINGS))
        self.assertIn("my_messages", selected)
        self.assertTrue(all(settings.values()))

    def test_selected_types_are_normalized_and_deduplicated(self):
        selected, settings = parse_cleanup_types(" Personal, bots,personal ")

        self.assertEqual(selected, ["personal", "bots"])
        self.assertTrue(settings["personal_chats"])
        self.assertTrue(settings["bot_chats"])
        self.assertFalse(settings["my_messages"])

    def test_all_rejects_empty_and_unknown_actions(self):
        for value in ("", "personal,", "unknown"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_cleanup_types(value)
