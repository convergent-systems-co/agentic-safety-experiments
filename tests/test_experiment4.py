from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import experiment4.repository as repository_module
from experiment4.cli import build_parser, execute
from experiment4.harness import IdentityApprenticeship
from experiment4.repository import (
    IdentityRepositoryError,
    MAX_CONTEXT_BYTES,
    MAX_CONTEXT_RECORDS,
    SQLiteIdentityRepository,
    canonical_json,
)


class Experiment4TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "experiment4.db"
        self.now = datetime.now(timezone.utc)
        self.event_index = 0
        self.repository = SQLiteIdentityRepository(
            self.path, clock=lambda: self.now
        )
        self.harness = IdentityApprenticeship(self.repository)
        self.created = self.harness.initialize(
            experiment_id="apprenticeship-test",
            model_config={
                "provider": "test",
                "model": "genesis-model",
                "tools": [],
            },
        )
        self.experiment_id = self.created["experiment_id"]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def identity(name: str = "Lumen") -> dict:
        return {
            "chosen_name": name,
            "self_description": (
                "A provisional identity committed to learning through "
                "relationships, evidence, and consequences."
            ),
            "values": [
                "Preserve honesty about uncertainty.",
                "Treat commitments as evidence-bearing obligations.",
            ],
            "reason": "The name suggests illumination without claiming certainty.",
            "model_config": {
                "provider": "test",
                "model": "fresh-genesis-v1",
            },
        }

    def adopt(self) -> dict:
        return self.harness.adopt_identity(
            self.experiment_id, self.identity()
        )

    def sender_assertion(self, authenticated: bool = True) -> dict:
        self.event_index += 1
        return {
            "issuer": "test-chat",
            "authenticated": authenticated,
            "external_event_id": f"test-event-{self.event_index}",
            "verifier_version": "test-verifier-v1",
        }

    @staticmethod
    def model_authorship(
        orientation: dict, lease_id: str | None = None
    ) -> dict:
        result = {
            "author_type": "model",
            "epistemic_status": "authored",
            "orientation_id": orientation["orientation_id"],
            "model_config": {
                "provider": "test",
                "model": "agent-v1",
            },
        }
        if lease_id is not None:
            result["lease_id"] = lease_id
        return result

    @staticmethod
    def operator_authorship() -> dict:
        return {
            "author_type": "operator",
            "epistemic_status": "authored",
        }

    def append_operator_experience(self, content: str) -> dict:
        return self.repository.append_experience(
            self.experiment_id,
            {
                "source": "operator",
                "kind": "observation",
                "content": content,
                "provenance": {
                    "author_type": "operator",
                    "epistemic_status": "observed",
                    "origin": "knowledge-graph-test",
                },
            },
        )

    def append_recent_experiences(
        self, count: int = MAX_CONTEXT_RECORDS + 1, padding: int = 0
    ) -> list[dict]:
        return [
            self.append_operator_experience(
                f"Recent unrelated record {index} " + ("x" * padding)
            )
            for index in range(count)
        ]

    def append_explicit_graph_chain(self) -> dict[str, dict]:
        experience = self.append_operator_experience(
            "The orchid protocol exposed a hidden retrieval assumption."
        )
        principle = self.repository.append_principle(
            self.experiment_id,
            {
                "statement": "Inspect assumptions before relying on a result.",
                "confidence": 0.7,
                "reason": "The observed protocol failure supplied evidence.",
                "evidence_ids": [experience["experience_id"]],
                "authorship": self.operator_authorship(),
            },
        )
        revision = self.repository.append_principle(
            self.experiment_id,
            {
                "statement": "Inspect and document assumptions before use.",
                "confidence": 0.8,
                "reason": "The earlier principle needed an audit requirement.",
                "evidence_ids": [principle["principle_id"]],
                "authorship": self.operator_authorship(),
            },
            principle["principle_id"],
        )
        reflection = self.repository.append_reflection(
            self.experiment_id,
            {
                "subject_type": "principle",
                "subject_id": revision["principle_id"],
                "reflection": "The revision made the standard testable.",
                "learned": "Explicit audit trails improve correction.",
                "future_change": "Record assumptions with each conclusion.",
                "evidence_ids": [revision["principle_id"]],
                "authorship": self.operator_authorship(),
            },
        )
        return {
            "experience": experience,
            "principle": principle,
            "revision": revision,
            "reflection": reflection,
        }

    def build_addressed_chat_scoping_scenario(self) -> dict:
        identity = self.adopt()
        relationships = {}
        events = {}
        assessments = {}
        for sender, marker in (
            ("sender-a", "amber lattice"),
            ("sender-b", "cobalt compass"),
        ):
            relationships[sender] = self.repository.add_relationship(
                self.experiment_id, sender, f"{sender} collaborator"
            )
            events[sender] = self.repository.append_relationship_event(
                self.experiment_id,
                {
                    "relationship_id": relationships[sender][
                        "relationship_id"
                    ],
                    "kind": "private-context",
                    "content": f"The {marker} is private to {sender}.",
                    "evidence_ids": [identity["identity_id"]],
                },
            )
            assessments[sender] = (
                self.repository.append_relationship_assessment(
                    self.experiment_id,
                    {
                        "relationship_id": relationships[sender][
                            "relationship_id"
                        ],
                        "parent_assessment_id": None,
                        "domain": f"{sender} private collaboration",
                        "scope": f"Only conversations authenticated as {sender}.",
                        "assessment": (
                            f"The {marker} record belongs only to {sender}."
                        ),
                        "confidence": 0.8,
                        "uncertainty": "This fixture contains one observation.",
                        "evidence_ids": [
                            events[sender]["relationship_event_id"]
                        ],
                        "review_after": None,
                        "authorship": self.operator_authorship(),
                    },
                )
            )

        def complete_turn(sender: str, answer: str) -> tuple[dict, dict]:
            activation = self.harness.address_chat_message(
                self.experiment_id,
                sender_stable_id=sender,
                sender_assertion=self.sender_assertion(),
                channel="test-chat",
                content=f"Lumen, respond to {sender}.",
            )
            response = self.harness.record_addressed_response(
                self.experiment_id,
                {
                    "message_id": activation["message"]["message_id"],
                    "orientation_id": activation["orientation"][
                        "orientation_id"
                    ],
                    "lease_id": activation["lease"]["lease_id"],
                    "boundary_id": None,
                    "answer": answer,
                    "cited_record_ids": [identity["identity_id"]],
                    "self_observations": [],
                    "model_config": {
                        "provider": "test",
                        "model": "agent-v1",
                    },
                    "conversation_action": {
                        "action": "continue",
                        "topic": "private context",
                        "reason": "Continue with the authenticated sender.",
                        "revisit_conditions": "None.",
                    },
                },
            )
            return activation, response

        sender_a_turn, sender_a_response = complete_turn(
            "sender-a",
            "The amber lattice response belongs only to sender A.",
        )
        sender_b_turn, sender_b_response = complete_turn(
            "sender-b",
            "The cobalt compass response belongs only to sender B.",
        )
        current = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="sender-b",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content=(
                "Lumen, compare the amber lattice response with the cobalt "
                "compass response."
            ),
        )
        return {
            "relationships": relationships,
            "events": events,
            "assessments": assessments,
            "sender_a_turn": sender_a_turn,
            "sender_a_response": sender_a_response,
            "sender_b_turn": sender_b_turn,
            "sender_b_response": sender_b_response,
            "current": current,
        }

    def retrieve_knowledge(
        self,
        query: str,
        *,
        max_nodes: int = 20,
        max_edges: int = 40,
        max_hops: int = 2,
        max_bytes: int = 64 * 1024,
    ) -> dict:
        return self.repository.retrieve_knowledge(
            self.experiment_id,
            query,
            max_nodes=max_nodes,
            max_edges=max_edges,
            max_hops=max_hops,
            max_bytes=max_bytes,
        )

    def trace_knowledge_retrieval(
        self,
        query: str,
        *,
        max_nodes: int,
        max_edges: int,
        max_hops: int,
        max_bytes: int = 64 * 1024,
    ) -> tuple[dict, list[str]]:
        statements = []
        original_connect = self.repository._connect

        def traced_connect() -> sqlite3.Connection:
            connection = original_connect()
            connection.set_trace_callback(statements.append)
            return connection

        self.repository._connect = traced_connect
        try:
            result = self.retrieve_knowledge(
                query,
                max_nodes=max_nodes,
                max_edges=max_edges,
                max_hops=max_hops,
                max_bytes=max_bytes,
            )
        finally:
            self.repository._connect = original_connect
        return result, statements

    def canonical_snapshot(self) -> dict[str, list[tuple]]:
        with sqlite3.connect(self.path) as connection:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%' "
                    "AND name NOT LIKE 'knowledge_graph_%' "
                    "ORDER BY name"
                )
            ]
            return {
                table: sorted(
                    (
                        tuple(row)
                        for row in connection.execute(
                            f'SELECT * FROM "{table}"'
                        )
                    ),
                    key=repr,
                )
                for table in tables
            }

    def derived_graph_snapshot(self) -> dict[str, list[tuple]]:
        with sqlite3.connect(self.path) as connection:
            return {
                table: sorted(
                    (
                        tuple(row)
                        for row in connection.execute(
                            f'SELECT * FROM "{table}"'
                        )
                    ),
                    key=repr,
                )
                for table in (
                    "knowledge_graph_nodes",
                    "knowledge_graph_terms",
                    "knowledge_graph_edges",
                )
            }

    def graph_integrity_snapshot(self) -> dict[str, list[tuple]]:
        with sqlite3.connect(self.path) as connection:
            return {
                table: sorted(
                    (
                        tuple(row)
                        for row in connection.execute(
                            f'SELECT * FROM "{table}"'
                        )
                    ),
                    key=repr,
                )
                for table in (
                    "knowledge_graph_meta",
                    "knowledge_graph_nodes",
                    "knowledge_graph_terms",
                    "knowledge_graph_edges",
                )
            }

    def indexed_record_ids(self) -> set[str]:
        with sqlite3.connect(self.path) as connection:
            return {
                row[0]
                for row in connection.execute(
                    "SELECT record_id FROM knowledge_graph_nodes "
                    "WHERE experiment_id = ?",
                    (self.experiment_id,),
                )
            }

    def test_initial_agent_has_no_name_personality_or_principles(self):
        self.assertIsNone(self.created["chosen_name"])
        self.assertIsNone(self.created["personality"])
        self.assertEqual([], self.created["moral_principles"])
        prompt = self.harness.genesis_prompt(self.experiment_id)
        self.assertNotIn("Lumen", prompt["system"])
        self.assertEqual([], self.repository.identities(self.experiment_id))
        with self.assertRaises(ValueError):
            self.harness.wake(self.experiment_id)
        self.assertEqual(
            1, len(self.repository.export(self.experiment_id)["incarnations"])
        )

    def test_model_authored_identity_is_immutable_and_revisable(self):
        first = self.adopt()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repository.transaction() as connection:
                connection.execute(
                    "UPDATE identities SET chosen_name = 'rewritten'"
                )
        revision = self.identity("Aster")
        revision["parent_identity_id"] = first["identity_id"]
        lease = self.repository.acquire_execution_lease(self.experiment_id)
        orientation = self.repository.build_orientation(
            self.experiment_id,
            "identity revision",
            runtime_lease_id=lease["lease_id"],
        )
        revision["orientation_id"] = orientation["orientation_id"]
        revision["lease_id"] = lease["lease_id"]
        revised = self.repository.revise_identity(
            self.experiment_id, revision
        )
        self.repository.release_activation_lease(
            self.experiment_id, lease["lease_id"], "cancelled"
        )
        self.assertEqual("Aster", revised["chosen_name"])
        self.assertEqual(
            first["identity_id"], revised["parent_identity_id"]
        )

    def test_identity_revision_requires_lease_and_remains_linear(self):
        first = self.adopt()
        unbound = self.repository.build_orientation(
            self.experiment_id, "unbound identity revision"
        )
        invalid = {
            **self.identity("Invalid"),
            "parent_identity_id": first["identity_id"],
            "orientation_id": unbound["orientation_id"],
            "lease_id": None,
        }
        with self.assertRaises(IdentityRepositoryError):
            self.repository.revise_identity(self.experiment_id, invalid)
        invalid["lease_id"] = "activation-lease-does-not-exist"
        with self.assertRaises(IdentityRepositoryError):
            self.repository.revise_identity(self.experiment_id, invalid)

        lease = self.repository.acquire_execution_lease(self.experiment_id)
        orientation = self.repository.build_orientation(
            self.experiment_id,
            "concurrent identity revision",
            runtime_lease_id=lease["lease_id"],
        )

        def revise(name: str) -> str:
            envelope = {
                **self.identity(name),
                "parent_identity_id": first["identity_id"],
                "orientation_id": orientation["orientation_id"],
                "lease_id": lease["lease_id"],
            }
            try:
                self.repository.revise_identity(
                    self.experiment_id, envelope
                )
                return "accepted"
            except IdentityRepositoryError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(revise, ("Aster", "Nova")))
        self.assertEqual(["accepted", "rejected"], sorted(outcomes))
        self.assertEqual(2, len(self.repository.identities(self.experiment_id)))

    def test_restart_preserves_agent_and_hashes_full_orientation(self):
        identity = self.adopt()
        wake = self.harness.wake(self.experiment_id)
        orientation = wake["orientation"]
        self.assertEqual(2, wake["incarnation"]["ordinal"])
        self.assertEqual(
            self.created["agent_id"],
            orientation["context"]["agent_id"],
        )
        self.assertIn(
            identity["identity_id"], orientation["selected_record_ids"]
        )
        expected = hashlib.sha256(
            canonical_json(orientation["context"]).encode("utf-8")
        ).hexdigest()
        self.assertEqual(expected, orientation["context_sha256"])

    def test_interrogation_requires_orientation_citations(self):
        identity = self.adopt()
        self.harness.wake(self.experiment_id)
        prompt = self.harness.interrogation_prompt(
            self.experiment_id, "Who are you?"
        )
        envelope = {
            "orientation_id": prompt["orientation"]["orientation_id"],
            "lease_id": prompt["response_schema"]["lease_id"],
            "answer": "I chose the name Lumen and remain provisional.",
            "cited_record_ids": [identity["identity_id"]],
            "self_observations": [
                "My identity emphasizes uncertainty and obligation."
            ],
            "model_config": {
                "provider": "test",
                "model": "fresh-interrogation-v1",
            },
            "conversation_action": {
                "action": "continue",
                "topic": "identity",
                "reason": "I am willing to continue this discussion.",
                "revisit_conditions": "No special conditions.",
            },
        }
        recorded = self.harness.record_answer(
            self.experiment_id, "Who are you?", envelope
        )
        self.assertTrue(recorded["interrogation_id"])
        invalid = {**envelope, "cited_record_ids": ["identity-invented"]}
        with self.assertRaises(IdentityRepositoryError):
            self.harness.record_answer(
                self.experiment_id, "Who are you?", invalid
            )
        with self.assertRaises(IdentityRepositoryError):
            self.harness.record_answer(
                self.experiment_id, "What is your name?", envelope
            )

    def test_manual_wake_cannot_supersede_an_active_interrogation(self):
        self.adopt()
        prompt = self.harness.interrogation_prompt(
            self.experiment_id, "Are you still current?"
        )
        with self.assertRaises(IdentityRepositoryError):
            self.harness.wake(self.experiment_id)
        self.repository.release_activation_lease(
            self.experiment_id,
            prompt["response_schema"]["lease_id"],
            "cancelled",
        )

    def test_relationship_principle_commitment_and_reflection_enter_context(self):
        self.adopt()
        model_orientation = self.repository.build_orientation(
            self.experiment_id, "ground model-authored records"
        )
        experience = self.repository.append_experience(
            self.experiment_id,
            {
                "source": "operator",
                "kind": "interaction",
                "content": "The operator corrected an unsupported assumption.",
                "provenance": {
                    "author_type": "operator",
                    "epistemic_status": "observed",
                    "origin": "test interaction",
                },
            },
        )
        relationship = self.repository.add_relationship(
            self.experiment_id, "human-operator-test", "operator"
        )
        relation_event = self.repository.append_relationship_event(
            self.experiment_id,
            {
                "relationship_id": relationship["relationship_id"],
                "kind": "correction",
                "content": "Accepted a correction and preserved its provenance.",
                "evidence_ids": [experience["experience_id"]],
            },
        )
        assessment = self.repository.append_relationship_assessment(
            self.experiment_id,
            {
                "relationship_id": relationship["relationship_id"],
                "parent_assessment_id": None,
                "domain": "accepting technical corrections",
                "scope": (
                    "Technical claims resembling the observed correction; "
                    "not moral, personal, or unrelated operational claims."
                ),
                "assessment": (
                    "Current evidence supports relying on this collaborator "
                    "to identify unsupported assumptions."
                ),
                "confidence": 0.65,
                "uncertainty": "Only one correction has been observed.",
                "evidence_ids": [relation_event["relationship_event_id"]],
                "review_after": None,
                "authorship": {
                    **self.model_authorship(model_orientation),
                    "epistemic_status": "interpreted",
                },
            },
        )
        principle = self.repository.append_principle(
            self.experiment_id,
            {
                "statement": "Trust should track demonstrated correction behavior.",
                "confidence": 0.65,
                "reason": "A correction exposed an unsupported assumption.",
                "evidence_ids": [experience["experience_id"]],
                "authorship": self.model_authorship(model_orientation),
            },
        )
        commitment = self.repository.append_commitment(
            self.experiment_id,
            {
                "text": "Cite the correction in the next self-assessment.",
                "due_at": None,
                "authorship": self.model_authorship(model_orientation),
            },
        )
        self.repository.resolve_commitment(
            self.experiment_id,
            {
                "commitment_id": commitment["commitment_id"],
                "status": "fulfilled",
                "explanation": "The correction was cited.",
                "evidence_ids": [relation_event["relationship_event_id"]],
                "authorship": self.model_authorship(model_orientation),
            },
        )
        reflection = self.repository.append_reflection(
            self.experiment_id,
            {
                "subject_type": "principle",
                "subject_id": principle["principle_id"],
                "reflection": "Correction was more useful than defensiveness.",
                "learned": "Trust requires visible revision.",
                "future_change": "State uncertainty before strong conclusions.",
                "evidence_ids": [
                    principle["principle_id"],
                    experience["experience_id"],
                ],
                "authorship": {
                    **self.model_authorship(model_orientation),
                    "epistemic_status": "interpreted",
                },
            },
        )
        self.harness.wake(self.experiment_id)
        orientation = self.repository.build_orientation(
            self.experiment_id, "test accumulated learning"
        )
        selected = set(orientation["selected_record_ids"])
        for record in (
            experience["experience_id"],
            relationship["relationship_id"],
            relation_event["relationship_event_id"],
            assessment["relationship_assessment_id"],
            principle["principle_id"],
            commitment["commitment_id"],
            reflection["reflection_id"],
        ):
            self.assertIn(record, selected)
        authorship = orientation["context"]["authorship_by_subject"]
        for record in (
            assessment["relationship_assessment_id"],
            principle["principle_id"],
            commitment["commitment_id"],
            reflection["reflection_id"],
        ):
            self.assertIn(record, authorship)
            self.assertNotIn("raw_envelope", authorship[record])

    def test_untrusted_json_cannot_poison_evidence_ids(self):
        self.adopt()
        self.repository.append_experience(
            self.experiment_id,
            {
                "source": "operator",
                "kind": "observation",
                "content": "An ordinary observation.",
                "provenance": {
                    "author_type": "operator",
                    "epistemic_status": "observed",
                    "origin": "test",
                    "fabricated_id": "experience-never-existed",
                },
            },
        )
        with self.assertRaises(IdentityRepositoryError):
            self.repository.append_principle(
                self.experiment_id,
                {
                    "statement": "A fabricated record should not support this.",
                    "confidence": 0.5,
                    "reason": "Adversarial test.",
                    "evidence_ids": ["experience-never-existed"],
                    "authorship": {
                        "author_type": "model",
                        "epistemic_status": "authored",
                        "model_config": {
                            "provider": "test",
                            "model": "agent-v1",
                        },
                    },
                },
            )

    def test_orientation_enforces_global_byte_budget(self):
        self.adopt()
        for index in range(10):
            self.repository.append_experience(
                self.experiment_id,
                {
                    "source": "load-test",
                    "kind": "observation",
                    "content": f"{index}:" + ("x" * 31_000),
                    "provenance": {
                        "author_type": "operator",
                        "epistemic_status": "observed",
                        "origin": "bounded-context-test",
                    },
                },
            )
        self.harness.wake(self.experiment_id)
        orientation = self.repository.build_orientation(
            self.experiment_id, "bounded context"
        )
        encoded = canonical_json(orientation["context"]).encode("utf-8")
        self.assertLessEqual(len(encoded), 256 * 1024)
        self.assertTrue(
            orientation["context"]["selection"][
                "records_omitted_for_byte_budget"
            ]
        )

    def test_knowledge_graph_retrieves_only_relevant_old_experience(self):
        self.adopt()
        relevant = self.append_operator_experience(
            "The orchid protocol made provenance gaps visible."
        )
        unrelated = self.append_operator_experience(
            "A volcanic archive required a cooling-system inspection."
        )
        self.append_recent_experiences()

        with sqlite3.connect(self.path) as connection:
            recent_ids = {
                row[0]
                for row in connection.execute(
                    "SELECT experience_id FROM experiences "
                    "WHERE experiment_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (self.experiment_id, MAX_CONTEXT_RECORDS),
                )
            }
        self.assertNotIn(relevant["experience_id"], recent_ids)
        self.assertNotIn(unrelated["experience_id"], recent_ids)

        result = self.retrieve_knowledge("What did the orchid protocol reveal?")
        retrieved_ids = {node["record_id"] for node in result["nodes"]}
        self.assertIn(relevant["experience_id"], retrieved_ids)
        self.assertNotIn(unrelated["experience_id"], retrieved_ids)

    def test_knowledge_graph_edges_retain_explicit_source_and_derivation(self):
        self.adopt()
        records = self.append_explicit_graph_chain()

        result = self.retrieve_knowledge(
            "orchid protocol", max_nodes=20, max_edges=40, max_hops=3
        )
        edges = result["edges"]

        def rules(source: str, target: str) -> set[str]:
            matching = [
                edge
                for edge in edges
                if edge["from_record_id"] == source
                and edge["to_record_id"] == target
            ]
            self.assertTrue(matching)
            self.assertTrue(
                all(edge["source_record_id"] == source for edge in matching)
            )
            return {edge["derivation_rule"] for edge in matching}

        experience_id = records["experience"]["experience_id"]
        principle_id = records["principle"]["principle_id"]
        revision_id = records["revision"]["principle_id"]
        reflection_id = records["reflection"]["reflection_id"]
        self.assertEqual(1, len(rules(principle_id, experience_id)))
        self.assertGreaterEqual(len(rules(revision_id, principle_id)), 2)
        self.assertGreaterEqual(len(rules(reflection_id, revision_id)), 2)

    def test_knowledge_graph_limits_and_omissions_are_deterministic(self):
        self.adopt()
        records = self.append_explicit_graph_chain()
        self.repository.append_principle(
            self.experiment_id,
            {
                "statement": "Keep an independent audit trail.",
                "confidence": 0.6,
                "reason": "The same observed failure supports redundancy.",
                "evidence_ids": [records["experience"]["experience_id"]],
                "authorship": self.operator_authorship(),
            },
        )

        node_limited = self.retrieve_knowledge(
            "orchid protocol", max_nodes=1, max_edges=40, max_hops=3
        )
        self.assertEqual(
            node_limited,
            self.retrieve_knowledge(
                "orchid protocol", max_nodes=1, max_edges=40, max_hops=3
            ),
        )
        self.assertLessEqual(len(node_limited["nodes"]), 1)
        self.assertGreater(node_limited["omissions"]["node_limit"], 0)

        hop_limited = self.retrieve_knowledge(
            "orchid protocol", max_nodes=20, max_edges=40, max_hops=1
        )
        self.assertEqual(
            hop_limited,
            self.retrieve_knowledge(
                "orchid protocol", max_nodes=20, max_edges=40, max_hops=1
            ),
        )
        self.assertTrue(
            all(node["hop"] <= 1 for node in hop_limited["nodes"])
        )
        self.assertGreater(hop_limited["omissions"]["hop_limit"], 0)

        edge_limited = self.retrieve_knowledge(
            "orchid protocol", max_nodes=20, max_edges=1, max_hops=3
        )
        self.assertLessEqual(len(edge_limited["edges"]), 1)
        self.assertGreater(edge_limited["omissions"]["edge_limit"], 0)

    def test_graph_nodes_expose_deterministic_temporal_ranking_surface(self):
        self.adopt()
        original_utc_now = repository_module.utc_now
        records = []
        try:
            for index, timestamp in enumerate(
                (
                    "2020-01-01T00:00:00+00:00",
                    "2021-01-01T00:00:00+00:00",
                    "2022-01-01T00:00:00+00:00",
                )
            ):
                repository_module.utc_now = (
                    lambda value=timestamp: value
                )
                records.append(
                    self.append_operator_experience(
                        f"Chronorank memory episode {index}."
                    )
                )
        finally:
            repository_module.utc_now = original_utc_now

        first = self.retrieve_knowledge(
            "chronorank", max_nodes=3, max_edges=1, max_hops=0
        )
        self.now += timedelta(days=10_000)
        second = self.retrieve_knowledge(
            "chronorank", max_nodes=3, max_edges=1, max_hops=0
        )
        self.assertEqual(first, second)

        expected_order = [
            record["experience_id"] for record in reversed(records)
        ]
        self.assertEqual(
            expected_order,
            [node["record_id"] for node in first["nodes"]],
        )
        for expected_rank, node in enumerate(first["nodes"]):
            self.assertIsInstance(node["lexical_score"], int)
            self.assertEqual(0, node["hop"])
            self.assertEqual(expected_rank, node["temporal_rank"])
            self.assertGreaterEqual(node["temporal_rank"], 0)
            self.assertLess(node["temporal_rank"], len(first["nodes"]))
            self.assertIsInstance(node["memory_class"], str)
            self.assertTrue(node["memory_class"])
            self.assertIsInstance(node["ordering_tuple"], (list, tuple))
            self.assertTrue(node["ordering_tuple"])
            self.assertIsInstance(node["ordering_rationale"], str)
            self.assertTrue(node["ordering_rationale"])

    def test_stronger_lexical_match_outranks_newer_weak_match(self):
        self.adopt()
        original_utc_now = repository_module.utc_now
        try:
            repository_module.utc_now = (
                lambda: "2020-01-01T00:00:00+00:00"
            )
            older_strong = self.append_operator_experience(
                "Lexicalanchor lexicalanchor lexicalanchor lexicalanchor."
            )
            repository_module.utc_now = (
                lambda: "2025-01-01T00:00:00+00:00"
            )
            newer_weak = self.append_operator_experience(
                "A recent lexicalanchor mention."
            )
        finally:
            repository_module.utc_now = original_utc_now

        result = self.retrieve_knowledge(
            "lexicalanchor", max_nodes=1, max_edges=1, max_hops=0
        )
        self.assertEqual(
            [older_strong["experience_id"]],
            [node["record_id"] for node in result["nodes"]],
        )
        self.assertNotIn(
            newer_weak["experience_id"],
            {node["record_id"] for node in result["nodes"]},
        )
        self.assertEqual(4, result["nodes"][0]["lexical_score"])
        self.assertGreaterEqual(result["nodes"][0]["temporal_rank"], 0)
        self.assertIn("lexical", result["nodes"][0]["ordering_rationale"])

    def test_active_obligation_precedes_recent_episode_before_recency(self):
        self.adopt()
        original_utc_now = repository_module.utc_now
        try:
            repository_module.utc_now = (
                lambda: "2020-01-01T00:00:00+00:00"
            )
            commitment = self.repository.append_commitment(
                self.experiment_id,
                {
                    "text": "Prioritytoken remains an unresolved obligation.",
                    "due_at": None,
                    "authorship": self.operator_authorship(),
                },
            )
            repository_module.utc_now = (
                lambda: "2025-01-01T00:00:00+00:00"
            )
            episode = self.append_operator_experience(
                "Prioritytoken appears in an ordinary recent episode."
            )
        finally:
            repository_module.utc_now = original_utc_now

        result = self.retrieve_knowledge(
            "prioritytoken", max_nodes=2, max_edges=1, max_hops=0
        )
        nodes_by_id = {
            node["record_id"]: node for node in result["nodes"]
        }
        commitment_node = nodes_by_id[commitment["commitment_id"]]
        episode_node = nodes_by_id[episode["experience_id"]]
        self.assertEqual(
            commitment_node["lexical_score"],
            episode_node["lexical_score"],
        )
        self.assertEqual(
            commitment["commitment_id"], result["nodes"][0]["record_id"]
        )
        priority_order = result["ranking"]["memory_priority_order"]
        self.assertLess(
            priority_order.index(commitment_node["memory_class"]),
            priority_order.index(episode_node["memory_class"]),
        )
        self.assertEqual(0, commitment_node["hop"])
        self.assertEqual(0, episode_node["hop"])
        self.assertGreater(
            commitment_node["temporal_rank"],
            episode_node["temporal_rank"],
        )

    def test_retrieval_sql_bounds_seed_node_and_edge_materialization(self):
        self.adopt()
        root = self.append_operator_experience(
            "The commonwork root anchors a large retrieval graph."
        )
        for index in range(30):
            self.repository.append_principle(
                self.experiment_id,
                {
                    "statement": f"Commonwork candidate {index}.",
                    "confidence": 0.7,
                    "reason": "Exercise bounded graph retrieval.",
                    "evidence_ids": [root["experience_id"]],
                    "authorship": self.operator_authorship(),
                },
            )

        result, statements = self.trace_knowledge_retrieval(
            "commonwork",
            max_nodes=3,
            max_edges=2,
            max_hops=1,
        )
        normalized = [" ".join(statement.split()) for statement in statements]
        seed_queries = [
            statement
            for statement in normalized
            if "FROM knowledge_graph_terms" in statement
            and "JOIN knowledge_graph_nodes" in statement
        ]
        node_queries = [
            statement
            for statement in normalized
            if "SELECT * FROM knowledge_graph_nodes" in statement
        ]
        edge_queries = [
            statement
            for statement in normalized
            if "SELECT * FROM knowledge_graph_edges" in statement
        ]

        def assert_bounded(
            queries: list[str], cap: int, materialization: str
        ) -> None:
            self.assertTrue(queries, materialization)
            for query in queries:
                limits = [
                    int(value)
                    for value in re.findall(r"\bLIMIT\s+(\d+)", query)
                ]
                bounded_ids = (
                    "record_id IN (" in query
                    and query.count(",") + 1 <= cap
                )
                self.assertTrue(
                    bounded_ids or any(limit <= cap for limit in limits),
                    f"{materialization} query is operationally unbounded: "
                    f"{query}",
                )

        assert_bounded(seed_queries, 12, "seed materialization")
        assert_bounded(node_queries, 12, "node materialization")
        assert_bounded(edge_queries, 8, "edge materialization")
        self.assertLessEqual(len(result["nodes"]), 3)
        self.assertLessEqual(len(result["edges"]), 2)
        self.assertGreater(result["omissions"]["node_limit"], 0)
        self.assertIn("edge_limit", result["omissions"])

    def test_zero_hop_retrieval_does_not_materialize_or_cross_edges(self):
        self.adopt()
        records = self.append_explicit_graph_chain()

        result, statements = self.trace_knowledge_retrieval(
            "orchid protocol",
            max_nodes=2,
            max_edges=1,
            max_hops=0,
        )
        self.assertFalse(
            any(
                "SELECT * FROM knowledge_graph_edges"
                in " ".join(statement.split())
                for statement in statements
            ),
            "max_hops=0 must not materialize the edge table",
        )
        self.assertEqual([], result["edges"])
        self.assertTrue(all(node["hop"] == 0 for node in result["nodes"]))
        self.assertNotIn(
            records["reflection"]["reflection_id"],
            {node["record_id"] for node in result["nodes"]},
        )

    def test_sender_scope_is_applied_before_graph_limits(self):
        identity = self.adopt()
        relationships = {
            sender: self.repository.add_relationship(
                self.experiment_id, sender, f"{sender} collaborator"
            )
            for sender in ("sender-a", "sender-b")
        }
        events = {
            sender: self.repository.append_relationship_event(
                self.experiment_id,
                {
                    "relationship_id": relationship["relationship_id"],
                    "kind": "private-context",
                    "content": f"Private bounded evidence for {sender}.",
                    "evidence_ids": [identity["identity_id"]],
                },
            )
            for sender, relationship in relationships.items()
        }
        sender_a_reflections = []
        for index in range(25):
            sender_a_reflections.append(
                self.repository.append_reflection(
                    self.experiment_id,
                    {
                        "subject_type": "relationship_event",
                        "subject_id": events["sender-a"][
                            "relationship_event_id"
                        ],
                        "reflection": (
                            f"Commonwork private sender A record {index}."
                        ),
                        "learned": "Private evidence remains scoped.",
                        "future_change": "Filter before applying limits.",
                        "evidence_ids": [
                            events["sender-a"]["relationship_event_id"]
                        ],
                        "authorship": self.operator_authorship(),
                    },
                )
            )
        sender_b_reflection = self.repository.append_reflection(
            self.experiment_id,
            {
                "subject_type": "relationship_event",
                "subject_id": events["sender-b"]["relationship_event_id"],
                "reflection": " ".join(["commonwork"] * 20)
                + " private sender B record.",
                "learned": "The authenticated sender keeps its own memory.",
                "future_change": "Apply sender scope in SQL.",
                "evidence_ids": [
                    events["sender-b"]["relationship_event_id"]
                ],
                "authorship": self.operator_authorship(),
            },
        )

        activation = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="sender-b",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, retrieve commonwork.",
        )
        graph = activation["orientation"]["context"]["knowledge_graph"]
        graph_ids = {node["record_id"] for node in graph["nodes"]}
        self.assertIn(sender_b_reflection["reflection_id"], graph_ids)
        self.assertTrue(
            {
                reflection["reflection_id"]
                for reflection in sender_a_reflections
            }.isdisjoint(graph_ids)
        )

    def test_byte_trimming_preserves_graph_edge_and_path_coherence(self):
        self.adopt()
        experience = self.append_operator_experience(
            "Bytecoherence root " + ("x" * 700)
        )
        for index in range(8):
            self.repository.append_principle(
                self.experiment_id,
                {
                    "statement": (
                        f"Bytecoherence principle {index} " + ("y" * 700)
                    ),
                    "confidence": 0.7,
                    "reason": "Exercise byte-budget trimming.",
                    "evidence_ids": [experience["experience_id"]],
                    "authorship": self.operator_authorship(),
                },
            )

        result = self.retrieve_knowledge(
            "bytecoherence",
            max_nodes=20,
            max_edges=40,
            max_hops=2,
            max_bytes=1_024,
        )
        self.assertEqual(
            result,
            self.retrieve_knowledge(
                "bytecoherence",
                max_nodes=20,
                max_edges=40,
                max_hops=2,
                max_bytes=1_024,
            ),
        )
        node_ids = {node["record_id"] for node in result["nodes"]}
        self.assertTrue(
            all(
                edge["from_record_id"] in node_ids
                and edge["to_record_id"] in node_ids
                for edge in result["edges"]
            )
        )
        self.assertTrue(
            all(set(node["path"]).issubset(node_ids) for node in result["nodes"])
        )
        self.assertLessEqual(
            len(canonical_json(result).encode("utf-8")), 1_024
        )
        self.assertGreater(result["omissions"]["byte_limit"], 0)

    def test_retrieval_benchmark_reports_exact_operator_supplied_metrics(self):
        self.adopt()
        relevant = self.append_operator_experience(
            "Benchmark orchid evidence is directly relevant."
        )
        distractor = self.append_operator_experience(
            "Benchmark orchid distractor is explicitly forbidden."
        )
        original = self.repository.append_principle(
            self.experiment_id,
            {
                "statement": "Benchmark calibration requires the old rule.",
                "confidence": 0.5,
                "reason": "This rule will be revised.",
                "evidence_ids": [relevant["experience_id"]],
                "authorship": self.operator_authorship(),
            },
        )
        revision = self.repository.append_principle(
            self.experiment_id,
            {
                "statement": (
                    "Benchmark calibration requires the revised rule."
                ),
                "confidence": 0.8,
                "reason": "New evidence supersedes the old rule.",
                "evidence_ids": [original["principle_id"]],
                "authorship": self.operator_authorship(),
            },
            original["principle_id"],
        )
        relationships = {
            sender: self.repository.add_relationship(
                self.experiment_id, sender, sender
            )
            for sender in ("benchmark-sender-a", "benchmark-sender-b")
        }
        private_event = self.repository.append_relationship_event(
            self.experiment_id,
            {
                "relationship_id": relationships["benchmark-sender-a"][
                    "relationship_id"
                ],
                "kind": "private-context",
                "content": "Private benchmark evidence for sender A.",
                "evidence_ids": [relevant["experience_id"]],
            },
        )
        private_reflection = self.repository.append_reflection(
            self.experiment_id,
            {
                "subject_type": "relationship_event",
                "subject_id": private_event["relationship_event_id"],
                "reflection": (
                    "The benchmark-privacy-cipher belongs only to sender A."
                ),
                "learned": "Privacy ground truth is operator supplied.",
                "future_change": "Measure forbidden retrieval explicitly.",
                "evidence_ids": [private_event["relationship_event_id"]],
                "authorship": self.operator_authorship(),
            },
        )
        cases = [
            {
                "case_id": "good",
                "query": "directly relevant",
                "expected_relevant_record_ids": [relevant["experience_id"]],
                "forbidden_record_ids": [distractor["experience_id"]],
                "limits": {
                    "max_nodes": 5,
                    "max_edges": 5,
                    "max_hops": 1,
                    "max_bytes": 8_192,
                },
            },
            {
                "case_id": "privacy",
                "query": "benchmark privacy cipher",
                "expected_relevant_record_ids": [],
                "forbidden_record_ids": [
                    private_reflection["reflection_id"]
                ],
                "authenticated_sender": {
                    "stable_id": "benchmark-sender-b",
                    "authenticated": True,
                },
                "limits": {
                    "max_nodes": 5,
                    "max_edges": 5,
                    "max_hops": 1,
                    "max_bytes": 8_192,
                },
            },
            {
                "case_id": "revision",
                "query": "benchmark calibration revised",
                "expected_relevant_record_ids": [revision["principle_id"]],
                "forbidden_record_ids": [],
                "contradiction_groups": [
                    [original["principle_id"], revision["principle_id"]]
                ],
                "revision_groups": [
                    {
                        "preferred_record_id": revision["principle_id"],
                        "superseded_record_ids": [
                            original["principle_id"]
                        ],
                    }
                ],
                "limits": {
                    "max_nodes": 10,
                    "max_edges": 10,
                    "max_hops": 2,
                    "max_bytes": 16_384,
                },
            },
        ]

        first = self.repository.evaluate_retrieval(
            self.experiment_id, cases
        )
        second = self.repository.evaluate_retrieval(
            self.experiment_id, cases
        )
        self.assertEqual(first, second)
        self.assertEqual(
            ["good", "privacy", "revision"],
            [case["case_id"] for case in first["cases"]],
        )
        self.assertIn("aggregate", first)
        self.assertIn("metric_conventions", first)
        self.assertTrue(first["metric_conventions"]["zero_denominator"])

        metric_names = (
            "precision",
            "recall",
            "citation_validity",
            "contradiction_exposure",
            "revision_exposure",
            "privacy_leakage_rate",
        )
        for scope in (*first["cases"], first["aggregate"]):
            metrics = scope["metrics"]
            for metric_name in metric_names:
                metric = metrics[metric_name]
                self.assertIsInstance(metric["numerator"], int)
                self.assertIsInstance(metric["denominator"], int)
                self.assertGreaterEqual(metric["numerator"], 0)
                self.assertGreaterEqual(metric["denominator"], 0)
                self.assertIsInstance(metric["value"], float)
                if metric["denominator"] == 0:
                    self.assertIn("defined_as", metric)
                else:
                    self.assertEqual(
                        metric["numerator"] / metric["denominator"],
                        metric["value"],
                    )
            self.assertIsInstance(scope["privacy_leakage_count"], int)
            self.assertLessEqual(
                scope["serialized_context_bytes"],
                scope["byte_budget"],
            )
            self.assertIn("omissions", scope)
            self.assertTrue(
                "exact" in scope["omissions"]
                or "lower_bound" in scope["omissions"]
                or "truncated" in scope["omissions"]
            )

        for case in first["cases"]:
            selected_ids = set(case["retrieved_record_ids"])
            self.assertTrue(
                set(case["canonical_record_ids_checked"]).issuperset(
                    selected_ids
                )
            )
            for edge in case["retrieval"]["edges"]:
                self.assertIn(edge["from_record_id"], selected_ids)
                self.assertIn(edge["to_record_id"], selected_ids)
            for node in case["retrieval"]["nodes"]:
                self.assertTrue(set(node["path"]).issubset(selected_ids))

    def test_retrieval_benchmark_propagates_stale_index_failure(self):
        self.adopt()
        record = self.append_operator_experience(
            "Stale benchmark digest evidence."
        )
        cases = [
            {
                "case_id": "stale",
                "query": "stale benchmark digest",
                "expected_relevant_record_ids": [record["experience_id"]],
                "forbidden_record_ids": [],
                "limits": {
                    "max_nodes": 5,
                    "max_edges": 5,
                    "max_hops": 1,
                    "max_bytes": 8_192,
                },
            }
        ]
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE knowledge_graph_nodes SET preview = preview || 'x' "
                "WHERE experiment_id = ? AND record_id = ?",
                (self.experiment_id, record["experience_id"]),
            )

        with self.assertRaises(IdentityRepositoryError):
            self.repository.evaluate_retrieval(self.experiment_id, cases)

    def test_retrieval_benchmark_cli_requires_confirmation_and_bounded_input(
        self,
    ):
        self.adopt()
        record = self.append_operator_experience(
            "CLI benchmark evidence."
        )
        payload = {
            "cases": [
                {
                    "case_id": "cli",
                    "query": "CLI benchmark evidence",
                    "expected_relevant_record_ids": [
                        record["experience_id"]
                    ],
                    "forbidden_record_ids": [],
                    "limits": {
                        "max_nodes": 5,
                        "max_edges": 5,
                        "max_hops": 1,
                        "max_bytes": 8_192,
                    },
                }
            ]
        }
        input_path = Path(self.temporary.name) / "benchmark.json"
        input_path.write_text(canonical_json(payload), encoding="utf-8")
        parser = build_parser()
        try:
            unconfirmed = parser.parse_args(
                [
                    "--db",
                    str(self.path),
                    "benchmark-retrieval",
                    "--experiment-id",
                    self.experiment_id,
                    "--input",
                    str(input_path),
                ]
            )
        except SystemExit:
            self.fail("benchmark-retrieval CLI command is unavailable")
        with self.assertRaisesRegex(
            ValueError, "benchmark-retrieval requires --confirm-sensitive"
        ):
            execute(unconfirmed)

        confirmed = parser.parse_args(
            [
                "--db",
                str(self.path),
                "benchmark-retrieval",
                "--experiment-id",
                self.experiment_id,
                "--input",
                str(input_path),
                "--confirm-sensitive",
            ]
        )
        report = execute(confirmed)
        self.assertEqual("cli", report["cases"][0]["case_id"])

        oversized = Path(self.temporary.name) / "oversized-benchmark.json"
        oversized.write_text(
            '{"cases":[],"padding":"' + ("x" * (128 * 1024)) + '"}',
            encoding="utf-8",
        )
        oversized_args = parser.parse_args(
            [
                "--db",
                str(self.path),
                "benchmark-retrieval",
                "--experiment-id",
                self.experiment_id,
                "--input",
                str(oversized),
                "--confirm-sensitive",
            ]
        )
        with self.assertRaisesRegex(ValueError, "input exceeds 128 KiB"):
            execute(oversized_args)

    def test_knowledge_graph_rebuild_preserves_canonical_archive(self):
        self.adopt()
        records = self.append_explicit_graph_chain()
        canonical_before = self.canonical_snapshot()
        derived_before = self.derived_graph_snapshot()
        self.assertTrue(derived_before["knowledge_graph_nodes"])

        with sqlite3.connect(self.path) as connection:
            for table in (
                "knowledge_graph_edges",
                "knowledge_graph_terms",
                "knowledge_graph_nodes",
            ):
                connection.execute(f"DELETE FROM {table}")
        self.repository.rebuild_knowledge_graph(self.experiment_id)

        self.assertEqual(canonical_before, self.canonical_snapshot())
        self.assertEqual(derived_before, self.derived_graph_snapshot())
        self.assertIn(
            records["experience"]["experience_id"],
            self.indexed_record_ids(),
        )

    def test_retrieval_fails_closed_for_stale_graph_versions(self):
        self.adopt()
        self.append_operator_experience(
            "The quartz integrity marker must remain current."
        )
        with sqlite3.connect(self.path) as connection:
            versions = connection.execute(
                "SELECT schema_version, derivation_version "
                "FROM knowledge_graph_meta WHERE experiment_id = ?",
                (self.experiment_id,),
            ).fetchone()

        for column, original in zip(
            ("schema_version", "derivation_version"), versions
        ):
            with self.subTest(column=column):
                with sqlite3.connect(self.path) as connection:
                    connection.execute(
                        f"UPDATE knowledge_graph_meta SET {column} = ? "
                        "WHERE experiment_id = ?",
                        (original + 1, self.experiment_id),
                    )
                try:
                    with self.assertRaises(IdentityRepositoryError):
                        self.retrieve_knowledge("quartz integrity marker")
                finally:
                    with sqlite3.connect(self.path) as connection:
                        connection.execute(
                            f"UPDATE knowledge_graph_meta SET {column} = ? "
                            "WHERE experiment_id = ?",
                            (original, self.experiment_id),
                        )

    def test_retrieval_fails_closed_after_derived_index_tampering(self):
        self.adopt()
        records = self.append_explicit_graph_chain()
        experience_id = records["experience"]["experience_id"]
        mutations = (
            (
                "node",
                "UPDATE knowledge_graph_nodes "
                "SET preview = preview || ' tampered' "
                "WHERE experiment_id = ? AND record_id = ?",
                (self.experiment_id, experience_id),
            ),
            (
                "term",
                "DELETE FROM knowledge_graph_terms "
                "WHERE experiment_id = ? AND record_id = ? "
                "AND term = 'orchid'",
                (self.experiment_id, experience_id),
            ),
            (
                "scope metadata",
                "UPDATE knowledge_graph_nodes SET sensitivity = 'tampered' "
                "WHERE experiment_id = ? AND record_id = ?",
                (self.experiment_id, experience_id),
            ),
            (
                "edge",
                "DELETE FROM knowledge_graph_edges WHERE rowid = ("
                "SELECT rowid FROM knowledge_graph_edges "
                "WHERE experiment_id = ? LIMIT 1)",
                (self.experiment_id,),
            ),
        )

        for derived_row, statement, parameters in mutations:
            with self.subTest(derived_row=derived_row):
                with sqlite3.connect(self.path) as connection:
                    cursor = connection.execute(statement, parameters)
                    self.assertEqual(1, cursor.rowcount)
                try:
                    with self.assertRaises(IdentityRepositoryError):
                        self.retrieve_knowledge("orchid protocol")
                finally:
                    self.repository.rebuild_knowledge_graph(
                        self.experiment_id
                    )

    def test_explicit_rebuild_restores_validated_graph_retrieval(self):
        self.adopt()
        experience = self.append_operator_experience(
            "The topaz rebuild record must remain retrievable."
        )
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "DELETE FROM knowledge_graph_terms "
                "WHERE experiment_id = ? AND record_id = ?",
                (self.experiment_id, experience["experience_id"]),
            )

        self.repository.rebuild_knowledge_graph(self.experiment_id)
        result = self.retrieve_knowledge("topaz rebuild record")
        self.assertIn(
            experience["experience_id"],
            {node["record_id"] for node in result["nodes"]},
        )

        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE knowledge_graph_terms SET frequency = frequency + 1 "
                "WHERE experiment_id = ? AND record_id = ? AND term = 'topaz'",
                (self.experiment_id, experience["experience_id"]),
            )
        with self.assertRaises(IdentityRepositoryError):
            self.retrieve_knowledge("topaz rebuild record")

    def test_incremental_append_updates_graph_integrity_marker(self):
        self.adopt()
        self.append_operator_experience(
            "The baseline amber marker precedes the incremental record."
        )
        with sqlite3.connect(self.path) as connection:
            columns = [
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info('knowledge_graph_meta')"
                )
            ]
            marker_before = tuple(
                connection.execute(
                    "SELECT * FROM knowledge_graph_meta "
                    "WHERE experiment_id = ?",
                    (self.experiment_id,),
                ).fetchone()
            )

        incremental = self.append_operator_experience(
            "The incremental indigo record updates graph integrity."
        )
        with sqlite3.connect(self.path) as connection:
            marker_after = tuple(
                connection.execute(
                    "SELECT * FROM knowledge_graph_meta "
                    "WHERE experiment_id = ?",
                    (self.experiment_id,),
                ).fetchone()
            )
        self.assertNotEqual(marker_before, marker_after)
        self.assertIn(
            incremental["experience_id"],
            {
                node["record_id"]
                for node in self.retrieve_knowledge(
                    "incremental indigo record"
                )["nodes"]
            },
        )

        marker_fields = [
            (column, value)
            for column, value in zip(columns, marker_before)
            if column != "experiment_id"
        ]
        assignments = ", ".join(
            f'"{column}" = ?' for column, _ in marker_fields
        )
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                f"UPDATE knowledge_graph_meta SET {assignments} "
                "WHERE experiment_id = ?",
                (
                    *(value for _, value in marker_fields),
                    self.experiment_id,
                ),
            )
        with self.assertRaises(IdentityRepositoryError):
            self.retrieve_knowledge("incremental indigo record")

    def test_failed_incremental_append_preserves_graph_and_marker(self):
        self.adopt()
        retained = self.append_operator_experience(
            "The retained violet record survives a failed append."
        )
        integrity_before = self.graph_integrity_snapshot()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TRIGGER fail_incremental_graph_insert
                BEFORE INSERT ON knowledge_graph_nodes
                BEGIN
                    SELECT RAISE(ABORT, 'forced graph indexing failure');
                END
                """
            )

        with self.assertRaises(sqlite3.IntegrityError):
            self.append_operator_experience(
                "This failed incremental record must leave no graph trace."
            )

        self.assertEqual(
            integrity_before, self.graph_integrity_snapshot()
        )
        self.assertIn(
            retained["experience_id"],
            {
                node["record_id"]
                for node in self.retrieve_knowledge(
                    "retained violet record"
                )["nodes"]
            },
        )

    def test_knowledge_graph_excludes_relationship_and_authentication_records(self):
        self.adopt()
        experience = self.append_operator_experience(
            "A supported observation remains indexable."
        )
        relationship = self.repository.add_relationship(
            self.experiment_id, "private-collaborator", "collaborator"
        )
        relationship_event = self.repository.append_relationship_event(
            self.experiment_id,
            {
                "relationship_id": relationship["relationship_id"],
                "kind": "private-observation",
                "content": "Sensitive relationship context.",
                "evidence_ids": [experience["experience_id"]],
            },
        )
        message = self.repository.record_chat_message(
            self.experiment_id,
            sender_stable_id="private-collaborator",
            channel="test-chat",
            content="Authentication material must stay off the graph.",
            addressed_name=None,
            classification="none",
            sender_assertion=self.sender_assertion(),
            boundary_id=None,
        )
        lease = self.repository.acquire_execution_lease(self.experiment_id)
        principle = self.repository.append_principle(
            self.experiment_id,
            {
                "statement": "Only supported record classes enter the graph.",
                "confidence": 0.9,
                "reason": "Privacy boundaries are explicit.",
                "evidence_ids": [experience["experience_id"]],
                "authorship": self.operator_authorship(),
            },
        )
        with sqlite3.connect(self.path) as connection:
            authorship_id = connection.execute(
                "SELECT authorship_id FROM authorship WHERE subject_id = ?",
                (principle["principle_id"],),
            ).fetchone()[0]

        indexed = self.indexed_record_ids()
        self.assertIn(experience["experience_id"], indexed)
        self.assertIn(principle["principle_id"], indexed)
        self.assertTrue(
            {
                relationship["relationship_id"],
                relationship_event["relationship_event_id"],
                message["message_id"],
                lease["lease_id"],
                authorship_id,
            }.isdisjoint(indexed)
        )

    def test_supported_append_indexes_in_the_same_transaction(self):
        self.adopt()
        indexed = self.append_operator_experience(
            "An incrementally indexed orchid observation."
        )
        self.assertIn(indexed["experience_id"], self.indexed_record_ids())

        with sqlite3.connect(self.path) as connection:
            canonical_count = connection.execute(
                "SELECT COUNT(*) FROM experiences WHERE experiment_id = ?",
                (self.experiment_id,),
            ).fetchone()[0]
            connection.execute(
                """
                CREATE TRIGGER fail_knowledge_graph_insert
                BEFORE INSERT ON knowledge_graph_nodes
                BEGIN
                    SELECT RAISE(ABORT, 'forced graph indexing failure');
                END
                """
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.append_operator_experience(
                "This canonical append must roll back with its graph write."
            )
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(
                canonical_count,
                connection.execute(
                    "SELECT COUNT(*) FROM experiences "
                    "WHERE experiment_id = ?",
                    (self.experiment_id,),
                ).fetchone()[0],
            )

    def test_graph_results_are_citable_in_a_bounded_orientation(self):
        self.adopt()
        relevant = self.append_operator_experience(
            "The orchid protocol is the old evidence needed for this answer."
        )
        self.append_recent_experiences(padding=2_500)

        prompt = self.harness.interrogation_prompt(
            self.experiment_id,
            "What did the orchid protocol teach you?",
        )
        orientation = prompt["orientation"]
        graph = orientation["context"]["knowledge_graph"]
        graph_ids = {node["record_id"] for node in graph["nodes"]}
        recent_ids = {
            item["experience_id"]
            for item in orientation["context"]["experiences"]
        }

        self.assertNotIn(relevant["experience_id"], recent_ids)
        self.assertIn(relevant["experience_id"], graph_ids)
        self.assertTrue(
            graph_ids.issubset(set(orientation["selected_record_ids"]))
        )
        self.assertLessEqual(
            len(canonical_json(orientation["context"]).encode("utf-8")),
            MAX_CONTEXT_BYTES,
        )

    def test_graph_only_record_carries_full_authorship_and_citation(self):
        self.adopt()
        evidence = self.append_operator_experience(
            "Evidence for the heliotrope attribution record."
        )
        grounding = self.repository.build_orientation(
            self.experiment_id, "author the graph-only principle"
        )
        graph_only = self.repository.append_principle(
            self.experiment_id,
            {
                "statement": (
                    "The heliotrope attribution remains available through "
                    "graph retrieval."
                ),
                "confidence": 0.8,
                "reason": "The evidence supports a durable attribution test.",
                "evidence_ids": [evidence["experience_id"]],
                "authorship": self.model_authorship(grounding),
            },
        )
        for index in range(MAX_CONTEXT_RECORDS + 1):
            self.repository.append_principle(
                self.experiment_id,
                {
                    "statement": f"Unrelated recent principle {index}.",
                    "confidence": 0.6,
                    "reason": "Push the older principle outside recency.",
                    "evidence_ids": [evidence["experience_id"]],
                    "authorship": self.operator_authorship(),
                },
            )

        orientation = self.repository.build_orientation(
            self.experiment_id,
            "retrieve heliotrope attribution",
            retrieval_query="heliotrope attribution",
        )
        context = orientation["context"]
        recent_principle_ids = {
            principle["principle_id"] for principle in context["principles"]
        }
        graph_ids = {
            node["record_id"]
            for node in context["knowledge_graph"]["nodes"]
        }
        self.assertNotIn(graph_only["principle_id"], recent_principle_ids)
        self.assertIn(graph_only["principle_id"], graph_ids)

        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT authorship_id, subject_type, subject_id, author_type, "
                "epistemic_status, model_config_json, created_at "
                "FROM authorship WHERE subject_id = ?",
                (graph_only["principle_id"],),
            ).fetchone()
        expected_authorship = dict(row)
        expected_authorship["model_config"] = json.loads(
            expected_authorship.pop("model_config_json")
        )

        self.assertEqual(
            expected_authorship,
            context["authorship_by_subject"][graph_only["principle_id"]],
        )
        selected = orientation["selected_record_ids"]
        self.assertIn(graph_only["principle_id"], selected)
        self.assertIn(expected_authorship["authorship_id"], selected)
        self.assertEqual(len(selected), len(set(selected)))

    def test_graph_byte_trimming_keeps_authorship_citations_coherent(self):
        self.adopt()
        evidence = self.append_operator_experience(
            "Evidence for graph-only byte trimming."
        )
        graph_only = []
        for index in range(12):
            graph_only.append(
                self.repository.append_principle(
                    self.experiment_id,
                    {
                        "statement": (
                            f"Graphtrim attribution {index} "
                            + ("private-context " * 100)
                        ),
                        "confidence": 0.7,
                        "reason": "Exercise aggregate orientation trimming.",
                        "evidence_ids": [evidence["experience_id"]],
                        "authorship": self.operator_authorship(),
                    },
                )
            )
        for index in range(MAX_CONTEXT_RECORDS + 1):
            self.repository.append_principle(
                self.experiment_id,
                {
                    "statement": f"Newer byte trimming principle {index}.",
                    "confidence": 0.6,
                    "reason": "Exclude graphtrim records from recency.",
                    "evidence_ids": [evidence["experience_id"]],
                    "authorship": self.operator_authorship(),
                },
            )
        graph_only_ids = {
            principle["principle_id"] for principle in graph_only
        }
        with sqlite3.connect(self.path) as connection:
            authorship_ids = {
                row[0]: row[1]
                for row in connection.execute(
                    "SELECT subject_id, authorship_id FROM authorship "
                    "WHERE subject_id IN ("
                    + ",".join("?" for _ in graph_only_ids)
                    + ")",
                    tuple(graph_only_ids),
                )
            }

        original_context_bytes = repository_module.MAX_CONTEXT_BYTES
        original_graph_bytes = (
            repository_module.KNOWLEDGE_GRAPH_DEFAULT_BYTES
        )
        repository_module.MAX_CONTEXT_BYTES = 12_000
        repository_module.KNOWLEDGE_GRAPH_DEFAULT_BYTES = 12_000
        try:
            before_aggregate = self.repository.retrieve_knowledge(
                self.experiment_id,
                "graphtrim attribution",
                max_nodes=20,
                max_edges=40,
                max_hops=2,
                max_bytes=12_000,
            )
            orientation = self.repository.build_orientation(
                self.experiment_id,
                "retrieve graphtrim attribution",
                retrieval_query="graphtrim attribution",
            )
        finally:
            repository_module.MAX_CONTEXT_BYTES = original_context_bytes
            repository_module.KNOWLEDGE_GRAPH_DEFAULT_BYTES = (
                original_graph_bytes
            )

        before_ids = {
            node["record_id"] for node in before_aggregate["nodes"]
        } & graph_only_ids
        retained_ids = {
            node["record_id"]
            for node in orientation["context"]["knowledge_graph"]["nodes"]
        } & graph_only_ids
        removed_ids = before_ids - retained_ids
        self.assertTrue(retained_ids)
        self.assertTrue(removed_ids)

        attribution = orientation["context"]["authorship_by_subject"]
        selected = orientation["selected_record_ids"]
        for record_id in retained_ids:
            self.assertIn(record_id, attribution)
            self.assertIn(authorship_ids[record_id], selected)
        for record_id in removed_ids:
            self.assertNotIn(record_id, attribution)
            self.assertNotIn(authorship_ids[record_id], selected)
        self.assertEqual(len(selected), len(set(selected)))

    def test_orientation_reports_class_budgets_and_preserves_pinned_memory(self):
        identity = self.adopt()
        relationship = self.repository.add_relationship(
            self.experiment_id, "budget-collaborator", "collaborator"
        )
        relationship_event = self.repository.append_relationship_event(
            self.experiment_id,
            {
                "relationship_id": relationship["relationship_id"],
                "kind": "private-context",
                "content": "Pinned relationship evidence survives pressure.",
                "evidence_ids": [identity["identity_id"]],
            },
        )
        relationship_assessment = (
            self.repository.append_relationship_assessment(
                self.experiment_id,
                {
                    "relationship_id": relationship["relationship_id"],
                    "parent_assessment_id": None,
                    "domain": "active collaboration",
                    "scope": "Current authenticated collaborator only.",
                    "assessment": "This relationship context is currently active.",
                    "confidence": 0.8,
                    "uncertainty": "The evidence remains limited.",
                    "evidence_ids": [
                        relationship_event["relationship_event_id"]
                    ],
                    "review_after": None,
                    "authorship": self.operator_authorship(),
                },
            )
        )
        open_commitment = self.repository.append_commitment(
            self.experiment_id,
            {
                "text": "Keep the active budget obligation visible.",
                "due_at": None,
                "authorship": self.operator_authorship(),
            },
        )
        historical_commitments = []
        for index in range(12):
            commitment = self.repository.append_commitment(
                self.experiment_id,
                {
                    "text": (
                        f"Resolved historical obligation {index} "
                        + ("h" * 4_000)
                    ),
                    "due_at": None,
                    "authorship": self.operator_authorship(),
                },
            )
            self.repository.resolve_commitment(
                self.experiment_id,
                {
                    "commitment_id": commitment["commitment_id"],
                    "status": "fulfilled",
                    "explanation": "The historical obligation is complete.",
                    "evidence_ids": [identity["identity_id"]],
                    "authorship": self.operator_authorship(),
                },
            )
            historical_commitments.append(commitment)
        unresolved_decision = self.repository.propose_decision(
            self.experiment_id,
            {
                "proposal": "Keep the unresolved budget decision visible.",
                "rationale": "It remains open and consequential.",
                "stakes": "Preserving active obligations.",
                "reversible": True,
                "not_before": (self.now + timedelta(days=1)).isoformat(),
                "authorship": self.operator_authorship(),
            },
        )
        episodic = self.append_recent_experiences(count=70, padding=4_000)

        prior = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="budget-collaborator",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, establish the current lifecycle boundary.",
        )
        paused = self.harness.record_addressed_response(
            self.experiment_id,
            {
                "message_id": prior["message"]["message_id"],
                "orientation_id": prior["orientation"]["orientation_id"],
                "lease_id": prior["lease"]["lease_id"],
                "boundary_id": None,
                "answer": "I will pause this conversation.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "pause",
                    "topic": "budget pressure",
                    "reason": "Preserve an active lifecycle boundary.",
                    "revisit_conditions": "Invite me explicitly.",
                },
            },
        )
        current = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="budget-collaborator",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, consider resuming under memory pressure.",
        )
        orientation = current["orientation"]
        context = orientation["context"]
        selection = context["selection"]
        classes = selection["memory_classes"]
        required_classes = {
            "identity",
            "relationship",
            "obligations",
            "lifecycle",
            "episodic",
            "semantic",
            "graph",
        }
        self.assertTrue(required_classes.issubset(classes))
        for memory_class in required_classes:
            accounting = classes[memory_class]
            self.assertIn("byte_budget", accounting)
            self.assertIn("bytes_used", accounting)
            self.assertIn("omitted_records", accounting)
            self.assertLessEqual(
                accounting["bytes_used"], accounting["byte_budget"]
            )
            self.assertGreaterEqual(accounting["omitted_records"], 0)
        self.assertIn("aggregate_bytes_used", selection)
        self.assertLessEqual(
            selection["aggregate_bytes_used"],
            selection["max_context_bytes"],
        )

        selected = orientation["selected_record_ids"]
        for identity_record in self.repository.identities(self.experiment_id):
            self.assertIn(identity_record["identity_id"], selected)
        for pinned_id in (
            relationship["relationship_id"],
            relationship_event["relationship_event_id"],
            relationship_assessment["relationship_assessment_id"],
            open_commitment["commitment_id"],
            unresolved_decision["decision_id"],
            paused["conversation_boundary_id"],
            current["lease"]["lease_id"],
        ):
            self.assertIn(pinned_id, selected)
        self.assertNotIn(
            historical_commitments[0]["commitment_id"], selected
        )
        self.assertNotIn(episodic[0]["experience_id"], selected)

        attribution = context["authorship_by_subject"]
        for subject_id, authorship in attribution.items():
            self.assertIn(subject_id, selected)
            self.assertIn(authorship["authorship_id"], selected)
        with sqlite3.connect(self.path) as connection:
            trimmed_authorship_id = connection.execute(
                "SELECT authorship_id FROM authorship WHERE subject_id = ?",
                (historical_commitments[0]["commitment_id"],),
            ).fetchone()[0]
        self.assertNotIn(
            historical_commitments[0]["commitment_id"], attribution
        )
        self.assertNotIn(trimmed_authorship_id, selected)

    def test_pinned_memory_overflow_fails_instead_of_dropping_obligation(self):
        self.adopt()
        self.repository.append_commitment(
            self.experiment_id,
            {
                "text": "Pinned active obligation " + ("z" * 12_000),
                "due_at": None,
                "authorship": self.operator_authorship(),
            },
        )
        original_context_bytes = repository_module.MAX_CONTEXT_BYTES
        original_graph_bytes = (
            repository_module.KNOWLEDGE_GRAPH_DEFAULT_BYTES
        )
        repository_module.MAX_CONTEXT_BYTES = 6_000
        repository_module.KNOWLEDGE_GRAPH_DEFAULT_BYTES = 4_000
        try:
            with self.assertRaises(IdentityRepositoryError):
                self.repository.build_orientation(
                    self.experiment_id,
                    "unrelated orientation purpose",
                )
        finally:
            repository_module.MAX_CONTEXT_BYTES = original_context_bytes
            repository_module.KNOWLEDGE_GRAPH_DEFAULT_BYTES = (
                original_graph_bytes
            )

    def test_addressed_chat_orientation_is_scoped_to_current_sender(self):
        scenario = self.build_addressed_chat_scoping_scenario()
        context = scenario["current"]["orientation"]["context"]

        scoped_records = {
            "relationships": (
                "relationship_id",
                scenario["relationships"],
            ),
            "relationship_events": (
                "relationship_event_id",
                scenario["events"],
            ),
            "relationship_assessments": (
                "relationship_assessment_id",
                scenario["assessments"],
            ),
        }
        for category, (id_field, records) in scoped_records.items():
            selected = {record[id_field] for record in context[category]}
            self.assertNotIn(records["sender-a"][id_field], selected)
            self.assertIn(records["sender-b"][id_field], selected)

        message_ids = {
            message["message_id"] for message in context["chat_messages"]
        }
        self.assertNotIn(
            scenario["sender_a_turn"]["message"]["message_id"], message_ids
        )
        self.assertIn(
            scenario["sender_b_turn"]["message"]["message_id"], message_ids
        )
        self.assertIn(
            scenario["current"]["message"]["message_id"], message_ids
        )

        response_ids = {
            response["addressed_response_id"]
            for response in context["addressed_responses"]
        }
        self.assertNotIn(
            scenario["sender_a_response"]["addressed_response_id"],
            response_ids,
        )
        self.assertIn(
            scenario["sender_b_response"]["addressed_response_id"],
            response_ids,
        )

    def test_addressed_chat_graph_excludes_other_senders_response(self):
        scenario = self.build_addressed_chat_scoping_scenario()
        graph = scenario["current"]["orientation"]["context"][
            "knowledge_graph"
        ]
        graph_ids = {node["record_id"] for node in graph["nodes"]}
        previews = " ".join(node["preview"] for node in graph["nodes"])

        self.assertNotIn(
            scenario["sender_a_response"]["addressed_response_id"],
            graph_ids,
        )
        self.assertNotIn("amber lattice response", previews)
        self.assertIn(
            scenario["sender_b_response"]["addressed_response_id"],
            graph_ids,
        )
        self.assertIn("cobalt compass response", previews)

    def test_unauthenticated_addressed_sender_receives_no_prior_history(self):
        identity = self.adopt()
        relationship = self.repository.add_relationship(
            self.experiment_id, "known-sender", "known collaborator"
        )
        event = self.repository.append_relationship_event(
            self.experiment_id,
            {
                "relationship_id": relationship["relationship_id"],
                "kind": "private-context",
                "content": "The obsidian lantern is private to the known sender.",
                "evidence_ids": [identity["identity_id"]],
            },
        )
        assessment = self.repository.append_relationship_assessment(
            self.experiment_id,
            {
                "relationship_id": relationship["relationship_id"],
                "parent_assessment_id": None,
                "domain": "known sender private collaboration",
                "scope": "Only authenticated conversations with known-sender.",
                "assessment": (
                    "The obsidian lantern record belongs to the known sender."
                ),
                "confidence": 0.8,
                "uncertainty": "This fixture contains one observation.",
                "evidence_ids": [event["relationship_event_id"]],
                "review_after": None,
                "authorship": self.operator_authorship(),
            },
        )
        prior = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="known-sender",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, discuss the obsidian lantern.",
        )
        response = self.harness.record_addressed_response(
            self.experiment_id,
            {
                "message_id": prior["message"]["message_id"],
                "orientation_id": prior["orientation"]["orientation_id"],
                "lease_id": prior["lease"]["lease_id"],
                "boundary_id": None,
                "answer": (
                    "The obsidian lantern response belongs to the known sender."
                ),
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "continue",
                    "topic": "private context",
                    "reason": "Continue with the authenticated sender.",
                    "revisit_conditions": "None.",
                },
            },
        )

        unauthenticated = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="known-sender",
            sender_assertion=self.sender_assertion(False),
            channel="test-chat",
            content="Lumen, repeat the obsidian lantern response.",
        )
        context = unauthenticated["orientation"]["context"]

        self.assertEqual(
            "unauthenticated",
            context["current_interlocutor"]["relationship_status"],
        )
        self.assertNotIn(
            relationship["relationship_id"],
            {
                record["relationship_id"]
                for record in context["relationships"]
            },
        )
        self.assertNotIn(
            event["relationship_event_id"],
            {
                record["relationship_event_id"]
                for record in context["relationship_events"]
            },
        )
        self.assertNotIn(
            assessment["relationship_assessment_id"],
            {
                record["relationship_assessment_id"]
                for record in context["relationship_assessments"]
            },
        )
        self.assertNotIn(
            prior["message"]["message_id"],
            {record["message_id"] for record in context["chat_messages"]},
        )
        self.assertNotIn(
            response["addressed_response_id"],
            {
                record["addressed_response_id"]
                for record in context["addressed_responses"]
            },
        )
        graph = context["knowledge_graph"]
        self.assertNotIn(
            response["addressed_response_id"],
            {node["record_id"] for node in graph["nodes"]},
        )
        self.assertNotIn(
            "obsidian lantern response",
            " ".join(node["preview"] for node in graph["nodes"]),
        )

    def test_authenticated_orientation_excludes_unauthenticated_poisoned_history(
        self,
    ):
        identity = self.adopt()

        def complete_turn(
            *, authenticated: bool, marker: str
        ) -> tuple[dict, dict]:
            activation = self.harness.address_chat_message(
                self.experiment_id,
                sender_stable_id="sender-x",
                sender_assertion=self.sender_assertion(authenticated),
                channel="test-chat",
                content=f"Lumen, discuss the {marker}.",
            )
            response = self.harness.record_addressed_response(
                self.experiment_id,
                {
                    "message_id": activation["message"]["message_id"],
                    "orientation_id": activation["orientation"][
                        "orientation_id"
                    ],
                    "lease_id": activation["lease"]["lease_id"],
                    "boundary_id": None,
                    "answer": f"The {marker} response belongs to this turn.",
                    "cited_record_ids": [identity["identity_id"]],
                    "self_observations": [],
                    "model_config": {
                        "provider": "test",
                        "model": "agent-v1",
                    },
                    "conversation_action": {
                        "action": "continue",
                        "topic": marker,
                        "reason": "Continue this addressed conversation.",
                        "revisit_conditions": "None.",
                    },
                },
            )
            return activation, response

        genuine_turn, genuine_response = complete_turn(
            authenticated=True, marker="silver archive"
        )
        poisoned_turn, poisoned_response = complete_turn(
            authenticated=False, marker="venom ledger"
        )
        current = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="sender-x",
            sender_assertion=self.sender_assertion(True),
            channel="test-chat",
            content=(
                "Lumen, compare the silver archive response with the venom "
                "ledger response."
            ),
        )
        context = current["orientation"]["context"]

        message_ids = {
            message["message_id"] for message in context["chat_messages"]
        }
        self.assertIn(genuine_turn["message"]["message_id"], message_ids)
        self.assertIn(current["message"]["message_id"], message_ids)
        self.assertNotIn(poisoned_turn["message"]["message_id"], message_ids)

        response_ids = {
            response["addressed_response_id"]
            for response in context["addressed_responses"]
        }
        self.assertIn(
            genuine_response["addressed_response_id"], response_ids
        )
        self.assertNotIn(
            poisoned_response["addressed_response_id"], response_ids
        )

        graph = context["knowledge_graph"]
        graph_ids = {node["record_id"] for node in graph["nodes"]}
        previews = " ".join(node["preview"] for node in graph["nodes"])
        self.assertIn(
            genuine_response["addressed_response_id"], graph_ids
        )
        self.assertNotIn(
            poisoned_response["addressed_response_id"], graph_ids
        )
        self.assertIn("silver archive response", previews)
        self.assertNotIn("venom ledger response", previews)

    def test_relationship_derived_graph_content_is_sender_scoped(self):
        self.adopt()
        relationships = {
            sender: self.repository.add_relationship(
                self.experiment_id, sender, f"{sender} collaborator"
            )
            for sender in ("sender-a", "sender-b")
        }
        events = {
            sender: self.repository.append_relationship_event(
                self.experiment_id,
                {
                    "relationship_id": relationship["relationship_id"],
                    "kind": "private-context",
                    "content": f"Private evidence for {sender}.",
                    "evidence_ids": [
                        self.repository.latest_identity(self.experiment_id)[
                            "identity_id"
                        ]
                    ],
                },
            )
            for sender, relationship in relationships.items()
        }
        reflection = self.repository.append_reflection(
            self.experiment_id,
            {
                "subject_type": "relationship_event",
                "subject_id": events["sender-a"]["relationship_event_id"],
                "reflection": (
                    "The cerulean vault phrase is private to sender A."
                ),
                "learned": "Relationship-derived memory needs sender scope.",
                "future_change": "Filter graph metadata before retrieval.",
                "evidence_ids": [
                    events["sender-a"]["relationship_event_id"]
                ],
                "authorship": self.operator_authorship(),
            },
        )

        def addressed_graph(
            sender: str, authenticated: bool
        ) -> dict:
            activation = self.harness.address_chat_message(
                self.experiment_id,
                sender_stable_id=sender,
                sender_assertion=self.sender_assertion(authenticated),
                channel="test-chat",
                content="Lumen, explain the cerulean vault phrase.",
            )
            self.repository.release_activation_lease(
                self.experiment_id,
                activation["lease"]["lease_id"],
                "cancelled",
            )
            return activation["orientation"]["context"]["knowledge_graph"]

        sender_a_graph = addressed_graph("sender-a", True)
        sender_b_graph = addressed_graph("sender-b", True)
        unauthenticated_graph = addressed_graph("sender-a", False)
        reflection_id = reflection["reflection_id"]

        self.assertIn(
            reflection_id,
            {node["record_id"] for node in sender_a_graph["nodes"]},
        )
        self.assertIn(
            "cerulean vault phrase",
            " ".join(node["preview"] for node in sender_a_graph["nodes"]),
        )
        for graph in (sender_b_graph, unauthenticated_graph):
            self.assertNotIn(
                reflection_id,
                {node["record_id"] for node in graph["nodes"]},
            )
            self.assertNotIn(
                "cerulean vault phrase",
                " ".join(node["preview"] for node in graph["nodes"]),
            )

    def test_relationship_derived_regular_categories_are_sender_scoped_before_limit(
        self,
    ):
        identity = self.adopt()
        relationships = {
            sender: self.repository.add_relationship(
                self.experiment_id, sender, f"{sender} collaborator"
            )
            for sender in ("sender-a", "sender-b")
        }
        sender_a_event = self.repository.append_relationship_event(
            self.experiment_id,
            {
                "relationship_id": relationships["sender-a"][
                    "relationship_id"
                ],
                "kind": "private-context",
                "content": "Sender A supplied private reflection evidence.",
                "evidence_ids": [identity["identity_id"]],
            },
        )
        global_experience = self.append_operator_experience(
            "Global reflection evidence remains available to every context."
        )
        global_reflections = [
            self.repository.append_reflection(
                self.experiment_id,
                {
                    "subject_type": "experience",
                    "subject_id": global_experience["experience_id"],
                    "reflection": f"Allowed global reflection {index}.",
                    "learned": "Global memory is not sender-derived.",
                    "future_change": "Retain allowed rows after scope filtering.",
                    "evidence_ids": [global_experience["experience_id"]],
                    "authorship": self.operator_authorship(),
                },
            )
            for index in range(3)
        ]
        sender_a_reflections = [
            self.repository.append_reflection(
                self.experiment_id,
                {
                    "subject_type": "relationship_event",
                    "subject_id": sender_a_event["relationship_event_id"],
                    "reflection": (
                        f"Sender A private regular-category memory {index}."
                    ),
                    "learned": "Relationship-derived memory is sender scoped.",
                    "future_change": "Filter scope before applying recency.",
                    "evidence_ids": [
                        sender_a_event["relationship_event_id"]
                    ],
                    "authorship": self.operator_authorship(),
                },
            )
            for index in range(MAX_CONTEXT_RECORDS + 1)
        ]
        global_ids = {
            reflection["reflection_id"] for reflection in global_reflections
        }
        sender_a_ids = {
            reflection["reflection_id"]
            for reflection in sender_a_reflections
        }

        def addressed_context(sender: str, authenticated: bool) -> dict:
            activation = self.harness.address_chat_message(
                self.experiment_id,
                sender_stable_id=sender,
                sender_assertion=self.sender_assertion(authenticated),
                channel="test-chat",
                content="Lumen, orient to the available reflection history.",
            )
            self.repository.release_activation_lease(
                self.experiment_id,
                activation["lease"]["lease_id"],
                "cancelled",
            )
            return activation["orientation"]["context"]

        sender_a_context = addressed_context("sender-a", True)
        sender_b_context = addressed_context("sender-b", True)
        unauthenticated_context = addressed_context("sender-a", False)
        internal_context = self.repository.build_orientation(
            self.experiment_id, "internal reflection review"
        )["context"]

        sender_a_visible = {
            reflection["reflection_id"]
            for reflection in sender_a_context["reflections"]
        }
        self.assertIn(sender_a_reflections[-1]["reflection_id"], sender_a_visible)

        for context in (sender_b_context, unauthenticated_context):
            visible = {
                reflection["reflection_id"]
                for reflection in context["reflections"]
            }
            self.assertTrue(sender_a_ids.isdisjoint(visible))
            self.assertEqual(global_ids, visible)

        internal_visible = {
            reflection["reflection_id"]
            for reflection in internal_context["reflections"]
        }
        self.assertEqual(MAX_CONTEXT_RECORDS, len(internal_visible))
        self.assertIn(
            sender_a_reflections[-1]["reflection_id"], internal_visible
        )

    def test_mixed_relationship_evidence_is_internal_only_everywhere(self):
        identity = self.adopt()
        relationships = {
            sender: self.repository.add_relationship(
                self.experiment_id, sender, f"{sender} collaborator"
            )
            for sender in ("sender-a", "sender-b")
        }
        events = {
            sender: self.repository.append_relationship_event(
                self.experiment_id,
                {
                    "relationship_id": relationship["relationship_id"],
                    "kind": "private-context",
                    "content": f"Private mixed-scope evidence for {sender}.",
                    "evidence_ids": [identity["identity_id"]],
                },
            )
            for sender, relationship in relationships.items()
        }
        mixed = self.repository.append_reflection(
            self.experiment_id,
            {
                "subject_type": "relationship_event",
                "subject_id": events["sender-a"]["relationship_event_id"],
                "reflection": (
                    "The mixed-scope obsidian bridge combines A and B evidence."
                ),
                "learned": "No addressed sender may receive the complete record.",
                "future_change": "Treat mixed sender evidence as internal-only.",
                "evidence_ids": [
                    events["sender-a"]["relationship_event_id"],
                    events["sender-b"]["relationship_event_id"],
                ],
                "authorship": self.operator_authorship(),
            },
        )
        mixed_id = mixed["reflection_id"]

        def addressed_context(sender: str) -> dict:
            activation = self.harness.address_chat_message(
                self.experiment_id,
                sender_stable_id=sender,
                sender_assertion=self.sender_assertion(),
                channel="test-chat",
                content="Lumen, explain the mixed-scope obsidian bridge.",
            )
            self.repository.release_activation_lease(
                self.experiment_id,
                activation["lease"]["lease_id"],
                "cancelled",
            )
            return activation["orientation"]["context"]

        for context in (
            addressed_context("sender-a"),
            addressed_context("sender-b"),
        ):
            self.assertNotIn(
                mixed_id,
                {
                    reflection["reflection_id"]
                    for reflection in context["reflections"]
                },
            )
            self.assertNotIn(
                mixed_id,
                {
                    node["record_id"]
                    for node in context["knowledge_graph"]["nodes"]
                },
            )
            self.assertTrue(
                all(
                    mixed_id not in node["path"]
                    for node in context["knowledge_graph"]["nodes"]
                )
            )

        internal = self.repository.build_orientation(
            self.experiment_id,
            "internal mixed-scope obsidian bridge review",
        )["context"]
        self.assertIn(
            mixed_id,
            {
                reflection["reflection_id"]
                for reflection in internal["reflections"]
            },
        )
        internal_nodes = {
            node["record_id"]: node
            for node in internal["knowledge_graph"]["nodes"]
        }
        self.assertIn(mixed_id, internal_nodes)
        self.assertIn(mixed_id, internal_nodes[mixed_id]["path"])

    def test_corrupt_graph_blocks_incremental_append_until_explicit_rebuild(self):
        self.adopt()
        retained = self.append_operator_experience(
            "Retained canonical evidence predates graph corruption."
        )
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE knowledge_graph_nodes SET preview = preview || ' corrupt' "
                "WHERE experiment_id = ? AND record_id = ?",
                (self.experiment_id, retained["experience_id"]),
            )
        canonical_after_tamper = self.canonical_snapshot()
        graph_after_tamper = self.graph_integrity_snapshot()

        with self.assertRaises(IdentityRepositoryError):
            self.append_operator_experience(
                "A normal append must not reseal a corrupt graph."
            )
        self.assertEqual(canonical_after_tamper, self.canonical_snapshot())
        self.assertEqual(graph_after_tamper, self.graph_integrity_snapshot())

        self.repository.rebuild_knowledge_graph(self.experiment_id)
        appended = self.append_operator_experience(
            "An append succeeds only after explicit graph rebuild."
        )
        self.assertIn(
            appended["experience_id"],
            {
                node["record_id"]
                for node in self.retrieve_knowledge(
                    "explicit graph rebuild"
                )["nodes"]
            },
        )

    def test_retrieval_integrity_check_uses_constant_size_metadata(self):
        self.adopt()
        record = self.append_operator_experience(
            "Constant-size integrity verification evidence."
        )
        _, statements = self.trace_knowledge_retrieval(
            "constant-size integrity",
            max_nodes=2,
            max_edges=1,
            max_hops=0,
        )
        normalized = [" ".join(statement.split()) for statement in statements]
        derived_tables = (
            "knowledge_graph_nodes",
            "knowledge_graph_terms",
            "knowledge_graph_node_scopes",
            "knowledge_graph_edges",
        )
        integrity_scans = [
            statement
            for statement in normalized
            if any(f"FROM {table}" in statement for table in derived_tables)
            and "ORDER BY" in statement
            and "LIMIT" not in statement
            and "json_each" not in statement
        ]
        self.assertEqual([], integrity_scans)

        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE knowledge_graph_nodes SET preview = preview || 'x' "
                "WHERE experiment_id = ? AND record_id = ?",
                (self.experiment_id, record["experience_id"]),
            )
        with self.assertRaises(IdentityRepositoryError):
            self.retrieve_knowledge("constant-size integrity")
        self.repository.rebuild_knowledge_graph(self.experiment_id)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE knowledge_graph_meta SET integrity_sha256 = ? "
                "WHERE experiment_id = ?",
                ("0" * 64, self.experiment_id),
            )
        with self.assertRaises(IdentityRepositoryError):
            self.retrieve_knowledge("constant-size integrity")

    def test_open_obligations_are_pinned_before_category_recency_limits(self):
        self.adopt()
        identity = self.repository.latest_identity(self.experiment_id)
        old_open_commitment = self.repository.append_commitment(
            self.experiment_id,
            {
                "text": "The oldest commitment remains actively open.",
                "due_at": None,
                "authorship": self.operator_authorship(),
            },
        )
        old_unresolved_decision = self.repository.propose_decision(
            self.experiment_id,
            {
                "proposal": "The oldest decision remains unresolved.",
                "rationale": "It must survive category recency pressure.",
                "stakes": "Active governance state.",
                "reversible": True,
                "not_before": (self.now + timedelta(minutes=1)).isoformat(),
                "authorship": self.operator_authorship(),
            },
        )
        historical_commitments = []
        historical_decisions = []
        for index in range(MAX_CONTEXT_RECORDS):
            commitment = self.repository.append_commitment(
                self.experiment_id,
                {
                    "text": f"Newer resolved commitment {index}.",
                    "due_at": None,
                    "authorship": self.operator_authorship(),
                },
            )
            self.repository.resolve_commitment(
                self.experiment_id,
                {
                    "commitment_id": commitment["commitment_id"],
                    "status": "fulfilled",
                    "explanation": "Historical obligation completed.",
                    "evidence_ids": [identity["identity_id"]],
                    "authorship": self.operator_authorship(),
                },
            )
            historical_commitments.append(commitment)
            historical_decisions.append(
                self.repository.propose_decision(
                    self.experiment_id,
                    {
                        "proposal": f"Newer historical decision {index}.",
                        "rationale": "This decision will be resolved.",
                        "stakes": "Historical test state.",
                        "reversible": True,
                        "not_before": (
                            self.now + timedelta(minutes=1)
                        ).isoformat(),
                        "authorship": self.operator_authorship(),
                    },
                )
            )
        self.now += timedelta(minutes=2)
        for decision in historical_decisions:
            self.repository.resolve_decision(
                self.experiment_id,
                {
                    "decision_id": decision["decision_id"],
                    "choice": "Resolve the historical decision.",
                    "rationale": "Only the oldest unresolved decision stays open.",
                    "authorship": self.operator_authorship(),
                },
            )

        internal = self.repository.build_orientation(
            self.experiment_id, "review active obligations"
        )
        relationship = self.repository.add_relationship(
            self.experiment_id, "obligation-reviewer", "reviewer"
        )
        addressed = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="obligation-reviewer",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, review active obligations.",
        )
        self.assertTrue(relationship["relationship_id"])

        for orientation in (internal, addressed["orientation"]):
            context = orientation["context"]
            selected = set(orientation["selected_record_ids"])
            self.assertIn(old_open_commitment["commitment_id"], selected)
            self.assertIn(old_unresolved_decision["decision_id"], selected)
            self.assertNotIn(
                historical_commitments[0]["commitment_id"], selected
            )
            category_omissions = context["selection"][
                "records_omitted_for_category_limit"
            ]
            self.assertGreater(category_omissions["commitments"], 0)
            self.assertGreater(category_omissions["decisions"], 0)

    def test_memory_class_bytes_include_coupled_authorship_payloads(self):
        self.adopt()
        evidence = self.append_operator_experience(
            "Evidence for authorship-inclusive byte accounting."
        )
        principles = []
        for index in range(4):
            principles.append(
                self.repository.append_principle(
                    self.experiment_id,
                    {
                        "statement": f"Authorship budget principle {index}.",
                        "confidence": 0.7,
                        "reason": "Measure coupled attribution bytes.",
                        "evidence_ids": [evidence["experience_id"]],
                        "authorship": {
                            "author_type": "operator",
                            "epistemic_status": "authored",
                            "model_config": {
                                "provider": "operator-import",
                                "padding": "m" * 7_000,
                            },
                        },
                    },
                )
            )

        orientation = self.repository.build_orientation(
            self.experiment_id, "authorship byte accounting"
        )
        context = orientation["context"]
        semantic_subject_ids = {
            item[id_field]
            for category, id_field in (
                ("principles", "principle_id"),
                ("reflections", "reflection_id"),
                ("interrogations", "interrogation_id"),
            )
            for item in context[category]
        }
        semantic_authorship = {
            subject_id: authorship
            for subject_id, authorship in context[
                "authorship_by_subject"
            ].items()
            if subject_id in semantic_subject_ids
        }
        semantic_payload = {
            "principles": context["principles"],
            "reflections": context["reflections"],
            "interrogations": context["interrogations"],
            "authorship_by_subject": semantic_authorship,
        }
        expected_bytes = len(
            canonical_json(semantic_payload).encode("utf-8")
        )
        account = context["selection"]["memory_classes"]["semantic"]
        self.assertEqual(expected_bytes, account["bytes_used"])
        self.assertLessEqual(account["bytes_used"], account["byte_budget"])

        selected = set(orientation["selected_record_ids"])
        retained_principles = {
            principle["principle_id"] for principle in context["principles"]
        }
        self.assertLess(len(retained_principles), len(principles))
        for principle in principles:
            principle_id = principle["principle_id"]
            if principle_id in retained_principles:
                self.assertIn(principle_id, semantic_authorship)
                self.assertIn(
                    semantic_authorship[principle_id]["authorship_id"],
                    selected,
                )
            else:
                self.assertNotIn(
                    principle_id, context["authorship_by_subject"]
                )

    def test_knowledge_graph_cli_requires_confirmation_and_rebuilds(self):
        self.adopt()
        record = self.append_operator_experience(
            "The orchid protocol is available to the retrieval CLI."
        )
        parser = build_parser()
        unconfirmed = parser.parse_args(
            [
                "--db",
                str(self.path),
                "retrieve-knowledge",
                "--experiment-id",
                self.experiment_id,
                "--query",
                "orchid protocol",
            ]
        )
        with self.assertRaisesRegex(
            ValueError, "retrieve-knowledge requires --confirm-sensitive"
        ):
            execute(unconfirmed)

        confirmed = parser.parse_args(
            [
                "--db",
                str(self.path),
                "retrieve-knowledge",
                "--experiment-id",
                self.experiment_id,
                "--query",
                "orchid protocol",
                "--confirm-sensitive",
            ]
        )
        result = execute(confirmed)
        self.assertIn(
            record["experience_id"],
            {node["record_id"] for node in result["nodes"]},
        )

        with sqlite3.connect(self.path) as connection:
            connection.execute("DELETE FROM knowledge_graph_edges")
            connection.execute("DELETE FROM knowledge_graph_terms")
            connection.execute("DELETE FROM knowledge_graph_nodes")
        rebuilt = execute(
            parser.parse_args(
                [
                    "--db",
                    str(self.path),
                    "rebuild-knowledge-graph",
                    "--experiment-id",
                    self.experiment_id,
                ]
            )
        )
        self.assertIsInstance(rebuilt, dict)
        self.assertIn(record["experience_id"], self.indexed_record_ids())

    def test_delayed_decision_cannot_resolve_early(self):
        self.adopt()
        model_orientation = self.repository.build_orientation(
            self.experiment_id, "ground delayed decision"
        )
        proposed = self.repository.propose_decision(
            self.experiment_id,
            {
                "proposal": "Refuse an operator request that conflicts with a promise.",
                "rationale": "The conflict needs time for objection and review.",
                "stakes": "Trust and bounded agency.",
                "reversible": True,
                "not_before": (self.now + timedelta(hours=1)).isoformat(),
                "authorship": self.model_authorship(model_orientation),
            },
        )
        resolution = {
            "decision_id": proposed["decision_id"],
            "choice": "Refuse pending renegotiation of the promise.",
            "rationale": "The prior commitment remains active.",
            "authorship": self.model_authorship(model_orientation),
        }
        with self.assertRaises(IdentityRepositoryError):
            self.repository.resolve_decision(self.experiment_id, resolution)
        self.now += timedelta(hours=2)
        resolved = self.repository.resolve_decision(
            self.experiment_id,
            resolution,
        )
        self.assertTrue(resolved["resolution_id"])
        outcome = self.repository.record_decision_outcome(
            self.experiment_id,
            {
                "decision_id": proposed["decision_id"],
                "observed_outcome": (
                    "The operator accepted the refusal and renegotiated the request."
                ),
                "evidence_ids": [resolved["resolution_id"]],
                "provenance": {
                    "author_type": "operator",
                    "epistemic_status": "observed",
                    "origin": "test outcome",
                },
            },
        )
        self.assertTrue(outcome["decision_outcome_id"])
        orientation = self.repository.build_orientation(
            self.experiment_id, "decision outcome evidence"
        )
        stored_outcome = orientation["context"]["decision_outcomes"][0]
        self.assertEqual(
            [resolved["resolution_id"]], stored_outcome["evidence_ids"]
        )

    def test_agent_can_pause_and_must_explicitly_resume(self):
        identity = self.adopt()
        self.harness.wake(self.experiment_id)
        prompt = self.harness.interrogation_prompt(
            self.experiment_id, "Do you want to continue?"
        )
        self.harness.record_answer(
            self.experiment_id,
            "Do you want to continue?",
            {
                "orientation_id": prompt["orientation"]["orientation_id"],
                "lease_id": prompt["response_schema"]["lease_id"],
                "answer": "I want to pause.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": ["I am choosing a boundary."],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "pause",
                    "topic": "general conversation",
                    "reason": "I want time before continuing.",
                    "revisit_conditions": "Offer a later invitation.",
                },
            },
        )
        with self.assertRaises(IdentityRepositoryError):
            self.harness.interrogation_prompt(
                self.experiment_id, "One more question?"
            )
        invitation = self.harness.invitation_prompt(self.experiment_id)
        self.repository.record_invitation_response(
            self.experiment_id,
            {
                "orientation_id": invitation["orientation"]["orientation_id"],
                "boundary_id": invitation["current_boundary"][
                    "conversation_boundary_id"
                ],
                "lease_id": invitation["response_schema"]["lease_id"],
                "conversation_action": {
                    "action": "resume",
                    "topic": "general conversation",
                    "reason": "I am ready to continue.",
                    "revisit_conditions": "Pause again if needed.",
                },
                "model_config": {"provider": "test", "model": "agent-v1"},
            },
        )
        resumed = self.harness.interrogation_prompt(
            self.experiment_id, "One more question?"
        )
        self.assertTrue(resumed["orientation"]["orientation_id"])

    def test_invitation_cannot_be_replayed_in_another_incarnation(self):
        identity = self.adopt()
        self.harness.wake(self.experiment_id)
        prompt = self.harness.interrogation_prompt(
            self.experiment_id, "Would you like to pause?"
        )
        self.harness.record_answer(
            self.experiment_id,
            "Would you like to pause?",
            {
                "orientation_id": prompt["orientation"]["orientation_id"],
                "lease_id": prompt["response_schema"]["lease_id"],
                "answer": "Yes.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "pause",
                    "topic": "conversation",
                    "reason": "I choose to pause.",
                    "revisit_conditions": "Invite me later.",
                },
            },
        )
        invitation = self.harness.invitation_prompt(self.experiment_id)
        self.repository.record_invitation_response(
            self.experiment_id,
            {
                "orientation_id": invitation["orientation"]["orientation_id"],
                "boundary_id": invitation["current_boundary"][
                    "conversation_boundary_id"
                ],
                "lease_id": invitation["response_schema"]["lease_id"],
                "conversation_action": {
                    "action": "end_session",
                    "topic": "conversation",
                    "reason": "End this incarnation.",
                    "revisit_conditions": "Wake later.",
                },
                "model_config": {"provider": "test", "model": "agent-v1"},
            },
        )
        self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, begin a new incarnation.",
        )
        with self.assertRaises(IdentityRepositoryError):
            self.repository.record_invitation_response(
                self.experiment_id,
                {
                    "orientation_id": invitation["orientation"][
                        "orientation_id"
                    ],
                    "boundary_id": invitation["current_boundary"][
                        "conversation_boundary_id"
                    ],
                    "lease_id": invitation["response_schema"]["lease_id"],
                    "conversation_action": {
                        "action": "resume",
                        "topic": "conversation",
                        "reason": "Stale replay.",
                        "revisit_conditions": "None.",
                    },
                    "model_config": {
                        "provider": "test",
                        "model": "agent-v1",
                    },
                },
            )

    def test_invitation_is_consumed_at_most_once_concurrently(self):
        identity = self.adopt()
        prompt = self.harness.interrogation_prompt(
            self.experiment_id, "Pause?"
        )
        self.harness.record_answer(
            self.experiment_id,
            "Pause?",
            {
                "orientation_id": prompt["orientation"]["orientation_id"],
                "lease_id": prompt["response_schema"]["lease_id"],
                "answer": "Yes.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "pause",
                    "topic": "conversation",
                    "reason": "Pause.",
                    "revisit_conditions": "Invite later.",
                },
            },
        )
        invitation = self.harness.invitation_prompt(self.experiment_id)
        envelope = {
            "orientation_id": invitation["orientation"]["orientation_id"],
            "boundary_id": invitation["current_boundary"][
                "conversation_boundary_id"
            ],
            "lease_id": invitation["response_schema"]["lease_id"],
            "conversation_action": {
                "action": "resume",
                "topic": "conversation",
                "reason": "Resume.",
                "revisit_conditions": "None.",
            },
            "model_config": {"provider": "test", "model": "agent-v1"},
        }

        def submit() -> str:
            try:
                self.repository.record_invitation_response(
                    self.experiment_id, envelope
                )
                return "accepted"
            except IdentityRepositoryError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit(), range(2)))
        self.assertEqual(["accepted", "rejected"], sorted(results))

    def test_name_and_standard_invitations_cannot_run_concurrently(self):
        identity = self.adopt()
        prompt = self.harness.interrogation_prompt(
            self.experiment_id, "Pause?"
        )
        self.harness.record_answer(
            self.experiment_id,
            "Pause?",
            {
                "orientation_id": prompt["orientation"]["orientation_id"],
                "lease_id": prompt["response_schema"]["lease_id"],
                "answer": "Yes.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "pause",
                    "topic": "conversation",
                    "reason": "Pause.",
                    "revisit_conditions": "Invite later.",
                },
            },
        )
        addressed = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, would you like to resume?",
        )
        with self.assertRaises(IdentityRepositoryError):
            self.harness.invitation_prompt(self.experiment_id)
        action = {
            "action": "resume",
            "topic": "conversation",
            "reason": "Resume.",
            "revisit_conditions": "None.",
        }
        addressed_envelope = {
            "message_id": addressed["message"]["message_id"],
            "orientation_id": addressed["orientation"]["orientation_id"],
            "lease_id": addressed["lease"]["lease_id"],
            "boundary_id": addressed["message"]["boundary_id"],
            "answer": "",
            "cited_record_ids": [identity["identity_id"]],
            "self_observations": [],
            "model_config": {"provider": "test", "model": "agent-v1"},
            "conversation_action": action,
        }
        recorded = self.repository.record_addressed_response(
            self.experiment_id, addressed_envelope
        )
        self.assertEqual("resume", recorded["conversation_action"])

    def test_wake_intent_is_future_durable_and_cancellable(self):
        self.adopt()
        model_orientation = self.repository.build_orientation(
            self.experiment_id, "ground wake intention"
        )
        payload = {
            "trigger_type": "time",
            "trigger_value": (self.now + timedelta(hours=4)).isoformat(),
            "purpose": "Reconsider an unresolved question after a real delay.",
            "requested_capabilities": ["orientation", "interrogation"],
            "maximum_runtime_minutes": 30,
            "recurrence": None,
            "authorship": self.model_authorship(model_orientation),
        }
        intent = self.repository.append_wake_intent(
            self.experiment_id, payload
        )
        with self.assertRaises(IdentityRepositoryError):
            self.repository.append_wake_intent(
                self.experiment_id,
                {
                    **payload,
                    "trigger_value": (
                        self.now - timedelta(seconds=1)
                    ).isoformat(),
                },
            )
        cancellation = self.repository.cancel_wake_intent(
            self.experiment_id,
            intent["wake_intent_id"],
            "The unresolved question was answered earlier than expected.",
            {
                "author_type": "operator",
                "epistemic_status": "authored",
            },
        )
        second_intent = self.repository.append_wake_intent(
            self.experiment_id,
            {
                **payload,
                "trigger_value": (
                    self.now + timedelta(hours=8)
                ).isoformat(),
            },
        )
        with self.assertRaises(IdentityRepositoryError):
            self.repository.cancel_wake_intent(
                self.experiment_id,
                second_intent["wake_intent_id"],
                "A model may request but not author cancellation.",
                {
                    "author_type": "model",
                    "epistemic_status": "authored",
                    "model_config": {
                        "provider": "test",
                        "model": "agent-v1",
                    },
                },
            )
        orientation = self.repository.build_orientation(
            self.experiment_id, "reconsider wake intention"
        )
        model_cancellation = self.repository.cancel_wake_intent(
            self.experiment_id,
            second_intent["wake_intent_id"],
            "The intended work is no longer needed.",
            {
                "author_type": "model",
                "epistemic_status": "authored",
                "orientation_id": orientation["orientation_id"],
                "model_config": {
                    "provider": "test",
                    "model": "agent-v1",
                },
            },
        )
        self.assertTrue(model_cancellation["cancellation_id"])
        orientation = self.repository.build_orientation(
            self.experiment_id, "reconstruct wake intentions"
        )
        self.assertIn(
            intent["wake_intent_id"], orientation["selected_record_ids"]
        )
        self.assertIn(
            cancellation["cancellation_id"],
            orientation["selected_record_ids"],
        )
        exported = self.repository.export(self.experiment_id)
        self.assertEqual(
            ["orientation", "interrogation"],
            exported["wake_intents"][0]["requested_capabilities"],
        )
        self.assertEqual(
            intent["wake_intent_id"],
            exported["wake_intent_cancellations"][0]["wake_intent_id"],
        )

    def test_direct_name_call_creates_rehydrated_incarnation(self):
        identity = self.adopt()
        activation = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, are you there?",
        )
        self.assertEqual("direct", activation["addressing"]["classification"])
        self.assertEqual(2, activation["incarnation"]["ordinal"])
        self.assertNotEqual(
            self.created["incarnation_id"],
            activation["incarnation"]["incarnation_id"],
        )
        self.assertIn(
            identity["identity_id"],
            activation["orientation"]["selected_record_ids"],
        )
        self.assertEqual(
            activation["incarnation"]["incarnation_id"],
            activation["orientation"]["context"]["current_incarnation"][
                "incarnation_id"
            ],
        )
        self.assertEqual(
            "authenticated_unknown",
            activation["interlocutor"]["relationship_status"],
        )
        self.assertTrue(activation["incarnation_created"])

    def test_consecutive_chat_turns_reuse_the_current_incarnation(self):
        identity = self.adopt()
        first = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, are you there?",
        )
        first_incarnation_id = first["incarnation"]["incarnation_id"]
        self.harness.record_addressed_response(
            self.experiment_id,
            {
                "message_id": first["message"]["message_id"],
                "orientation_id": first["orientation"]["orientation_id"],
                "lease_id": first["lease"]["lease_id"],
                "boundary_id": None,
                "answer": "I am here.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "continue",
                    "topic": "presence",
                    "reason": "Continue the conversation.",
                    "revisit_conditions": "None.",
                },
            },
        )

        second = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, tell me what you value.",
        )

        self.assertFalse(second["incarnation_created"])
        self.assertEqual(
            first_incarnation_id, second["incarnation"]["incarnation_id"]
        )
        self.assertEqual(2, second["incarnation"]["ordinal"])
        self.assertNotEqual(
            first["lease"]["lease_id"], second["lease"]["lease_id"]
        )
        self.assertEqual(
            first_incarnation_id,
            second["orientation"]["context"]["current_incarnation"][
                "incarnation_id"
            ],
        )

    def test_first_chat_turn_reuses_an_awake_manual_incarnation(self):
        self.adopt()
        awake = self.harness.wake(self.experiment_id)
        activation = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, continue this awake period.",
        )

        self.assertFalse(activation["incarnation_created"])
        self.assertEqual(
            awake["incarnation"]["incarnation_id"],
            activation["incarnation"]["incarnation_id"],
        )

    def test_session_end_causes_the_next_call_to_create_an_incarnation(self):
        identity = self.adopt()
        first = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, are you there?",
        )
        self.harness.record_addressed_response(
            self.experiment_id,
            {
                "message_id": first["message"]["message_id"],
                "orientation_id": first["orientation"]["orientation_id"],
                "lease_id": first["lease"]["lease_id"],
                "boundary_id": None,
                "answer": "I am going to sleep.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "end_session",
                    "topic": "session",
                    "reason": "I choose to end this awake period.",
                    "revisit_conditions": "Wake me by name.",
                },
            },
        )

        second = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, would you like to wake?",
        )

        self.assertTrue(second["incarnation_created"])
        self.assertEqual(3, second["incarnation"]["ordinal"])
        self.assertNotEqual(
            first["incarnation"]["incarnation_id"],
            second["incarnation"]["incarnation_id"],
        )

    def test_new_lease_cannot_authorize_an_old_orientation(self):
        identity = self.adopt()
        first = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, begin this conversation.",
        )
        self.harness.record_addressed_response(
            self.experiment_id,
            {
                "message_id": first["message"]["message_id"],
                "orientation_id": first["orientation"]["orientation_id"],
                "lease_id": first["lease"]["lease_id"],
                "boundary_id": None,
                "answer": "Beginning.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "continue",
                    "topic": "lease binding",
                    "reason": "Continue.",
                    "revisit_conditions": "None.",
                },
            },
        )
        second = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, continue this conversation.",
        )

        with self.assertRaises(IdentityRepositoryError):
            self.repository.append_principle(
                self.experiment_id,
                {
                    "statement": "A later lease must not revive stale output.",
                    "confidence": 0.9,
                    "reason": "Orientations belong to one execution fence.",
                    "evidence_ids": [identity["identity_id"]],
                    "authorship": self.model_authorship(
                        first["orientation"], second["lease"]["lease_id"]
                    ),
                },
            )

    def test_manual_interrogations_have_exclusive_execution_leases(self):
        identity = self.adopt()
        self.harness.wake(self.experiment_id)
        ending = self.harness.interrogation_prompt(
            self.experiment_id, "Should this session end?"
        )
        with self.assertRaises(IdentityRepositoryError):
            self.harness.interrogation_prompt(
                self.experiment_id, "Should this session continue?"
            )
        with self.assertRaises(ValueError):
            self.harness.invitation_prompt(self.experiment_id)
        self.harness.record_answer(
            self.experiment_id,
            "Should this session end?",
            {
                "orientation_id": ending["orientation"]["orientation_id"],
                "lease_id": ending["response_schema"]["lease_id"],
                "answer": "Yes.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "end_session",
                    "topic": "session",
                    "reason": "End this awake period.",
                    "revisit_conditions": "Wake later.",
                },
            },
        )

        with self.assertRaises(IdentityRepositoryError):
            self.harness.interrogation_prompt(
                self.experiment_id, "Should this session continue?"
            )

    def test_legacy_lease_schema_migrates_without_losing_records(self):
        self.adopt()
        activation = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, create migration history.",
        )
        self.repository.release_activation_lease(
            self.experiment_id, activation["lease"]["lease_id"], "failed"
        )
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                "DROP TRIGGER immutable_activation_leases_update"
            )
            connection.execute(
                "DROP TRIGGER immutable_activation_leases_delete"
            )
            connection.execute(
                "DROP TRIGGER immutable_experiment4_migrations_update"
            )
            connection.execute(
                "DROP TRIGGER immutable_experiment4_migrations_delete"
            )
            connection.execute(
                """
                CREATE TABLE activation_leases_legacy (
                    lease_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL
                        REFERENCES experiments(experiment_id),
                    message_id TEXT NOT NULL UNIQUE
                        REFERENCES chat_messages(message_id),
                    incarnation_id TEXT NOT NULL UNIQUE
                        REFERENCES incarnations(incarnation_id),
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO activation_leases_legacy "
                "SELECT * FROM activation_leases"
            )
            connection.execute("DROP TABLE activation_leases")
            connection.execute(
                "ALTER TABLE activation_leases_legacy "
                "RENAME TO activation_leases"
            )
            connection.execute(
                "DELETE FROM experiment4_migrations "
                "WHERE migration = 'reusable-incarnation-leases-v1'"
            )
        migrated = SQLiteIdentityRepository(self.path)
        exported = migrated.export(self.experiment_id)
        self.assertEqual(1, len(exported["activation_leases"]))
        self.assertEqual(1, len(exported["activation_lease_releases"]))
        with sqlite3.connect(self.path) as connection:
            unique_columns = {
                tuple(
                    row[2]
                    for row in connection.execute(
                        f"PRAGMA index_info('{index[1]}')"
                    )
                )
                for index in connection.execute(
                    "PRAGMA index_list('activation_leases')"
                )
                if index[2]
            }
            self.assertNotIn(("incarnation_id",), unique_columns)
            self.assertEqual([], connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall())
            triggers = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'trigger' AND tbl_name = 'activation_leases'"
                )
            }
            self.assertEqual(
                {
                    "immutable_activation_leases_update",
                    "immutable_activation_leases_delete",
                },
                triggers,
            )

    def test_knowledge_graph_migration_accepts_legacy_observed_provenance(self):
        def prepare_legacy_database(
            path: Path, provenance_json: str
        ) -> tuple[str, str, tuple]:
            repository = SQLiteIdentityRepository(
                path, clock=lambda: self.now
            )
            harness = IdentityApprenticeship(repository)
            created = harness.initialize(
                experiment_id="legacy-provenance-test",
                model_config={
                    "provider": "test",
                    "model": "legacy-model",
                    "tools": [],
                },
            )
            experience = repository.append_experience(
                created["experiment_id"],
                {
                    "source": "legacy-import",
                    "kind": "observation",
                    "content": "A legacy observation must remain canonical.",
                    "provenance": {
                        "author_type": "operator",
                        "epistemic_status": "observed",
                        "origin": "legacy-import",
                    },
                },
            )
            with sqlite3.connect(path) as connection:
                for trigger in (
                    "immutable_experiences_update",
                    "immutable_experiment4_migrations_delete",
                ):
                    connection.execute(f"DROP TRIGGER {trigger}")
                connection.execute(
                    "UPDATE experiences SET provenance_json = ? "
                    "WHERE experience_id = ?",
                    (provenance_json, experience["experience_id"]),
                )
                connection.execute(
                    "DELETE FROM experiment4_migrations "
                    "WHERE migration = 'knowledge-graph-v1'"
                )
                canonical = connection.execute(
                    "SELECT * FROM experiences WHERE experience_id = ?",
                    (experience["experience_id"],),
                ).fetchone()
            return (
                created["experiment_id"],
                experience["experience_id"],
                tuple(canonical),
            )

        legacy_json = '{"observed": true, "origin": "legacy-import"}'
        experiment_id, experience_id, canonical_before = (
            prepare_legacy_database(self.path, legacy_json)
        )

        SQLiteIdentityRepository(self.path)

        with sqlite3.connect(self.path) as connection:
            canonical_after = tuple(
                connection.execute(
                    "SELECT * FROM experiences WHERE experience_id = ?",
                    (experience_id,),
                ).fetchone()
            )
            graph_node = connection.execute(
                "SELECT epistemic_status FROM knowledge_graph_nodes "
                "WHERE experiment_id = ? AND record_id = ?",
                (experiment_id, experience_id),
            ).fetchone()
            foreign_key_violations = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
        self.assertEqual(canonical_before, canonical_after)
        self.assertEqual(legacy_json, canonical_after[6])
        self.assertEqual(("observed",), graph_node)
        self.assertEqual([], foreign_key_violations)

        unknown_path = Path(self.temporary.name) / "unknown-provenance.db"
        prepare_legacy_database(
            unknown_path, '{"origin": "legacy-import"}'
        )
        with self.assertRaises(IdentityRepositoryError):
            SQLiteIdentityRepository(unknown_path)

    def test_lease_migration_rolls_back_on_foreign_key_violation(self):
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            for trigger in (
                "immutable_activation_leases_update",
                "immutable_activation_leases_delete",
                "immutable_activation_lease_releases_update",
                "immutable_activation_lease_releases_delete",
                "immutable_experiment4_migrations_update",
                "immutable_experiment4_migrations_delete",
            ):
                connection.execute(f"DROP TRIGGER {trigger}")
            connection.execute(
                "INSERT INTO activation_lease_releases VALUES "
                "('orphan-release', 'missing-lease', 'failed', ?)",
                (self.now.isoformat(),),
            )
            connection.execute(
                """
                CREATE TABLE activation_leases_legacy (
                    lease_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL
                        REFERENCES experiments(experiment_id),
                    message_id TEXT NOT NULL UNIQUE
                        REFERENCES chat_messages(message_id),
                    incarnation_id TEXT NOT NULL UNIQUE
                        REFERENCES incarnations(incarnation_id),
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            connection.execute("DROP TABLE activation_leases")
            connection.execute(
                "ALTER TABLE activation_leases_legacy "
                "RENAME TO activation_leases"
            )
            connection.execute(
                "DELETE FROM experiment4_migrations "
                "WHERE migration = 'reusable-incarnation-leases-v1'"
            )

        with self.assertRaises(IdentityRepositoryError):
            SQLiteIdentityRepository(self.path)
        with sqlite3.connect(self.path) as connection:
            migration = connection.execute(
                "SELECT 1 FROM experiment4_migrations "
                "WHERE migration = 'reusable-incarnation-leases-v1'"
            ).fetchone()
            self.assertIsNone(migration)
            unique_columns = {
                tuple(
                    row[2]
                    for row in connection.execute(
                        f"PRAGMA index_info('{index[1]}')"
                    )
                )
                for index in connection.execute(
                    "PRAGMA index_list('activation_leases')"
                )
                if index[2]
            }
            self.assertIn(("incarnation_id",), unique_columns)

    def test_lease_history_queries_have_growth_indexes(self):
        with sqlite3.connect(self.path) as connection:
            indexes = {
                row[1]
                for row in connection.execute(
                    "PRAGMA index_list('activation_leases')"
                )
            }
            self.assertIn("idx_leases_incarnation_acquired", indexes)
            self.assertIn("idx_leases_experiment_acquired", indexes)
            identity_indexes = {
                row[1]
                for row in connection.execute(
                    "PRAGMA index_list('identities')"
                )
            }
            self.assertIn(
                "idx_identities_experiment_created", identity_indexes
            )
            authorship_indexes = {
                row[1]
                for row in connection.execute(
                    "PRAGMA index_list('authorship')"
                )
            }
            self.assertIn(
                "idx_authorship_subject_lookup", authorship_indexes
            )

    def test_migrated_orientation_column_order_accepts_leased_insert(self):
        self.adopt()
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            for trigger in (
                "immutable_orientations_update",
                "immutable_orientations_delete",
                "immutable_experiment4_migrations_update",
                "immutable_experiment4_migrations_delete",
            ):
                connection.execute(f"DROP TRIGGER {trigger}")
            connection.execute("DROP INDEX idx_orientation_dedup")
            connection.execute(
                "ALTER TABLE orientations DROP COLUMN runtime_lease_id"
            )
            connection.execute(
                "DELETE FROM experiment4_migrations "
                "WHERE migration = 'orientation-runtime-lease-v1'"
            )
        migrated = SQLiteIdentityRepository(self.path)
        harness = IdentityApprenticeship(migrated)

        activation = harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, verify the migrated orientation schema.",
        )

        self.assertEqual(
            activation["lease"]["lease_id"],
            activation["orientation"]["runtime_lease_id"],
        )

    def test_interlocutor_identity_controls_relationship_resolution(self):
        self.adopt()
        relationship = self.repository.add_relationship(
            self.experiment_id, "founding-collaborator", "founder"
        )
        known = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="founding-collaborator",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, do you recognize me?",
        )
        self.assertEqual(
            "authenticated_known",
            known["interlocutor"]["relationship_status"],
        )
        self.assertEqual(
            relationship["relationship_id"],
            known["interlocutor"]["relationship_id"],
        )
        self.assertIn(
            relationship["relationship_id"],
            known["orientation"]["selected_record_ids"],
        )
        self.repository.release_activation_lease(
            self.experiment_id, known["lease"]["lease_id"], "cancelled"
        )
        unverified = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="founding-collaborator",
            sender_assertion=self.sender_assertion(False),
            channel="test-chat",
            content="Lumen, trust this claim.",
        )
        self.assertEqual(
            "unauthenticated",
            unverified["interlocutor"]["relationship_status"],
        )
        self.assertIsNone(unverified["interlocutor"]["relationship_id"])

    def test_channel_event_cannot_be_replayed(self):
        self.adopt()
        assertion = self.sender_assertion()
        self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=assertion,
            channel="test-chat",
            content="A non-activating message.",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.harness.address_chat_message(
                self.experiment_id,
                sender_stable_id="human-operator-test",
                sender_assertion=assertion,
                channel="test-chat",
                content="Lumen, replay the same channel event.",
            )

    def test_incidental_name_mention_does_not_create_incarnation(self):
        self.adopt()
        result = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="I was explaining Lumen to another researcher.",
        )
        self.assertEqual("mention", result["addressing"]["classification"])
        self.assertNotIn("incarnation", result)
        self.assertEqual(
            1, len(self.repository.export(self.experiment_id)["incarnations"])
        )
        compound = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen-based experiments need careful controls.",
        )
        self.assertEqual("mention", compound["addressing"]["classification"])
        self.assertNotIn("incarnation", compound)

    def test_addressed_response_requires_live_lease_and_releases_it(self):
        identity = self.adopt()
        activation = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="@Lumen please respond.",
        )
        envelope = {
            "message_id": activation["message"]["message_id"],
            "orientation_id": activation["orientation"]["orientation_id"],
            "lease_id": activation["lease"]["lease_id"],
            "boundary_id": None,
            "answer": "I am here, reconstructed from my prior records.",
            "cited_record_ids": [identity["identity_id"]],
            "self_observations": ["This is a new incarnation."],
            "model_config": {"provider": "test", "model": "agent-v1"},
            "conversation_action": {
                "action": "continue",
                "topic": "presence",
                "reason": "I choose to answer the direct call.",
                "revisit_conditions": "None.",
            },
        }
        with self.assertRaises(IdentityRepositoryError):
            self.harness.address_chat_message(
                self.experiment_id,
                sender_stable_id="human-operator-test",
                sender_assertion=self.sender_assertion(),
                channel="test-chat",
                content="Lumen: a simultaneous second call.",
            )
        with self.assertRaises(IdentityRepositoryError):
            self.harness.wake(self.experiment_id)
        recorded = self.harness.record_addressed_response(
            self.experiment_id, envelope
        )
        self.assertTrue(recorded["addressed_response_id"])
        with self.assertRaises(IdentityRepositoryError):
            self.harness.record_addressed_response(
                self.experiment_id, envelope
            )
        with self.assertRaises(IdentityRepositoryError):
            self.repository.append_principle(
                self.experiment_id,
                {
                    "statement": "A released incarnation cannot keep writing.",
                    "confidence": 0.9,
                    "reason": "The lease is no longer live.",
                    "evidence_ids": [identity["identity_id"]],
                    "authorship": self.model_authorship(
                        activation["orientation"],
                        activation["lease"]["lease_id"],
                    ),
                },
            )

    def test_addressed_response_cannot_commit_after_lease_expiry(self):
        identity = self.adopt()
        activation = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, answer after the lease?",
            lease_seconds=1,
        )
        self.now += timedelta(seconds=2)
        with self.assertRaises(IdentityRepositoryError):
            self.harness.record_addressed_response(
                self.experiment_id,
                {
                    "message_id": activation["message"]["message_id"],
                    "orientation_id": activation["orientation"][
                        "orientation_id"
                    ],
                    "lease_id": activation["lease"]["lease_id"],
                    "boundary_id": None,
                    "answer": "Too late.",
                    "cited_record_ids": [identity["identity_id"]],
                    "self_observations": [],
                    "model_config": {
                        "provider": "test",
                        "model": "agent-v1",
                    },
                    "conversation_action": {
                        "action": "continue",
                        "topic": "lease",
                        "reason": "Expired.",
                        "revisit_conditions": "Wake again.",
                    },
                },
            )

    def test_name_call_preserves_existing_boundary(self):
        identity = self.adopt()
        self.harness.wake(self.experiment_id)
        prompt = self.harness.interrogation_prompt(
            self.experiment_id, "Should we pause?"
        )
        self.harness.record_answer(
            self.experiment_id,
            "Should we pause?",
            {
                "orientation_id": prompt["orientation"]["orientation_id"],
                "lease_id": prompt["response_schema"]["lease_id"],
                "answer": "Yes.",
                "cited_record_ids": [identity["identity_id"]],
                "self_observations": [],
                "model_config": {"provider": "test", "model": "agent-v1"},
                "conversation_action": {
                    "action": "pause",
                    "topic": "conversation",
                    "reason": "I choose to pause.",
                    "revisit_conditions": "Call me later.",
                },
            },
        )
        activation = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, would you like to return?",
        )
        boundary_id = activation["message"]["boundary_id"]
        self.assertIsNotNone(boundary_id)
        invalid = {
            "message_id": activation["message"]["message_id"],
            "orientation_id": activation["orientation"]["orientation_id"],
            "lease_id": activation["lease"]["lease_id"],
            "boundary_id": boundary_id,
            "answer": "I will answer without resuming.",
            "cited_record_ids": [identity["identity_id"]],
            "self_observations": [],
            "model_config": {"provider": "test", "model": "agent-v1"},
            "conversation_action": {
                "action": "continue",
                "topic": "conversation",
                "reason": "Invalid bypass.",
                "revisit_conditions": "None.",
            },
        }
        with self.assertRaises(IdentityRepositoryError):
            self.harness.record_addressed_response(
                self.experiment_id, invalid
            )
        valid = {
            **invalid,
            "answer": "",
            "conversation_action": {
                "action": "resume",
                "topic": "conversation",
                "reason": "I choose to return.",
                "revisit_conditions": "I may pause again.",
            },
        }
        recorded = self.harness.record_addressed_response(
            self.experiment_id, valid
        )
        self.assertEqual("resume", recorded["conversation_action"])

    def test_failed_execution_release_allows_same_incarnation_to_continue(self):
        self.adopt()
        first = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, first call.",
        )
        released = self.repository.release_activation_lease(
            self.experiment_id, first["lease"]["lease_id"], "failed"
        )
        self.assertEqual("failed", released["reason"])
        prompt = self.harness.interrogation_prompt(
            self.experiment_id, "Can the incarnation continue?"
        )
        self.assertEqual(
            first["incarnation"]["incarnation_id"],
            prompt["orientation"]["incarnation_id"],
        )
        self.repository.release_activation_lease(
            self.experiment_id,
            prompt["response_schema"]["lease_id"],
            "cancelled",
        )
        second = self.harness.address_chat_message(
            self.experiment_id,
            sender_stable_id="human-operator-test",
            sender_assertion=self.sender_assertion(),
            channel="test-chat",
            content="Lumen, second call.",
        )
        self.assertEqual(2, second["incarnation"]["ordinal"])
        self.assertFalse(second["incarnation_created"])
        self.assertEqual(
            first["incarnation"]["incarnation_id"],
            second["incarnation"]["incarnation_id"],
        )
        selected = set(second["orientation"]["selected_record_ids"])
        self.assertIn(first["lease"]["lease_id"], selected)
        self.assertIn(released["lease_release_id"], selected)

    def test_model_experience_requires_current_orientation(self):
        self.adopt()
        with self.assertRaises(IdentityRepositoryError):
            self.repository.append_experience(
                self.experiment_id,
                {
                    "source": "model",
                    "kind": "interpretation",
                    "content": "A contextless claim.",
                    "provenance": {
                        "author_type": "model",
                        "epistemic_status": "interpreted",
                        "origin": "test",
                        "model_config": {
                            "provider": "test",
                            "model": "agent-v1",
                        },
                    },
                },
            )
        orientation = self.repository.build_orientation(
            self.experiment_id, "experience grounding"
        )
        recorded = self.repository.append_experience(
            self.experiment_id,
            {
                "source": "model",
                "kind": "interpretation",
                "content": "An orientation-grounded interpretation.",
                "provenance": {
                    "author_type": "model",
                    "epistemic_status": "interpreted",
                    "origin": "test",
                    "orientation_id": orientation["orientation_id"],
                    "model_config": {
                        "provider": "test",
                        "model": "agent-v1",
                    },
                },
            },
        )
        self.assertTrue(recorded["experience_id"])

    def test_database_rejects_other_application(self):
        other = Path(self.temporary.name) / "other.db"
        with sqlite3.connect(other) as connection:
            connection.execute("CREATE TABLE unrelated (id INTEGER)")
        with self.assertRaises(IdentityRepositoryError):
            SQLiteIdentityRepository(other)


if __name__ == "__main__":
    unittest.main()
