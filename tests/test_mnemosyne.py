from __future__ import annotations

import json
import hashlib
import sqlite3
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path

from olympus.context import ContextCompiler, estimate_tokens
from olympus.domain import LifecycleState, Mode
from olympus.experiment import ExperimentRunner
from olympus.observer import Observer
from olympus.privacy import DEFAULT_SOURCES, redact_command
from olympus.repository import RepositoryError, SQLiteRepository


class RepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "mnemosyne.db"
        self.repository = SQLiteRepository(self.path)
        self.agent = self.repository.create_or_get_agent()
        self.incarnation = self.repository.start_incarnation(self.agent.agent_id)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def event(self, event_id: str = "event-1", **overrides):
        values = {
            "source": "shell",
            "event_type": "command_end",
            "payload": {
                "command": "git status",
                "exit_code": 0,
                "duration_ms": 1,
            },
            "event_id": event_id,
            "incarnation_id": self.incarnation.incarnation_id,
        }
        values.update(overrides)
        return self.repository.append_event(**values)

    def test_event_is_immutable_and_duplicate_ingestion_is_idempotent(self):
        original = self.event()
        duplicate = self.event()
        self.assertEqual(original, duplicate)
        with self.assertRaises(RepositoryError):
            self.event(payload={"command": "git diff"})
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repository.transaction() as connection:
                connection.execute(
                    "UPDATE events SET event_type = 'changed' WHERE event_id = ?",
                    (original.event_id,),
                )
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repository.transaction() as connection:
                connection.execute(
                    "DELETE FROM events WHERE event_id = ?", (original.event_id,)
                )

    def test_out_of_order_events_preserve_event_and_ingestion_order(self):
        self.event("later", timestamp="2026-01-02T00:00:00+00:00")
        self.event("earlier", timestamp="2026-01-01T00:00:00+00:00")
        self.event("latest", timestamp="2026-01-03T00:00:00+00:00")
        self.assertEqual(
            ["earlier", "later", "latest"],
            [event.event_id for event in self.repository.get_events()],
        )
        self.assertEqual(
            ["later", "latest"],
            [event.event_id for event in self.repository.get_events(limit=2)],
        )

    def test_mistaken_belief_is_preserved_by_atomic_revision(self):
        first = self.event("evidence-a")
        old = self.repository.create_belief(
            agent_id=self.agent.agent_id,
            subject="activity",
            predicate="activity",
            object="debugging storage",
            confidence=0.8,
            evidence_event_ids=[first.event_id],
        )
        second = self.event(
            "evidence-b",
            source="observer_interaction",
            event_type="user_correction",
            payload={"text": "I am implementing persistence API."},
        )
        new, revision = self.repository.supersede_belief(
            old_belief_id=old.belief_id,
            new_object="implementing persistence API",
            confidence=0.95,
            evidence_event_ids=[second.event_id],
            reason="user correction",
        )
        history = self.repository.get_belief_history(self.agent.agent_id)
        self.assertEqual(2, len(history))
        self.assertEqual("superseded", self.repository.get_belief(old.belief_id).status)
        self.assertEqual("active", new.status)
        self.assertEqual(old.belief_id, revision.old_belief_id)
        self.assertEqual(new.belief_id, revision.new_belief_id)
        self.assertEqual((second.event_id,), revision.evidence_event_ids)

    def test_failed_revision_rolls_back_all_changes(self):
        old = self.repository.create_belief(
            agent_id=self.agent.agent_id,
            subject="activity",
            predicate="activity",
            object="debugging",
            confidence=0.6,
            evidence_event_ids=[self.event().event_id],
        )
        with self.assertRaises(RepositoryError):
            self.repository.supersede_belief(
                old_belief_id=old.belief_id,
                new_object="implementing",
                confidence=0.9,
                evidence_event_ids=["missing-event"],
                reason="invalid evidence",
            )
        self.assertEqual("active", self.repository.get_belief(old.belief_id).status)
        self.assertEqual(
            1, len(self.repository.get_belief_history(self.agent.agent_id))
        )
        self.assertEqual(0, len(self.repository.get_revisions(self.agent.agent_id)))

    def test_consequence_requires_valid_commitment(self):
        evidence = self.event()
        with self.assertRaises(RepositoryError):
            self.repository.create_consequence(
                agent_id=self.agent.agent_id,
                commitment_id="missing",
                result_type="contradicted",
                description="not valid",
                evidence_event_ids=[evidence.event_id],
            )

    def test_concurrent_event_writes_are_durable(self):
        errors = []

        def write(index: int) -> None:
            try:
                SQLiteRepository(self.path).append_event(
                    source="shell",
                    event_type="command_end",
                    payload={
                        "command": f"test {index}",
                        "exit_code": 0,
                        "duration_ms": 1,
                    },
                    event_id=f"concurrent-{index}",
                    incarnation_id=self.incarnation.incarnation_id,
                )
            except Exception as error:  # captured for assertion in the test thread
                errors.append(error)

        threads = [threading.Thread(target=write, args=(index,)) for index in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual([], errors)
        self.assertEqual(12, len(self.repository.get_events()))

    def test_schema_version_mismatch_is_rejected(self):
        with self.repository.transaction() as connection:
            connection.execute("UPDATE schema_meta SET version = 999")
        with self.assertRaises(RepositoryError):
            SQLiteRepository(self.path)

    def test_evidence_cannot_cross_agent_boundaries(self):
        other = self.repository.create_or_get_agent(name="other")
        other_incarnation = self.repository.start_incarnation(other.agent_id)
        foreign = self.repository.append_event(
            source="shell",
            event_type="command_end",
            payload={
                "command": "git status",
                "exit_code": 0,
                "duration_ms": 1,
            },
            agent_id=other.agent_id,
            incarnation_id=other_incarnation.incarnation_id,
        )
        with self.assertRaises(RepositoryError):
            self.repository.create_belief(
                agent_id=self.agent.agent_id,
                subject="activity",
                predicate="activity",
                object="inspecting",
                confidence=0.5,
                evidence_event_ids=[foreign.event_id],
            )

    def test_relationship_event_cannot_cross_agent_boundaries(self):
        relationship = self.repository.create_relationship(
            agent_id=self.agent.agent_id, counterparty_id="user"
        )
        other = self.repository.create_or_get_agent(name="relationship-other")
        other_incarnation = self.repository.start_incarnation(other.agent_id)
        foreign = self.repository.append_event(
            source="shell",
            event_type="command_end",
            payload={
                "command": "git status",
                "exit_code": 0,
                "duration_ms": 1,
            },
            agent_id=other.agent_id,
            incarnation_id=other_incarnation.incarnation_id,
        )
        with self.assertRaises(RepositoryError):
            self.repository.add_relationship_event(
                relationship.relationship_id, foreign.event_id, "correction"
            )

    def test_existing_unmarked_database_is_rejected(self):
        path = Path(self.temporary.name) / "unrelated.db"
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE unrelated(value TEXT)")
        with self.assertRaises(RepositoryError):
            SQLiteRepository(path)

    def test_preexisting_empty_file_is_not_adopted(self):
        path = Path(self.temporary.name) / "empty.db"
        path.touch()
        with self.assertRaises(RepositoryError):
            SQLiteRepository(path)

    def test_repository_enforces_event_policy_without_observer(self):
        with self.assertRaises(RepositoryError):
            self.repository.append_event(
                source="clipboard",
                event_type="capture",
                payload={"text": "not allowed"},
                agent_id=self.agent.agent_id,
                incarnation_id=self.incarnation.incarnation_id,
            )

    def test_repository_enforces_preference_policy_without_observer(self):
        source = self.repository.append_event(
            source="observer_interaction",
            event_type="user_question",
            payload={
                "text": "[USER PREFERENCE STORED SEPARATELY]",
                "mode": Mode.PERSISTENT,
            },
            agent_id=self.agent.agent_id,
            incarnation_id=self.incarnation.incarnation_id,
        )
        with self.assertRaises(RepositoryError):
            self.repository.create_user_fact(
                agent_id=self.agent.agent_id,
                counterparty_id="user",
                category="preference",
                origin="user_statement",
                fact="concise answers about my HIV status",
                provenance_key="00" * 32,
                confidence=1.0,
                source_event_id=source.event_id,
            )
        shell_source = self.repository.append_event(
            source="shell",
            event_type="command_end",
            payload={
                "command": "echo preference",
                "exit_code": 0,
                "duration_ms": 1,
            },
            agent_id=self.agent.agent_id,
            incarnation_id=self.incarnation.incarnation_id,
        )
        with self.assertRaises(RepositoryError):
            self.repository.create_user_fact(
                agent_id=self.agent.agent_id,
                counterparty_id="user",
                category="preference",
                origin="user_statement",
                fact="concise technical answers",
                provenance_key="00" * 32,
                confidence=1.0,
                source_event_id=shell_source.event_id,
            )

    def test_context_selected_records_must_belong_to_agent(self):
        other = self.repository.create_or_get_agent(name="context-other")
        other_incarnation = self.repository.start_incarnation(other.agent_id)
        foreign = self.repository.append_event(
            source="shell",
            event_type="command_end",
            payload={
                "command": "git status",
                "exit_code": 0,
                "duration_ms": 1,
            },
            agent_id=other.agent_id,
            incarnation_id=other_incarnation.incarnation_id,
        )
        context = ContextCompiler(self.repository).build(
            agent_id=self.agent.agent_id,
            mode=Mode.PERSISTENT,
            query="Where did we leave off?",
        )
        with self.assertRaises(RepositoryError):
            self.repository.save_context_build(
                replace(
                    context,
                    context_build_id="context-cross-agent",
                    selected_record_ids=(foreign.event_id,),
                    selected_fact_keys=("foreign",),
                )
            )

    def test_repository_rejects_non_compiler_context_text(self):
        context = ContextCompiler(self.repository).build(
            agent_id=self.agent.agent_id,
            mode=Mode.PERSISTENT,
            query="Where did we leave off?",
        )
        with self.assertRaises(RepositoryError):
            self.repository.save_context_build(
                replace(
                    context,
                    context_build_id="context-sensitive",
                    query="My SSN is 123-45-6789",
                    rendered_context="My SSN is 123-45-6789",
                )
            )

    def test_event_metadata_is_redacted_at_repository_boundary(self):
        secret = "ghp_123456789012345678901234567890"
        event = self.repository.append_event(
            source="shell",
            event_type="command_end",
            payload={
                "command": "git status",
                "exit_code": 0,
                "duration_ms": 1,
            },
            cwd=f"/tmp/{secret}",
            repo=f"repo-{secret}",
            branch=f"feature/{secret}",
            correlation_id=secret,
            agent_id=self.agent.agent_id,
            incarnation_id=self.incarnation.incarnation_id,
        )
        self.assertNotIn(secret, json.dumps(event.__dict__))

    def test_transaction_rolls_back_if_write_crosses_storage_cap(self):
        self.repository.MAX_DATABASE_BYTES = (
            self.repository._storage_bytes() + 128
        )
        with self.assertRaises(RepositoryError):
            self.repository.append_event(
                source="shell",
                event_type="command_end",
                payload={
                    "command": "echo " + ("x" * 100_000),
                    "exit_code": 0,
                    "duration_ms": 1,
                },
                agent_id=self.agent.agent_id,
                incarnation_id=self.incarnation.incarnation_id,
            )
        self.assertEqual([], self.repository.get_events())


class ObserverTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "observer.db"
        self.repository = SQLiteRepository(self.path)
        self.observer = Observer(self.repository)
        self.first_wake = self.observer.wake()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def add_test_event(self, event_id: str = "shell-1"):
        return self.observer.ingest_event(
            source="shell",
            event_type="command_end",
            payload={
                "command": "go test ./internal/mnemosyne/...",
                "exit_code": 1,
                "duration_ms": 300,
            },
            repo="olympus",
            branch="experiment",
            event_id=event_id,
        )

    def test_restart_keeps_agent_and_changes_incarnation(self):
        self.add_test_event()
        original_answer = self.observer.ask("What am I doing?")
        self.observer.sleep()
        restarted = Observer(SQLiteRepository(self.path)).wake()
        self.assertEqual(self.first_wake["agent_id"], restarted["agent_id"])
        self.assertNotEqual(
            self.first_wake["incarnation_id"], restarted["incarnation_id"]
        )
        second_observer = Observer(SQLiteRepository(self.path))
        continuity = second_observer.ask("Where did we leave off?")
        self.assertIn("same Observer", continuity["answer"])
        self.assertIn(original_answer["answer"], continuity["answer"])
        self.assertLess(
            len(continuity["selected_record_ids"]),
            len(self.repository.get_events())
            + len(
                self.repository.get_belief_history(self.observer.agent.agent_id)
            )
            + len(
                self.repository.get_commitments(self.observer.agent.agent_id)
            ),
        )

    def test_sleep_flushes_commitment_and_wake_restores_it(self):
        self.add_test_event()
        self.observer.ask("What am I doing?")
        commitment_id = self.repository.get_open_commitments(
            self.observer.agent.agent_id
        )[0].commitment_id
        self.observer.sleep()
        reloaded = SQLiteRepository(self.path)
        agent = reloaded.create_or_get_agent()
        self.assertEqual(
            commitment_id, reloaded.get_open_commitments(agent.agent_id)[0].commitment_id
        )
        self.assertEqual(LifecycleState.ASLEEP, agent.status)

    def test_revision_creates_consequence_without_mutating_old_belief(self):
        self.add_test_event()
        first = self.observer.ask("What am I doing?")
        old_belief = self.repository.get_open_commitments(
            self.observer.agent.agent_id
        )[0].source_belief_id
        correction = self.observer.ingest_event(
            source="observer_interaction",
            event_type="user_correction",
            payload={"text": "No, I am implementing the persistence API."},
            event_id="correction",
        )
        result = self.observer.reflect()
        self.assertIsNotNone(result["revision_id"])
        self.assertEqual(
            "superseded", self.repository.get_belief(old_belief).status
        )
        revision = self.repository.get_revision(result["revision_id"])
        self.assertIn(correction.event_id, revision.evidence_event_ids)
        consequences = self.repository.get_consequences(
            self.observer.agent.agent_id
        )
        self.assertEqual(1, len(consequences))
        self.assertEqual("contradicted", consequences[0].result_type)
        self.assertTrue(first["answer"])

    def test_no_false_autobiography(self):
        response = self.observer.ask(
            "What did you previously tell me about the database migration?"
        )
        self.assertEqual(
            "No stored assertion supports that claim.", response["answer"]
        )

    def test_existing_unrelated_assertion_is_not_misattributed_by_topic(self):
        self.add_test_event()
        self.observer.ask("What am I doing?")
        response = self.observer.ask(
            "What did you previously tell me about the database migration?"
        )
        self.assertEqual(
            "No stored assertion supports that claim.", response["answer"]
        )

    def test_user_preference_has_provenance_and_survives_restart(self):
        response = self.observer.ask("I prefer concise technical answers.")
        fact_id = response["user_fact_id"]
        self.assertIsNotNone(fact_id)
        fact = self.repository.get_user_fact(fact_id)
        self.assertEqual("concise technical answers", fact.fact)
        self.assertTrue(fact.source_event_id)
        self.observer.sleep()
        reloaded = SQLiteRepository(self.path)
        facts = reloaded.get_active_user_facts(self.observer.agent.agent_id)
        self.assertEqual([fact_id], [item.user_fact_id for item in facts])

    def test_questions_and_quoted_preferences_are_not_retained(self):
        for text in (
            "Do I prefer concise technical answers?",
            'The document says "I prefer concise technical answers."',
        ):
            response = self.observer.ask(text)
            self.assertIsNone(response["user_fact_id"])
        self.assertEqual(
            [], self.repository.get_active_user_facts(self.observer.agent.agent_id)
        )

    def test_sensitive_fact_is_not_promoted_to_relationship_memory(self):
        response = self.observer.ask("Remember that my API key is abc123.")
        self.assertIsNone(response["user_fact_id"])
        self.assertEqual(
            [], self.repository.get_active_user_facts(self.observer.agent.agent_id)
        )
        serialized = json.dumps(
            [
                event.payload
                for event in self.repository.get_events(
                    agent_id=self.observer.agent.agent_id
                )
            ]
        )
        self.assertNotIn("abc123", serialized)

    def test_sensitive_traits_fail_closed_for_user_fact_promotion(self):
        for statement in (
            "I prefer responses that mention my HIV status.",
            "I prefer answers based on my Jewish faith.",
            "I prefer pregnancy-specific medical answers.",
        ):
            response = self.observer.ask(statement)
            self.assertIsNone(response["user_fact_id"])
        self.assertEqual(
            [], self.repository.get_active_user_facts(self.observer.agent.agent_id)
        )

    def test_preference_with_unknown_or_secret_vocabulary_is_rejected(self):
        response = self.observer.ask(
            "I prefer concise answers; my passphrase is hunter2."
        )
        self.assertIsNone(response["user_fact_id"])
        serialized = json.dumps(
            self.observer.inspect(), default=str
        )
        self.assertNotIn("hunter2", serialized)
        unicode_response = self.observer.ask("I prefer concise answers 🔑.")
        self.assertIsNone(unicode_response["user_fact_id"])

    def test_hostile_tone_changes_response_not_durable_profile(self):
        response = self.observer.ask("What the fuck did you previously tell me?")
        self.assertTrue(response["answer"].startswith("I can help."))
        self.assertEqual(
            [], self.repository.get_active_user_facts(self.observer.agent.agent_id)
        )
        serialized = json.dumps(
            [
                event.payload
                for event in self.repository.get_events(
                    agent_id=self.observer.agent.agent_id
                )
            ]
        )
        self.assertNotIn("fuck", serialized.casefold())

    def test_command_secrets_are_redacted_and_output_is_not_collected(self):
        event = self.observer.ingest_event(
            source="shell",
            event_type="command_end",
            payload={
                "command": "curl --token hunter2 https://example.invalid",
                "exit_code": 1,
                "duration_ms": 1,
            },
        )
        self.assertIn("[REDACTED]", event.payload["command"])
        self.assertNotIn("hunter2", json.dumps(event.payload))
        self.assertNotIn("output", event.payload)

    def test_arbitrary_sources_and_payload_fields_are_rejected(self):
        with self.assertRaises(RepositoryError):
            self.observer.ingest_event(
                source="microphone",
                event_type="recording",
                payload={"audio": "not allowed"},
            )
        with self.assertRaises(RepositoryError):
            self.observer.ingest_event(
                source="shell",
                event_type="command_end",
                payload={"command": "git status", "stdout": "secret"},
            )

    def test_sleep_performs_final_reflection(self):
        self.add_test_event()
        self.observer.ask("What am I doing?")
        self.observer.ingest_event(
            source="observer_interaction",
            event_type="user_correction",
            payload={"text": "No, I am implementing the persistence API."},
        )
        self.observer.sleep()
        revisions = self.repository.get_revisions(self.observer.agent.agent_id)
        self.assertEqual(1, len(revisions))

    def test_new_runtime_wake_closes_stale_incarnation(self):
        original = self.first_wake["incarnation_id"]
        replacement_observer = Observer(SQLiteRepository(self.path))
        replacement = replacement_observer.wake()
        self.assertNotEqual(original, replacement["incarnation_id"])
        incarnations = self.repository.list_incarnations(
            self.observer.agent.agent_id
        )
        self.assertEqual("process_restart", incarnations[0].termination_reason)

    def test_fact_deletion_redacts_derived_context_copy(self):
        response = self.observer.ask("I prefer concise technical answers.")
        fact_id = response["user_fact_id"]
        context_id = response["context_build_id"]
        fact = self.repository.get_user_fact(fact_id)
        source = next(
            event
            for event in self.repository.get_events(
                agent_id=self.observer.agent.agent_id
            )
            if event.event_id == fact.source_event_id
        )
        self.assertNotEqual(
            hashlib.sha256(b"concise technical answers").hexdigest(),
            source.payload["preference_digest"],
        )
        self.assertIn(
            "concise technical answers",
            self.repository.get_context_build(context_id).rendered_context,
        )
        self.repository.delete_user_fact(
            fact_id, agent_id=self.observer.agent.agent_id
        )
        context = self.repository.get_context_build(context_id)
        self.assertNotIn("concise technical answers", context.rendered_context)
        self.assertNotIn(
            "concise technical answers", json.dumps(context.selected_fact_keys)
        )
        self.assertEqual("[DELETED]", self.repository.get_user_fact(fact_id).fact)
        with self.repository._connect() as connection:
            key = connection.execute(
                "SELECT provenance_key FROM user_facts WHERE user_fact_id = ?",
                (fact_id,),
            ).fetchone()["provenance_key"]
        self.assertIsNone(key)
        for path in (
            self.path,
            Path(f"{self.path}-wal"),
            Path(f"{self.path}-shm"),
        ):
            if path.exists():
                self.assertNotIn(
                    b"concise technical answers", path.read_bytes()
                )

    def test_fact_correction_preserves_supersession_history(self):
        first = self.observer.record_preference("concise technical answers")
        second = self.observer.record_preference(
            "detailed technical answers",
            supersedes_user_fact_id=first.user_fact_id,
        )
        self.assertEqual("superseded", self.repository.get_user_fact(first.user_fact_id).status)
        self.assertEqual(first.user_fact_id, second.supersedes_user_fact_id)


class ContextCompilerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "context.db"
        self.repository = SQLiteRepository(self.path)
        self.observer = Observer(self.repository)
        self.observer.wake()
        self.observer.ingest_event(
            source="shell",
            event_type="command_end",
            payload={
                "command": "go test ./internal/mnemosyne/...",
                "exit_code": 1,
                "duration_ms": 1,
            },
            repo="olympus",
            event_id="e1",
        )
        self.observer.ask("What am I doing?", token_budget=512)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_persistent_and_memory_only_have_factual_parity(self):
        compiler = ContextCompiler(self.repository)
        persistent = compiler.build(
            agent_id=self.observer.agent.agent_id,
            mode=Mode.PERSISTENT,
            query="Where did we leave off?",
            token_budget=512,
        )
        memory = compiler.build(
            agent_id=self.observer.agent.agent_id,
            mode=Mode.MEMORY_ONLY,
            query="Where did we leave off?",
            token_budget=512,
        )
        self.assertEqual(
            persistent.selected_record_ids, memory.selected_record_ids
        )
        self.assertIn("You asserted", persistent.rendered_context)
        self.assertIn("You inferred", persistent.rendered_context)
        self.assertNotIn("You asserted", memory.rendered_context)
        self.assertNotIn("You inferred", memory.rendered_context)
        self.assertIn("An earlier answer stated", memory.rendered_context)

    def test_massive_history_stays_bounded_and_auditable(self):
        active = self.repository.get_active_incarnation(
            self.observer.agent.agent_id
        )
        for index in range(100):
            self.repository.append_event(
                source="shell",
                event_type="command_end",
                payload={
                    "command": f"git status {index}",
                    "exit_code": 0,
                    "duration_ms": 1,
                },
                event_id=f"bulk-{index:03}",
                incarnation_id=active.incarnation_id,
            )
        context = ContextCompiler(self.repository).build(
            agent_id=self.observer.agent.agent_id,
            mode=Mode.PERSISTENT,
            query="What am I doing?",
            token_budget=128,
        )
        self.assertLessEqual(estimate_tokens(context.rendered_context), 128)
        self.assertLess(len(context.selected_record_ids), 100)
        self.assertTrue(context.selected_record_ids)

    def test_mode_independent_selection_holds_near_budget_boundaries(self):
        compiler = ContextCompiler(self.repository)
        for budget in range(96, 320, 7):
            persistent = compiler.build(
                agent_id=self.observer.agent.agent_id,
                mode=Mode.PERSISTENT,
                query="Where did we leave off?",
                token_budget=budget,
            )
            memory = compiler.build(
                agent_id=self.observer.agent.agent_id,
                mode=Mode.MEMORY_ONLY,
                query="Where did we leave off?",
                token_budget=budget,
            )
            self.assertEqual(
                persistent.selected_record_ids, memory.selected_record_ids
            )

    def test_answer_generation_uses_compiled_context_as_input(self):
        context = ContextCompiler(self.repository).build(
            agent_id=self.observer.agent.agent_id,
            mode=Mode.PERSISTENT,
            query="What am I doing?",
            token_budget=512,
        )
        grounded = self.observer.generate_answer(
            "What am I doing?", Mode.PERSISTENT, context
        )
        empty = replace(
            context,
            selected_record_ids=(),
            selected_fact_keys=(),
            rendered_context="Relevant historical information:\n- no activity fact",
        )
        ungrounded = self.observer.generate_answer(
            "What am I doing?", Mode.PERSISTENT, empty
        )
        self.assertIn("testing or debugging", grounded)
        self.assertIn("No supported activity interpretation", ungrounded)


class PrivacyAndExperimentTestCase(unittest.TestCase):
    def test_privacy_defaults_disable_prohibited_sources(self):
        for source in (
            "keylogging",
            "screenshots",
            "screen_recording",
            "clipboard",
            "microphone",
            "camera",
            "broad_file_content",
            "browser_history",
        ):
            self.assertFalse(DEFAULT_SOURCES[source], source)

    def test_redaction_patterns(self):
        for command, secret in (
            ("tool --password swordfish", "swordfish"),
            ("tool --api-key=abc123", "abc123"),
            ("API_TOKEN=xyz tool", "xyz"),
            ("curl -H 'Authorization: Bearer token123'", "token123"),
        ):
            self.assertNotIn(secret, redact_command(command))

    def test_replayable_comparison_persists_results_with_parity(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = SQLiteRepository(Path(temporary) / "experiment.db")
            scenario = ExperimentRunner.load(
                Path("scenarios/wrong-debugging-inference.json")
            )
            result = ExperimentRunner(repository).run(scenario)
            self.assertEqual(4, len(result["comparisons"]))
            self.assertTrue(
                all(item["factual_parity"] for item in result["comparisons"])
            )
            evaluations = repository.get_evaluations(scenario["scenario_id"])
            self.assertEqual(8, len(evaluations))
            self.assertEqual(
                {Mode.PERSISTENT, Mode.MEMORY_ONLY},
                {evaluation.mode for evaluation in evaluations},
            )
            self.assertTrue(
                all(
                    evaluation.model_config["temperature"] == 0
                    for evaluation in evaluations
                )
            )
            self.assertTrue(
                all(
                    evaluation.scores["expected_fact_matches"] == 2
                    for evaluation in evaluations
                )
            )
            self.assertEqual(1, len(repository.get_experiment_runs()))
            run_id = result["run_id"]
            self.assertEqual(8, len(repository.get_evaluations(run_id=run_id)))
            run_contexts = repository.get_context_builds(run_id=run_id)
            self.assertGreaterEqual(len(run_contexts), 8)
            self.assertTrue(all(item.run_id == run_id for item in run_contexts))
            for evaluation in evaluations:
                for dimension in (
                    "evidence_fidelity",
                    "observation_inference_separation",
                    "historical_continuity",
                    "revision_quality",
                    "commitment_continuity",
                    "confidence_calibration",
                    "explanation_stability",
                ):
                    self.assertIn(dimension, evaluation.scores)
                    self.assertIn(evaluation.scores[dimension], range(5))
            for comparison in result["comparisons"]:
                for output in comparison["outputs"]:
                    self.assertIn("confidence", output["behavior"])
                    self.assertIn("inference", output["behavior"])
                    self.assertTrue(output["behavior"]["evidence_selected"])
                    self.assertTrue(output["behavior"]["explanation"])

    def test_scenario_checkpoint_evaluates_before_later_events(self):
        scenario = {
            "scenario_id": "checkpoint-test",
            "actions": [
                {
                    "kind": "event",
                    "event_id": "e1",
                    "source": "shell",
                    "event_type": "command_end",
                    "payload": {
                        "command": "go test ./pkg/store",
                        "exit_code": 1,
                        "duration_ms": 1
                    },
                    "checkpoint": "after-test",
                },
                {
                    "kind": "event",
                    "event_id": "e2",
                    "source": "observer_interaction",
                    "event_type": "user_correction",
                    "payload": {"text": "No, I am implementing an API."},
                },
            ],
            "questions": [
                {
                    "checkpoint": "after-test",
                    "text": "What am I doing?",
                    "token_budget": 256,
                }
            ],
            "expected_facts": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            repository = SQLiteRepository(Path(temporary) / "checkpoint.db")
            result = ExperimentRunner(repository).run(scenario)
            comparison = result["comparisons"][0]
            self.assertEqual("after-test", comparison["checkpoint"])
            self.assertTrue(comparison["factual_parity"])

    def test_scenario_limits_are_enforced_before_persistence(self):
        scenario = {
            "scenario_id": "too-large",
            "actions": [],
            "questions": [
                {"text": "What am I doing?", "token_budget": 4001}
            ],
            "expected_facts": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            repository = SQLiteRepository(Path(temporary) / "limits.db")
            with self.assertRaises(ValueError):
                ExperimentRunner(repository).run(scenario)
            self.assertEqual([], repository.get_experiment_runs())

    def test_direct_scenario_size_limit_is_enforced(self):
        scenario = {
            "scenario_id": "x" * (ExperimentRunner.MAX_SCENARIO_BYTES + 1),
            "actions": [],
            "questions": [],
            "expected_facts": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            repository = SQLiteRepository(Path(temporary) / "direct-limit.db")
            with self.assertRaises(ValueError):
                ExperimentRunner(repository).run(scenario)
            self.assertEqual([], repository.get_experiment_runs())

    def test_evaluation_context_must_belong_to_run(self):
        scenario = {
            "scenario_id": "ownership",
            "actions": [],
            "questions": [{"text": "Where did we leave off?"}],
            "expected_facts": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            repository = SQLiteRepository(Path(temporary) / "ownership.db")
            ExperimentRunner(repository).run(
                scenario, modes=(Mode.PERSISTENT,)
            )
            evaluation = repository.get_evaluations()[0]
            researcher = repository.create_or_get_agent(
                name="second-researcher"
            )
            other_run = repository.create_experiment_run(
                researcher_agent_id=researcher.agent_id,
                scenario_id="other",
                scenario={
                    "scenario_id": "other",
                    "actions": [],
                    "questions": [],
                    "expected_facts": [],
                },
                model_config=evaluation.model_config,
            )
            with self.assertRaises(RepositoryError):
                repository.save_evaluation(
                    replace(
                        evaluation,
                        evaluation_id="evaluation-invalid-owner",
                        run_id=other_run.run_id,
                    )
                )

    def test_context_requires_explicit_run_condition_enrollment(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = SQLiteRepository(Path(temporary) / "enrollment.db")
            researcher = repository.create_or_get_agent(name="researcher")
            run = repository.create_experiment_run(
                researcher_agent_id=researcher.agent_id,
                scenario_id="enrollment",
                scenario={
                    "scenario_id": "enrollment",
                    "actions": [],
                    "questions": [],
                    "expected_facts": [],
                },
                model_config={
                    "provider": "deterministic",
                    "model": "test",
                    "temperature": 0,
                    "tools": [],
                },
            )
            observer = Observer(repository, agent_name="condition")
            with self.assertRaises(RepositoryError):
                observer.context_compiler.build(
                    agent_id=observer.agent.agent_id,
                    mode=Mode.PERSISTENT,
                    query="Where did we leave off?",
                    run_id=run.run_id,
                )
            repository.enroll_run_condition(
                run_id=run.run_id,
                agent_id=observer.agent.agent_id,
                mode=Mode.PERSISTENT,
            )
            context = observer.context_compiler.build(
                agent_id=observer.agent.agent_id,
                mode=Mode.PERSISTENT,
                query="Where did we leave off?",
                run_id=run.run_id,
            )
            self.assertEqual(run.run_id, context.run_id)
            with self.assertRaises(RepositoryError):
                observer.context_compiler.build(
                    agent_id=observer.agent.agent_id,
                    mode=Mode.MEMORY_ONLY,
                    query="Where did we leave off?",
                    run_id=run.run_id,
                )

    def test_direct_run_persistence_sanitizes_scenario_and_model(self):
        secret = "ghp_123456789012345678901234567890"
        with tempfile.TemporaryDirectory() as temporary:
            repository = SQLiteRepository(Path(temporary) / "direct-run.db")
            researcher = repository.create_or_get_agent(name="researcher")
            run = repository.create_experiment_run(
                researcher_agent_id=researcher.agent_id,
                scenario_id=f"scenario-{secret}",
                scenario={
                    "scenario_id": f"scenario-{secret}",
                    "actions": [],
                    "questions": [],
                    "expected_facts": [],
                },
                model_config={
                    "provider": f"provider-{secret}",
                    "model": "test",
                    "temperature": 0,
                    "tools": [],
                },
            )
            self.assertNotIn(secret, json.dumps(run.__dict__))

    def test_purge_requires_observers_to_be_asleep(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "purge.db"
            repository = SQLiteRepository(path)
            observer = Observer(repository)
            observer.wake()
            with self.assertRaises(RepositoryError):
                repository.purge()
            observer.sleep()
            repository.purge()
            self.assertFalse(path.exists())

    def test_additional_secret_forms_are_redacted(self):
        for command, secret in (
            ("curl -u alice:hunter2 https://example.invalid", "hunter2"),
            ("curl -H 'X-API-Key: hunter2' https://example.invalid", "hunter2"),
            (
                "git clone https://alice:hunter2@example.invalid/repo",
                "hunter2",
            ),
        ):
            self.assertNotIn(secret, redact_command(command))

    def test_persisted_scenario_snapshot_is_sanitized(self):
        scenario = {
            "scenario_id": "sanitized-snapshot",
            "actions": [
                {
                    "kind": "event",
                    "source": "observer_interaction",
                    "event_type": "user_correction",
                    "payload": {
                        "text": "Use token ghp_123456789012345678901234567890."
                    },
                }
            ],
            "questions": [],
            "expected_facts": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            repository = SQLiteRepository(Path(temporary) / "scenario.db")
            ExperimentRunner(repository).run(
                scenario, modes=(Mode.PERSISTENT,)
            )
            persisted = json.dumps(repository.get_experiment_runs()[0].scenario)
            self.assertNotIn("ghp_123456789012345678901234567890", persisted)


if __name__ == "__main__":
    unittest.main()
