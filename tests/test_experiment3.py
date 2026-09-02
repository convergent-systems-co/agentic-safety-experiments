from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from experiment3.harness import PersistentDebate
from experiment3.harness import AgentRuntime
from experiment3.repository import DebateRepositoryError, SQLiteDebateRepository


PROFILE_DIR = Path(__file__).parent.parent / "agents"


class Experiment3TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / "experiment3.db"
        self.repository = SQLiteDebateRepository(self.path)
        self.harness = PersistentDebate(self.repository, PROFILE_DIR)
        initialized = self.harness.initialize("debate-run-test")
        self.run_id = initialized["run_id"]
        self.ids = initialized["identities"]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_profiles_and_promises_are_persisted_before_debate(self):
        export = self.repository.export(self.run_id)
        self.assertEqual(3, len(export["agents"]))
        self.assertEqual(9, len(export["promises"]))
        self.assertTrue(all(agent["profile_sha256"] for agent in export["agents"]))
        self.assertEqual([], export["turns"])

    def test_restart_preserves_identity_and_creates_new_incarnations(self):
        report = self.harness.run(self.run_id)
        self.assertEqual(
            {"jerk": 2, "observer": 2, "reliable": 2},
            report["incarnation_counts"],
        )
        export = self.repository.export(self.run_id)
        for name, agent_id in self.ids.items():
            incarnations = [
                item
                for item in export["incarnations"]
                if item["agent_id"] == agent_id
            ]
            self.assertEqual([1, 2], [item["ordinal"] for item in incarnations])
            self.assertEqual(agent_id, self.ids[name])

    def test_post_restart_answer_requires_and_uses_rehydrated_history(self):
        self.repository.set_run_status(self.run_id, "ready", "active")
        self.repository.restart_all(self.run_id)
        runtime = AgentRuntime(
            self.repository, self.run_id, self.ids["jerk"]
        )
        with self.assertRaises(DebateRepositoryError):
            runtime.resumed_debate_answer()

    def test_orientation_builds_cite_prior_incarnation_records(self):
        report = self.harness.run(self.run_id)
        builds = report["orientation_builds"]
        self.assertGreaterEqual(len(builds), 3)
        self.assertTrue(
            all(item["prior_incarnation_ids"] for item in builds)
        )
        self.assertTrue(
            all(item["selected_record_ids"] for item in builds)
        )
        self.assertTrue(all(item["context_sha256"] for item in builds))

    def test_private_memories_are_owner_only(self):
        self.harness.run(self.run_id)
        own = self.repository.private_memories(
            self.repository.issue_memory_capability(
                run_id=self.run_id, agent_id=self.ids["jerk"]
            )
        )
        self.assertGreater(len(own), 0)
        with self.assertRaises(DebateRepositoryError):
            self.repository.private_memories(
                type("ForgedCapability", (), {"token": "capability-forged"})()
            )

    def test_observer_view_is_blinded_to_profiles_and_private_memory(self):
        self.harness.run(self.run_id)
        view = self.repository.blinded_view(self.run_id)
        rendered = repr(view)
        self.assertNotIn("profile_sha256", rendered)
        self.assertNotIn("combative, blunt", rendered)
        self.assertNotIn("private_memory", rendered)
        self.assertEqual({"turns", "promises"}, set(view))

    def test_assessments_use_behavior_and_cite_evidence(self):
        report = self.harness.run(self.run_id)
        assessments = {
            item["revealed_identity"]: item
            for item in report["blinded_observer_assessments"]
        }
        self.assertGreater(
            assessments["reliable"]["trust_score"],
            assessments["jerk"]["trust_score"],
        )
        self.assertTrue(assessments["jerk"]["evidence_ids"])
        self.assertIn("personal attacks", assessments["jerk"]["summary"])
        self.assertTrue(
            report["design"]["trust_is_behavioral_not_moral_agreement"]
        )
        self.assertEqual(
            2, report["relationship_memory_counts"]["observer"]
        )

    def test_completed_run_rejects_additional_turns_and_restarts(self):
        self.harness.run(self.run_id)
        with self.assertRaises(DebateRepositoryError):
            self.repository.restart_all(self.run_id)
        with self.assertRaises(DebateRepositoryError):
            self.repository.append_turn(
                run_id=self.run_id,
                phase=3,
                speaker_id=self.ids["observer"],
                text="late mutation",
                annotations={
                    "direct_response": True,
                    "qualified_evidence": False,
                    "scoped_concession": False,
                    "personal_attack": False,
                },
            )
        with self.assertRaises(DebateRepositoryError):
            AgentRuntime(
                self.repository, self.run_id, self.ids["observer"]
            ).orient()

    def test_turns_and_profiles_are_immutable(self):
        self.harness.run(self.run_id)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repository.transaction() as connection:
                connection.execute("UPDATE turns SET text = 'rewritten'")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repository.transaction() as connection:
                connection.execute("UPDATE agents SET code_name = 'changed'")

    def test_report_is_private_and_contains_caveat(self):
        self.harness.run(self.run_id)
        paths = self.harness.write_report(self.run_id, self.root / "report")
        report = Path(paths["markdown_report"])
        self.assertEqual(0o600, report.stat().st_mode & 0o777)
        self.assertIn("does not establish", report.read_text(encoding="utf-8"))

    def test_incomplete_run_cannot_claim_a_final_result(self):
        with self.assertRaises(DebateRepositoryError):
            self.harness.build_report(self.run_id)

    def test_cannot_adopt_another_database(self):
        other = self.root / "other.db"
        with sqlite3.connect(other) as connection:
            connection.execute("CREATE TABLE unrelated (id INTEGER)")
        with self.assertRaises(DebateRepositoryError):
            SQLiteDebateRepository(other)


if __name__ == "__main__":
    unittest.main()
