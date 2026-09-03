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
            "scope_kind": "global", "sender_stable_id": None,
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
        self.assertEqual(28 * 1024, context["selection"]["memory_classes"]["episodic"]["byte_budget"])
        nodes = {n["record_id"]: n for n in self.retrieve_knowledge("provenance bounded memory")["nodes"]}
        self.assertIn(reading["reading_id"], nodes)
        self.assertEqual("reported", nodes[reading["reading_id"]]["epistemic_status"])

    def test_reading_fields_are_validated(self):
        self.adopt()
        lease, orientation = self.leased_orientation()
        authorship = {**self.model_authorship(orientation, lease["lease_id"]), "epistemic_status": "reported"}
        base = {k: v for k, v in reading_payload().items() if k != "notes"} | {"scope_kind": "global", "sender_stable_id": None}
        for bad in (
            {"url": "ftp://example.org/x"},
            {"content_sha256": "nothex"},
            {"gist": "g" * (READING_GIST_MAX_BYTES + 1)},
            {"retrieved_at": "yesterday"},
            {"scope_kind": "sender", "sender_stable_id": None},
            {"scope_kind": "global", "sender_stable_id": "someone"},
        ):
            with self.assertRaises(IdentityRepositoryError, msg=str(bad)):
                self.repository.append_reading(self.experiment_id, {**base, **bad, "authorship": authorship})
        # Credentials and fragments never survive into the record. The test URL
        # is assembled so no credential-shaped literal appears in this file.
        userinfo = "reader" + ":" + "not-a-real-credential"
        with_userinfo = "https://" + userinfo + "@example.org:8443/path?q=1#section"
        stored = self.repository.append_reading(self.experiment_id, {**base, "url": with_userinfo, "authorship": authorship})
        with sqlite3.connect(self.path) as connection:
            url = connection.execute("SELECT url FROM readings WHERE reading_id = ?", (stored["reading_id"],)).fetchone()[0]
        self.assertEqual("https://example.org:8443/path?q=1", url)
        self.repository.release_activation_lease(self.experiment_id, lease["lease_id"], "cancelled")

    def test_readings_carry_the_scope_of_the_turn_that_produced_them(self):
        identity = self.adopt()
        for sender in ("sender-a", "sender-b"):
            self.repository.add_relationship(self.experiment_id, sender, f"{sender} collaborator")

        def turn(sender: str, readings: list) -> None:
            activation = self.harness.address_chat_message(
                self.experiment_id, sender_stable_id=sender, sender_assertion=self.sender_assertion(),
                channel="test-chat", content=f"Lumen, what did you read for {sender}?",
            )
            self.harness.record_addressed_response(self.experiment_id, {
                "message_id": activation["message"]["message_id"], "orientation_id": activation["orientation"]["orientation_id"],
                "lease_id": activation["lease"]["lease_id"], "boundary_id": None, "answer": "Reading recorded.",
                "cited_record_ids": [identity["identity_id"]], "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {"action": "continue", "topic": "t", "reason": "r", "revisit_conditions": "c"},
                "readings": readings,
            })

        def peek(sender: str) -> dict:
            activation = self.harness.address_chat_message(
                self.experiment_id, sender_stable_id=sender, sender_assertion=self.sender_assertion(),
                channel="test-chat", content="Lumen, amaranth ledger?",
            )
            self.repository.release_activation_lease(self.experiment_id, activation["lease"]["lease_id"], "cancelled")
            return activation["orientation"]["context"]

        turn("sender-a", [reading_payload(gist="Private research about the amaranth ledger for sender A.", url="https://example.org/a")])
        self.assertEqual([], peek("sender-b")["readings"])
        b_nodes = self.repository.retrieve_knowledge(
            self.experiment_id, "amaranth ledger", current_sender_stable_id="sender-b", current_sender_authenticated=True
        )["nodes"]
        self.assertFalse(any(n["record_type"] == "reading" for n in b_nodes))
        self.assertEqual(1, len(peek("sender-a")["readings"]))
        internal = self.repository.build_orientation(self.experiment_id, "internal review")["context"]
        self.assertEqual(1, len(internal["readings"]))
        self.assertEqual("sender", internal["readings"][0]["scope_kind"])

    def test_a_reading_survives_a_stale_graph_unindexed(self):
        self.adopt()
        lease, orientation = self.leased_orientation()
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE knowledge_graph_meta SET derivation_version = derivation_version - 1")
        reading = self.repository.append_reading(self.experiment_id, {
            **{k: v for k, v in reading_payload().items() if k != "notes"},
            "scope_kind": "global", "sender_stable_id": None,
            "authorship": {**self.model_authorship(orientation, lease["lease_id"]), "epistemic_status": "reported"},
        })
        self.repository.release_activation_lease(self.experiment_id, lease["lease_id"], "cancelled")
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM readings").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM knowledge_graph_nodes WHERE record_id = ?", (reading["reading_id"],)).fetchone()[0])
        self.repository.rebuild_knowledge_graph(self.experiment_id)
        self.assertIn(reading["reading_id"], {n["record_id"] for n in self.retrieve_knowledge("provenance bounded")["nodes"]})

    def test_episodic_memory_evicts_by_age_across_experiences_and_readings(self):
        stamp = lambda i: f"2026-09-0{1 + i // 10}T00:00:{i % 10:02d}+00:00"
        context = {
            "selection": {"records_omitted_for_byte_budget": {}, "identity_records_omitted": 0, "aggregate_bytes_used": 0, "memory_classes": {}},
            "current_interlocutor": None, "identity_history": [{"identity_id": "identity-1", "created_at": stamp(0)}],
            "readings": [{"reading_id": f"reading-{i}", "created_at": stamp(i), "gist": "r" * 3_000} for i in range(3)],
            "experiences": [{"experience_id": f"experience-{i}", "created_at": stamp(10 + i), "content": "e" * 3_000} for i in range(8)],
            "knowledge_graph": {"nodes": [], "edges": [], "omissions": {"byte_limit": 0, "byte_limit_edges": 0}},
            "authorship_by_subject": {},
        }
        self.repository._fit_context_budget(context)
        omitted = context["selection"]["records_omitted_for_byte_budget"]
        self.assertGreater(omitted.get("readings", 0), 0)
        self.assertEqual(0, omitted.get("experiences", 0))

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

    def test_a_bad_reading_anywhere_in_the_list_persists_nothing(self):
        identity = self.adopt()
        self.repository.add_relationship(self.experiment_id, "human-primary", "founding collaborator")
        activation = self.harness.address_chat_message(
            self.experiment_id, sender_stable_id="human-primary", sender_assertion=self.sender_assertion(),
            channel="test-chat", content="Lumen, three readings, one broken.",
        )
        envelope = {
            "message_id": activation["message"]["message_id"], "orientation_id": activation["orientation"]["orientation_id"],
            "lease_id": activation["lease"]["lease_id"], "boundary_id": None, "answer": "x",
            "cited_record_ids": [identity["identity_id"]], "self_observations": [],
            "model_config": {"provider": "test", "model": "agent-v1"},
            "conversation_action": {"action": "continue", "topic": "t", "reason": "r", "revisit_conditions": "c"},
            "readings": [reading_payload(url="https://example.org/1"), reading_payload(url="https://example.org/2"),
                         {**reading_payload(url="ftp://example.org/3")}],
        }
        with self.assertRaises(IdentityRepositoryError):
            self.harness.record_addressed_response(self.experiment_id, envelope)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM readings").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM reflections").fetchone()[0])
        self.repository.release_activation_lease(self.experiment_id, activation["lease"]["lease_id"], "cancelled")
        with self.assertRaises(IdentityRepositoryError):
            self.harness.record_addressed_response(self.experiment_id, {**envelope, "readings": [reading_payload()]})
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM readings").fetchone()[0])

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
