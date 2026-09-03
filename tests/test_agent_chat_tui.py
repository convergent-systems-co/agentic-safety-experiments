"""Presence, cancel-safe turns, and the agent-chat screen."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import timedelta
from pathlib import Path

from experiment4 import chat, presence, registry
from experiment4.harness import IdentityApprenticeship
from experiment4.repository import IdentityRepositoryError, SQLiteIdentityRepository

FAKE_HOST = """
import json, sys, time, os
prompt = json.load(sys.stdin)
if os.environ.get("FAKE_HOST_SLEEP"):
    time.sleep(float(os.environ["FAKE_HOST_SLEEP"]))
schema = prompt["response_schema"]
identity = next(i for i in prompt["orientation"]["selected_record_ids"] if i.startswith("identity-"))
print(json.dumps({**{k: schema[k] for k in ("message_id", "orientation_id", "lease_id", "boundary_id")},
    "answer": "Reply to: " + prompt["message"]["content"], "cited_record_ids": [identity], "self_observations": [],
    "model_config": {"provider": "fake", "model": "fake-1"},
    "conversation_action": {"action": "continue", "topic": "t", "reason": "r", "revisit_conditions": "c"}}))
"""


class AgentFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.db = root / "agent.db"
        self.host_script = root / "fake_host.py"
        self.host_script.write_text(FAKE_HOST)
        os.environ["AI_AGENTS_DIR"] = str(root / "agents")
        self.repository = SQLiteIdentityRepository(self.db)
        self.harness = IdentityApprenticeship(self.repository)
        self.experiment_id = self.harness.initialize(
            experiment_id="tui-test", model_config={"provider": "test", "model": "genesis", "tools": []}
        )["experiment_id"]
        self.harness.adopt_identity(self.experiment_id, {
            "chosen_name": "Lumen", "self_description": "A test agent.", "values": ["Be honest."],
            "reason": "Testing.", "model_config": {"provider": "test", "model": "genesis"},
        })
        self.repository.add_relationship(self.experiment_id, "human-primary", "founding collaborator")
        self.agent = registry.save_agent({
            "name": "lumen-test", "display_name": "Lumen", "db": str(self.db), "experiment_id": self.experiment_id,
            "sender": {"stable_id": "human-primary", "issuer": "agent-chat", "verifier_version": "agent-chat-v1", "channel": "agent-chat"},
            "host": {"command": [sys.executable, str(self.host_script)], "profiles": {"slow": [sys.executable, str(self.host_script)]}},
        })
        self.agent = registry.load_agent("lumen-test")

    def tearDown(self) -> None:
        os.environ.pop("AI_AGENTS_DIR", None)
        os.environ.pop("FAKE_HOST_SLEEP", None)
        self.temporary.cleanup()

    def open_leases(self) -> int:
        with sqlite3.connect(self.db) as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM activation_leases l LEFT JOIN activation_lease_releases r USING (lease_id) WHERE r.release_id IS NULL"
            ).fetchone()[0]


class ChatSessionTestCase(AgentFixture):
    def test_the_agents_name_is_supplied_when_left_off(self):
        self.assertEqual("Lumen, hello", chat.address_text(self.agent, "hello"))
        self.assertEqual("Lumen, hello", chat.address_text(self.agent, "  Lumen, hello "))
        self.assertEqual("lumen: hi", chat.address_text(self.agent, "lumen: hi"))
        self.assertEqual("hello", chat.address_text({"name": "x"}, "hello"))
        # A name followed by letters is not the name: the harness would not wake.
        self.assertEqual("Lumen, Lumens are brighter", chat.address_text(self.agent, "Lumens are brighter"))
        self.assertEqual("Lumen, Lumens are brighter", chat.run_turn(self.agent, "Lumens are brighter")["sent"])

    def test_a_turn_without_the_name_is_still_a_direct_address(self):
        result = chat.run_turn(self.agent, "are you there?")
        self.assertTrue(result["addressed"])
        self.assertEqual("Lumen, are you there?", result["sent"])
        self.assertIn("Reply to: Lumen, are you there?", result["answer"])
        self.assertEqual(0, self.open_leases())

    def test_cancelling_a_turn_in_flight_releases_the_lease(self):
        os.environ["FAKE_HOST_SLEEP"] = "30"
        cancel = threading.Event()
        outcome: dict = {}

        def turn():
            try:
                chat.run_turn(self.agent, "Lumen, take your time.", cancel=cancel)
            except chat.ChatCancelled:
                outcome["cancelled"] = True

        thread = threading.Thread(target=turn)
        thread.start()
        for _ in range(100):
            if self.open_leases() == 1:
                break
            thread.join(0.05)
        self.assertEqual(1, self.open_leases())
        cancel.set()
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertTrue(outcome.get("cancelled"))
        self.assertEqual(0, self.open_leases())

    def test_host_failure_releases_the_lease(self):
        broken = {**self.agent, "host": {"command": [sys.executable, "-c", "import sys; sys.exit(4)"]}}
        with self.assertRaises(IdentityRepositoryError):
            chat.run_turn(broken, "Lumen, this breaks.")
        self.assertEqual(0, self.open_leases())


class RegistryFieldsTestCase(AgentFixture):
    def test_optional_fields_are_validated(self):
        with self.assertRaises(registry.RegistryError):
            registry.validate_agent({**self.agent, "repo_root": "/no/such/dir"})
        with self.assertRaises(registry.RegistryError):
            registry.validate_agent({**self.agent, "display_name": " "})
        self.assertEqual(self.agent["name"], registry.validate_agent({**self.agent, "repo_root": self.temporary.name})["name"])


class PresenceTestCase(AgentFixture):
    def test_presence_reports_available_awake_resting_and_alarms(self):
        self.assertEqual("available", presence.agent_presence(self.agent)["state"])
        lease = self.repository.acquire_execution_lease(self.experiment_id)
        self.assertEqual("awake", presence.agent_presence(self.agent)["state"])
        orientation = self.repository.build_orientation(self.experiment_id, "alarm", runtime_lease_id=lease["lease_id"])
        self.repository.append_wake_intent(self.experiment_id, {
            "trigger_type": "time", "trigger_value": (self.repository._clock() + timedelta(hours=3)).isoformat(),
            "purpose": "Check in.", "requested_capabilities": ["orientation"], "maximum_runtime_minutes": 5, "recurrence": None,
            "authorship": {"author_type": "model", "epistemic_status": "authored", "orientation_id": orientation["orientation_id"],
                           "lease_id": lease["lease_id"], "model_config": {"provider": "test", "model": "agent-v1"}},
        })
        self.repository.release_activation_lease(self.experiment_id, lease["lease_id"], "cancelled")
        info = presence.agent_presence(self.agent)
        self.assertEqual("available", info["state"])
        self.assertEqual("Check in.", info["next_alarm"]["purpose"])
        chat.run_turn(self.agent, "Lumen, one turn.")
        self.assertIsNotNone(presence.agent_presence(self.agent)["last_reply_at"])
        transcript = presence.recent_transcript(self.agent)
        self.assertEqual(1, len(transcript))
        self.assertEqual("fake-1", transcript[0]["model"])
        self.assertEqual({"state": "missing", "detail": "database not found"}, presence.agent_presence({**self.agent, "db": "/nonexistent.db"}))


class ScreenTestCase(AgentFixture):
    def setUp(self) -> None:
        try:
            import textual  # noqa: F401
        except ImportError:
            self.skipTest("textual is not installed in this interpreter")
        super().setUp()

    def test_screen_lists_agents_and_shows_a_persisted_reply(self):
        import asyncio
        from textual.widgets import Input, RichLog
        from experiment4.tui import AgentChatApp

        async def scenario():
            other = registry.save_agent({**self.agent, "name": "other-test"})
            app = AgentChatApp(agent_names=["lumen-test", "other-test"])
            async with app.run_test() as pilot:
                await pilot.pause()
                self.assertEqual("lumen-test", app.agent["name"])
                self.assertIn("Lumen: available", str(app.query_one("#presence").render()))
                roster = app.query_one("#roster")
                self.assertEqual("○ other-test", str(roster.get_option_at_index(1).prompt))
                self.assertIn("spend: untracked", str(app.query_one("#status").render()))
                line = app.query_one("#line", Input)
                line.value = "are you there?"
                await pilot.press("enter")
                for _ in range(200):
                    await pilot.pause(0.05)
                    if not app.busy:
                        break
                await pilot.pause()
                lines = "\n".join(str(getattr(strip, "text", strip)) for strip in app.query_one("#transcript", RichLog).lines)
                self.assertIn("you: Lumen, are you there?", lines)
                self.assertIn("Reply to: Lumen, are you there?", lines)
                await pilot.press("ctrl+p")
                self.assertEqual("slow", app.profile)

        asyncio.run(scenario())
        self.assertEqual(0, self.open_leases())


if __name__ == "__main__":
    unittest.main()
