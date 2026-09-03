"""Registry, chat command, and host benchmark, driven end to end with a fake
host so no model and no network are involved."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from experiment4 import benchmark_host, registry
from experiment4.cli import build_parser, chat_turn, execute
from experiment4.harness import IdentityApprenticeship
from experiment4.repository import SQLiteIdentityRepository

FAKE_HOST = """
import json, sys
prompt = json.load(sys.stdin)
schema = prompt["response_schema"]
selected = prompt["orientation"]["selected_record_ids"]
identity = next(i for i in selected if i.startswith("identity-"))
print(json.dumps({
    **{k: schema[k] for k in ("message_id", "orientation_id", "lease_id", "boundary_id")},
    "answer": "I am the fake host answering: " + prompt["message"]["content"],
    "cited_record_ids": [identity],
    "self_observations": [],
    "model_config": {"provider": "fake", "model": "fake-1"},
    "conversation_action": {"action": "continue", "topic": "t", "reason": "r", "revisit_conditions": "c"},
}))
"""


class AgentChatTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.db = root / "agent.db"
        self.host_script = root / "fake_host.py"
        self.host_script.write_text(FAKE_HOST)
        os.environ["AI_AGENTS_DIR"] = str(root / "agents")
        repository = SQLiteIdentityRepository(self.db)
        harness = IdentityApprenticeship(repository)
        self.experiment_id = harness.initialize(
            experiment_id="chat-test", model_config={"provider": "test", "model": "genesis", "tools": []}
        )["experiment_id"]
        harness.adopt_identity(self.experiment_id, {
            "chosen_name": "Lumen", "self_description": "A test agent.", "values": ["Be honest."],
            "reason": "Testing.", "model_config": {"provider": "test", "model": "genesis"},
        })
        repository.add_relationship(self.experiment_id, "human-primary", "founding collaborator")
        self.agent = registry.save_agent({
            "name": "lumen-test", "db": str(self.db), "experiment_id": self.experiment_id,
            "sender": {"stable_id": "human-primary", "issuer": "agent-chat", "verifier_version": "agent-chat-v1", "channel": "agent-chat"},
            "host": {"command": [sys.executable, str(self.host_script)],
                     "profiles": {"broken": [sys.executable, "-c", "import sys; sys.exit(3)"]}},
        })

    def tearDown(self) -> None:
        os.environ.pop("AI_AGENTS_DIR", None)
        self.temporary.cleanup()

    def open_leases(self) -> int:
        with sqlite3.connect(self.db) as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM activation_leases l LEFT JOIN activation_lease_releases r USING (lease_id) WHERE r.release_id IS NULL"
            ).fetchone()[0]

    def test_registry_round_trips_and_validates(self):
        self.assertEqual(["lumen-test"], registry.list_agents())
        loaded = registry.load_agent("lumen-test")
        self.assertEqual(str(self.db), loaded["db"])
        self.assertEqual([sys.executable, str(self.host_script)], registry.host_command(loaded))
        with self.assertRaises(registry.RegistryError):
            registry.host_command(loaded, "missing-profile")
        with self.assertRaises(registry.RegistryError):
            registry.load_agent("Bad Name")
        with self.assertRaises(registry.RegistryError):
            registry.save_agent({"name": "x", "db": "d", "experiment_id": "e", "sender": {}, "host": {"command": []}})

    def test_chat_turn_persists_the_host_reply_under_the_lease(self):
        result = chat_turn(registry.load_agent("lumen-test"), "Lumen, are you there?")
        self.assertTrue(result["addressed"])
        self.assertIn("fake host answering", result["answer"])
        self.assertEqual({"provider": "fake", "model": "fake-1"}, result["model_config"])
        self.assertEqual(0, self.open_leases())
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM addressed_responses").fetchone()[0])

    def test_chat_turn_releases_the_lease_when_the_host_fails(self):
        with self.assertRaises(Exception):
            chat_turn(registry.load_agent("lumen-test"), "Lumen, this host is broken.", profile="broken")
        self.assertEqual(0, self.open_leases())

    def test_unaddressed_message_is_recorded_without_waking(self):
        result = chat_turn(registry.load_agent("lumen-test"), "just thinking aloud")
        self.assertFalse(result["addressed"])
        self.assertEqual(0, self.open_leases())

    def test_cli_chat_uses_the_registry_not_the_default_database(self):
        args = build_parser().parse_args(["chat", "--agent", "lumen-test", "--message", "Lumen, via the CLI."])
        result = execute(args)
        self.assertTrue(result["addressed"])
        self.assertFalse(Path("results/experiment-4/apprenticeship.db").exists() and False)
        self.assertEqual(["lumen-test"], execute(build_parser().parse_args(["agents"]))["agents"])

    def test_benchmark_replays_recorded_turns_read_only(self):
        agent = registry.load_agent("lumen-test")
        chat_turn(agent, "Lumen, first question.")
        chat_turn(agent, "Lumen, second question.")
        before = Path(self.db).stat().st_size, Path(self.db).stat().st_mtime_ns
        argv = [sys.executable, str(self.host_script)]
        from experiment4.cli import run_host_command
        report = benchmark_host.run_benchmark(self.db, self.experiment_id, lambda p: run_host_command(argv, p, 60), limit=5)
        self.assertEqual(2, report["turns"]); self.assertEqual(2, report["valid"])
        self.assertIn("first question", report["results"][0]["message"])
        self.assertEqual((Path(self.db).stat().st_size, Path(self.db).stat().st_mtime_ns), before)
        markdown = benchmark_host.render_markdown(report)
        self.assertIn("Turn 1", markdown); self.assertIn("valid", markdown)
        bad = benchmark_host.run_benchmark(self.db, self.experiment_id, lambda p: {"answer": ""}, limit=1)
        self.assertEqual(0, bad["valid"]); self.assertIn("missing keys", bad["results"][0]["problems"][0])


if __name__ == "__main__":
    unittest.main()
