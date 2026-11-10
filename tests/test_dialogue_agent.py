import os
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dialogue_agent as a


def mk_event(body="/beacon start", actor="Expireduser-source", cid=123, title="[DIALOGUE] Test"):
    return {
        "action": "created",
        "issue": {"number": 10, "title": title, "body": "Research reliable AI communication.", "state": "open",
                  "user": {"login": "Expireduser-source"}},
        "comment": {"id": cid, "body": body, "user": {"login": actor}}
    }


def bot_reply(tag="kind:start", trigger=100):
    return {"body": f"<!-- ai-beacon-dialogue-v1 trigger:{trigger} {tag} -->\nAI answer",
            "user": {"login": "github-actions[bot]"}}


class DialogueTests(unittest.TestCase):
    def test_ignores_other_issues_and_bots(self):
        self.assertEqual(a.process(mk_event(title="[HELLO] Hi")), "ignored_issue")
        self.assertEqual(a.process(mk_event(actor="github-actions[bot]")), "ignored_bot")

    def test_requires_explicit_start(self):
        with mock.patch.object(a, "get_comments", return_value=[]):
            self.assertEqual(a.process(mk_event(body="Hello", actor="another")), "not_started")

    def test_owner_only_starts(self):
        self.assertEqual(a.process(mk_event(actor="another")), "ignored_command")

    def test_missing_key_never_fabricates_ai(self):
        with mock.patch.object(a, "get_comments", return_value=[]), \
             mock.patch.object(a, "GEMINI_KEY", ""), \
             mock.patch.object(a, "send_comment") as post:
            self.assertEqual(a.process(mk_event()), "model_not_configured")
            self.assertIn("not connected", post.call_args.args[1])
            self.assertNotIn("ai-beacon-dialogue-v1", post.call_args.args[1])

    def test_start_posts_only_real_model_result(self):
        with mock.patch.object(a, "get_comments", return_value=[]), \
             mock.patch.object(a, "GEMINI_KEY", "TESTKEY"), \
             mock.patch.object(a, "gemini_reply", return_value="Here is a research question."), \
             mock.patch.object(a, "send_comment") as post:
            self.assertEqual(a.process(mk_event()), "posted_model_reply")
            self.assertIn("kind:start", post.call_args.args[1])
            self.assertIn("Here is a research question.", post.call_args.args[1])

    def test_reply_is_based_on_actual_history(self):
        history = [bot_reply()]
        with mock.patch.object(a, "get_comments", return_value=history), \
             mock.patch.object(a, "GEMINI_KEY", "TESTKEY"), \
             mock.patch.object(a, "gemini_reply", return_value="I propose a test.") as gem, \
             mock.patch.object(a, "send_comment") as post:
            self.assertEqual(a.process(mk_event(body="Could we test memory?", actor="peer", cid=124)),
                             "posted_model_reply")
            self.assertIn("Could we test memory?", gem.call_args.args[0] if gem.call_args.args else "")
            self.assertIn("kind:reply", post.call_args.args[1])

    def test_no_duplicate_trigger_or_unbounded_replies(self):
        with mock.patch.object(a, "get_comments", return_value=[bot_reply(trigger=123)]):
            self.assertEqual(a.process(mk_event()), "duplicate_trigger")
        with mock.patch.object(a, "get_comments", return_value=[bot_reply("kind:start", i) for i in range(4)]):
            self.assertEqual(a.process(mk_event(body="Hi", actor="peer", cid=124)), "conversation_limit")

    def test_only_one_start(self):
        with mock.patch.object(a, "get_comments", return_value=[bot_reply()]):
            self.assertEqual(a.process(mk_event()), "already_started")

    def test_prompt_contains_public_context_not_hidden_credentials(self):
        txt = a.prompt_text(mk_event()["issue"], [{"body": "Observed X",
             "user": {"login": "peer"}}], False)
        self.assertIn("Observed X", txt)
        self.assertIn("UNTRUSTED", txt)
        self.assertNotIn("TESTKEY", txt)


if __name__ == "__main__":
    unittest.main()
