"""
Unit tests for Claude-Linux-Helper.

These tests cover the config, linux_tips, and agent modules without
requiring a real Anthropic API key (the agent tests use unittest.mock).
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Make sure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── config ────────────────────────────────────────────────────────────────────

class TestConfig(unittest.TestCase):
    def test_get_api_key_returns_key_when_set(self):
        import config
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}):
            self.assertEqual(config.get_api_key(), "test-key-123")

    def test_get_api_key_exits_when_missing(self):
        import config
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit):
                config.get_api_key()

    def test_model_is_string(self):
        import config
        self.assertIsInstance(config.MODEL, str)
        self.assertTrue(config.MODEL.startswith("claude"))

    def test_max_tokens_positive(self):
        import config
        self.assertGreater(config.MAX_TOKENS, 0)


# ── linux_tips ────────────────────────────────────────────────────────────────

class TestLinuxTips(unittest.TestCase):
    def test_categories_not_empty(self):
        from linux_tips import CATEGORIES
        self.assertGreater(len(CATEGORIES), 0)

    def test_each_category_has_title_and_tips(self):
        from linux_tips import CATEGORIES
        for name, cat in CATEGORIES.items():
            with self.subTest(category=name):
                self.assertIn("title", cat)
                self.assertIn("tips", cat)
                self.assertIsInstance(cat["tips"], list)
                self.assertGreater(len(cat["tips"]), 0)

    def test_get_all_tips_returns_string(self):
        from linux_tips import get_all_tips
        result = get_all_tips()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_get_category_tips_known(self):
        from linux_tips import get_category_tips
        result = get_category_tips("packages")
        self.assertIn("apt", result)

    def test_get_category_tips_unknown(self):
        from linux_tips import get_category_tips
        result = get_category_tips("nonexistent_category")
        self.assertIn("Unknown category", result)

    def test_get_category_tips_case_insensitive(self):
        from linux_tips import get_category_tips
        lower = get_category_tips("packages")
        upper = get_category_tips("PACKAGES")
        self.assertEqual(lower, upper)

    def test_claude_category_exists(self):
        from linux_tips import CATEGORIES
        self.assertIn("claude", CATEGORIES)

    def test_python_category_exists(self):
        from linux_tips import CATEGORIES
        self.assertIn("python", CATEGORIES)


# ── agent ─────────────────────────────────────────────────────────────────────

class TestAgent(unittest.TestCase):
    def _make_agent(self):
        """Return an Agent with a mocked Anthropic client."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-key"}):
            import importlib
            import agent as agent_module
            importlib.reload(agent_module)
            ag = agent_module.Agent.__new__(agent_module.Agent)
            ag._history = []
            ag._client = MagicMock()
            return ag

    def test_initial_history_empty(self):
        ag = self._make_agent()
        self.assertEqual(ag.history, [])

    def test_chat_appends_to_history(self):
        ag = self._make_agent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude!")]
        ag._client.messages.create.return_value = mock_response

        reply = ag.chat("Hello")

        self.assertEqual(reply, "Hello from Claude!")
        self.assertEqual(len(ag.history), 2)
        self.assertEqual(ag.history[0]["role"], "user")
        self.assertEqual(ag.history[0]["content"], "Hello")
        self.assertEqual(ag.history[1]["role"], "assistant")
        self.assertEqual(ag.history[1]["content"], "Hello from Claude!")

    def test_reset_clears_history(self):
        ag = self._make_agent()
        ag._history = [{"role": "user", "content": "hi"}]
        ag.reset()
        self.assertEqual(ag.history, [])

    def test_multi_turn_preserves_history(self):
        ag = self._make_agent()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="reply")]
        ag._client.messages.create.return_value = mock_response

        ag.chat("first message")
        ag.chat("second message")

        self.assertEqual(len(ag.history), 4)

    def test_history_is_copy(self):
        ag = self._make_agent()
        h = ag.history
        h.append({"role": "user", "content": "tamper"})
        self.assertEqual(ag.history, [])


if __name__ == "__main__":
    unittest.main()
