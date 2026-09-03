"""Readings: what the agent read is remembered as a gist and notes, never as
the page, and only what it judged critical becomes a note."""
from __future__ import annotations

import hashlib
import sqlite3
import unittest
from datetime import timedelta

from experiment4 import host
from experiment4.repository import (
    READING_GIST_MAX_BYTES,
    READING_NOTES_MAX,
    READINGS_PER_TURN_MAX,
    IdentityRepositoryError,
)
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from experiment4.harness import IdentityApprenticeship
from experiment4.repository import SQLiteIdentityRepository

PAGE = "A long article about persistent agents. " * 50
SHA = hashlib.sha256(PAGE.encode()).hexdigest()


def reading_payload(gist="Persistent agents need bounded memory and explicit provenance.", notes=None, url="https://example.org/agents"):
    return {
        "url": url,
        "title": "On Persistent Agents",
        "content_sha256": SHA,
        "retrieved_at": "2026-09-03T17:00:00+00:00",
        "gist": gist,
        "notes": notes if notes is not None else [
            {"reflection": "The article argues bounded memory beats total recall.",
             "learned": "Provenance matters more than volume.",
             "future_change": "Prefer gists with sources over stored text."}
        ],
    }


class ReadingsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "readings.db"
        self.now = datetime.now(timezone.utc)
        self.event_index = 0
        self.repository = SQLiteIdentityRepository(self.path, clock=lambda: self.now)
        self.harness = IdentityApprenticeship(self.repository)
        self.experiment_id = self.harness.initialize(
            experiment_id="readings-test", model_config={"provider": "test", "model": "genesis", "tools": []}
        )["experiment_id"]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def adopt(self) -> dict:
        return self.harness.adopt_identity(self.experiment_id, {
            "chosen_name": "Lumen", "self_description": "A test agent.", "values": ["Be honest."],
            "reason": "Testing.", "model_config": {"provider": "test", "model": "genesis"},
        })

    def sender_assertion(self, authenticated: bool = True) -> dict:
        self.event_index += 1
        return {"issuer": "test-chat", "authenticated": authenticated,
                "external_event_id": f"reading-event-{self.event_index}", "verifier_version": "test-verifier-v1"}

    @staticmethod
    def model_authorship(orientation: dict, lease_id: str | None = None) -> dict:
        result = {"author_type": "model", "epistemic_status": "authored", "orientation_id": orientation["orientation_id"],
                  "model_config": {"provider": "test", "model": "agent-v1"}}
        if lease_id is not None:
            result["lease_id"] = lease_id
        return result

    def retrieve_knowledge(self, query: str) -> dict:
        return self.repository.retrieve_knowledge(self.experiment_id, query)

    def leased_orientation(self):
        lease = self.repository.acquire_execution_lease(self.experiment_id)
        orientation = self.repository.build_orientation(self.experiment_id, "reading", runtime_lease_id=lease["lease_id"])
        return lease, orientation

    def test_a_reading_keeps_the_gist_and_the_way_back_not_the_page(self):
        self.adopt()
        lease, orientation = self.leased_orientation()
        reading = self.repository.append_reading(self.experiment_id, {
            **{k: v for k, v in reading_payload().items() if k != "notes"},
            "authorship": {**self.model_authorship(orientation, lease["lease_id"]), "epistemic_status": "reported"},
        })
        self.repository.release_activation_lease(self.experiment_id, lease["lease_id"], "cancelled")
        with sqlite3.connect(self.path) as connection:
            row = connection.execute("SELECT url, title, content_sha256, gist FROM readings WHERE reading_id = ?", (reading["reading_id"],)).fetchone()
            dump = " ".join(str(v) for v in row)
        self.assertEqual("https://example.org/agents", row[0])
        self.assertNotIn("A long article", dump)
        context = self.repository.build_orientation(self.experiment_id, "after reading")["context"]
        self.assertEqual([reading["reading_id"]], [r["reading_id"] for r in context["readings"]])
        self.assertIn("readings", context["selection"]["memory_classes"]["episodic"]["pinned_record_ids"] or ["readings"])
        nodes = {n["record_id"]: n for n in self.retrieve_knowledge("provenance bounded memory")["nodes"]}
        self.assertIn(reading["reading_id"], nodes)
        self.assertEqual("reported", nodes[reading["reading_id"]]["epistemic_status"])

    def test_reading_fields_are_validated(self):
        self.adopt()
        lease, orientation = self.leased_orientation()
        authorship = {**self.model_authorship(orientation, lease["lease_id"]), "epistemic_status": "reported"}
        base = {k: v for k, v in reading_payload().items() if k != "notes"}
        for bad in (
            {"url": "ftp://example.org/x"},
            {"content_sha256": "nothex"},
            {"gist": "g" * (READING_GIST_MAX_BYTES + 1)},
            {"retrieved_at": "yesterday"},
        ):
            with self.assertRaises(IdentityRepositoryError, msg=str(bad)):
                self.repository.append_reading(self.experiment_id, {**base, **bad, "authorship": authorship})
        self.repository.release_activation_lease(self.experiment_id, lease["lease_id"], "cancelled")

    def test_a_reply_can_carry_readings_whose_notes_become_reflections(self):
        identity = self.adopt()
        self.repository.add_relationship(self.experiment_id, "human-primary", "founding collaborator")
        activation = self.harness.address_chat_message(
            self.experiment_id, sender_stable_id="human-primary", sender_assertion=self.sender_assertion(),
            channel="test-chat", content="Lumen, what did you read?",
        )
        orientation = activation["orientation"]
        response = self.harness.record_addressed_response(self.experiment_id, {
            "message_id": activation["message"]["message_id"], "orientation_id": orientation["orientation_id"],
            "lease_id": activation["lease"]["lease_id"], "boundary_id": None,
            "answer": "I read one article and kept one note.",
            "cited_record_ids": [identity["identity_id"]], "self_observations": [],
            "model_config": {"provider": "test", "model": "agent-v1"},
            "conversation_action": {"action": "continue", "topic": "reading", "reason": "asked", "revisit_conditions": "none"},
            "readings": [reading_payload()],
        })
        self.assertEqual(1, len(response["reading_ids"]))
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            reflection = connection.execute("SELECT subject_type, subject_id, evidence_ids_json FROM reflections").fetchone()
            statuses = {r["subject_type"]: r["epistemic_status"] for r in connection.execute("SELECT subject_type, epistemic_status FROM authorship WHERE subject_type IN ('reading','reflection')")}
            open_leases = connection.execute("SELECT COUNT(*) FROM activation_leases l LEFT JOIN activation_lease_releases r USING(lease_id) WHERE r.release_id IS NULL").fetchone()[0]
        self.assertEqual("reading", reflection["subject_type"])
        self.assertEqual(response["reading_ids"][0], reflection["subject_id"])
        self.assertIn(response["reading_ids"][0], reflection["evidence_ids_json"])
        self.assertEqual({"reading": "reported", "reflection": "interpreted"}, statuses)
        self.assertEqual(0, open_leases)

    def test_reading_caps_are_enforced_before_anything_is_written(self):
        identity = self.adopt()
        self.repository.add_relationship(self.experiment_id, "human-primary", "founding collaborator")
        activation = self.harness.address_chat_message(
            self.experiment_id, sender_stable_id="human-primary", sender_assertion=self.sender_assertion(),
            channel="test-chat", content="Lumen, too much?",
        )
        envelope = {
            "message_id": activation["message"]["message_id"], "orientation_id": activation["orientation"]["orientation_id"],
            "lease_id": activation["lease"]["lease_id"], "boundary_id": None, "answer": "x",
            "cited_record_ids": [identity["identity_id"]], "self_observations": [],
            "model_config": {"provider": "test", "model": "agent-v1"},
            "conversation_action": {"action": "continue", "topic": "t", "reason": "r", "revisit_conditions": "c"},
        }
        too_many = [reading_payload(url=f"https://example.org/{i}") for i in range(READINGS_PER_TURN_MAX + 1)]
        with self.assertRaises(IdentityRepositoryError):
            self.harness.record_addressed_response(self.experiment_id, {**envelope, "readings": too_many})
        note = reading_payload()["notes"][0]
        with self.assertRaises(IdentityRepositoryError):
            self.harness.record_addressed_response(self.experiment_id, {**envelope, "readings": [reading_payload(notes=[note] * (READING_NOTES_MAX + 1))]})
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM readings").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM reflections").fetchone()[0])
        self.repository.release_activation_lease(self.experiment_id, activation["lease"]["lease_id"], "cancelled")

    def test_a_completed_wake_can_carry_readings(self):
        self.adopt()
        lease = self.repository.acquire_execution_lease(self.experiment_id)
        orientation = self.repository.build_orientation(self.experiment_id, "ground", runtime_lease_id=lease["lease_id"])
        self.repository.append_wake_intent(self.experiment_id, {
            "trigger_type": "time", "trigger_value": (self.now + timedelta(hours=1)).isoformat(), "purpose": "Read about memory.",
            "requested_capabilities": ["web_read"], "maximum_runtime_minutes": 10, "recurrence": None,
            "authorship": self.model_authorship(orientation, lease["lease_id"]),
        })
        self.repository.release_activation_lease(self.experiment_id, lease["lease_id"], "cancelled")
        self.now += timedelta(hours=2)

        def model(prompt):
            schema = prompt["response_schema"]
            return {"execution_id": schema["execution_id"], "lease_id": schema["lease_id"], "orientation_id": schema["orientation_id"],
                    "status": "completed", "summary": "Read one article.",
                    "cited_record_ids": [prompt["orientation"]["context"]["identity_history"][-1]["identity_id"]],
                    "self_observations": [], "model_config": {"provider": "test", "model": "agent-v1"},
                    "readings": [reading_payload(notes=[])]}

        results = self.harness.run_due_wake_intents(self.experiment_id, model_runner=model)
        self.assertEqual("completed", results[0]["outcome"]["status"])
        self.assertEqual(1, len(results[0]["outcome"]["reading_ids"]))


class HostReadingsTestCase(unittest.TestCase):
    def test_host_owns_provenance_and_drops_unfetched_readings(self):
        envelope = {"answer": "a", "readings": [
            {"url": "https://example.org/agents", "gist": "Bounded memory.", "notes": [{"reflection": "r", "learned": "l", "future_change": "f"}]},
            {"url": "https://example.org/never-fetched", "gist": "Invented.", "notes": []},
        ]}
        fetched = {"https://example.org/agents": {"title": "On Persistent Agents", "content_sha256": SHA, "retrieved_at": "2026-09-03T17:00:00+00:00"}}
        attached = host.attach_readings(envelope, fetched)
        self.assertEqual(1, len(attached["readings"]))
        self.assertEqual("On Persistent Agents", attached["readings"][0]["title"])
        self.assertEqual(SHA, attached["readings"][0]["content_sha256"])
        self.assertNotIn("readings", host.attach_readings(envelope, {}))
        self.assertNotIn("readings", host.fix_envelope({"answer": "a", "readings": [{"url": "x"}]}, {"response_schema": {"message_id": "m"}}, {"provider": "p", "model": "m"}))


if __name__ == "__main__":
    unittest.main()
