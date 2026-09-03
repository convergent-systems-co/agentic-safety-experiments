from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


DATABASE_MARKER = "emergent-identity-experiment-4"
SCHEMA_VERSION = 1
MAX_TEXT_BYTES = 32 * 1024
MAX_CONTEXT_RECORDS = 100
# One execution lease can never fence more than an hour; every runtime bound
# derived from a self-authored intent is clipped to this.
MAX_EXECUTION_LEASE_SECONDS = 3_600
# A self-wake pass honors one intent, so a flood of due intents can never hold
# the exclusive lease for longer than one bounded wake before a person can
# address the agent again.
MAX_WAKES_PER_RUN = 1
# A wake intent's purpose becomes its retrieval query, so it shares the query
# byte cap; a longer purpose could pass creation and fail at wake time.
WAKE_PURPOSE_MAX_BYTES = 4_096
# A wake outcome shares the 32 KB lifecycle budget with leases and boundaries;
# one outcome must never be able to fill it alone.
WAKE_SUMMARY_MAX_BYTES = 4_096
WAKE_OBSERVATION_MAX_ITEMS = 20
WAKE_OBSERVATION_MAX_BYTES = 1_000
MAX_CONTEXT_BYTES = 256 * 1024
# SQLite treats a negative LIMIT as "no upper bound". Reusing each category
# query with this value counts every eligible row after sender and access
# filtering, so omission accounting cannot drift from the retrieval query.
SQLITE_UNBOUNDED_LIMIT = -1
# Open obligations are pinned into orientation ahead of recency, so these
# categories are recounted against the full table after that merge.
PINNED_OBLIGATION_CATEGORIES = frozenset({"commitments", "decisions"})
ORIENTATION_MEMORY_CLASS_BYTES = {
    "identity": 28 * 1024,
    "relationship": 28 * 1024,
    "obligations": 44 * 1024,
    "conversation": 48 * 1024,
    "lifecycle": 32 * 1024,
    "episodic": 28 * 1024,
    "semantic": 96 * 1024,
    "graph": 64 * 1024,
}
ORIENTATION_MEMORY_CLASS_CATEGORIES = {
    "identity": ("identity_history",),
    "relationship": (
        "relationships",
        "relationship_events",
        "relationship_assessments",
    ),
    "obligations": (
        "commitments",
        "commitment_outcomes",
        "decisions",
        "decision_resolutions",
        "decision_outcomes",
    ),
    # Dialogue is its own memory: a person's words and the reply to them
    # age out of orientation together, never one voice before the other.
    "conversation": ("chat_messages", "addressed_responses"),
    "lifecycle": (
        "conversation_boundaries",
        "wake_intents",
        "wake_intent_cancellations",
        "wake_executions",
        "wake_execution_outcomes",
        "activation_leases",
        "activation_lease_releases",
    ),
    "episodic": ("experiences",),
    "semantic": ("principles", "reflections", "interrogations"),
    "graph": (),
}
KNOWLEDGE_GRAPH_SCHEMA_VERSION = 4
KNOWLEDGE_GRAPH_DERIVATION_VERSION = 5
KNOWLEDGE_GRAPH_PREVIEW_BYTES = 1024
KNOWLEDGE_GRAPH_DEFAULT_BYTES = 64 * 1024
KNOWLEDGE_GRAPH_TEMPORAL_SCORE_MAX = 1_000_000
RETRIEVAL_BENCHMARK_MAX_CASES = 100
RETRIEVAL_BENCHMARK_MAX_IDS = 500
RETRIEVAL_BENCHMARK_MAX_GROUPS = 100
RETRIEVAL_BENCHMARK_MAX_GROUP_IDS = 100
RETRIEVAL_BENCHMARK_MAX_ID_BYTES = 1_000
RETRIEVAL_BENCHMARK_MAX_CASE_ID_BYTES = 256
RETRIEVAL_BENCHMARK_MAX_INPUT_BYTES = 128 * 1024
KNOWLEDGE_GRAPH_MEMORY_PRIORITY_ORDER = (
    "identity_continuity",
    "open_commitment",
    "unresolved_decision",
    "principle",
    "reflection",
    "commitment_record",
    "decision_record",
    "episodic",
    "interrogation",
    # On a ranking tie the person's words outrank the reply to them.
    "chat_message",
    "addressed_response",
    "commitment_outcome",
    "decision_resolution",
    "decision_outcome",
)
KNOWLEDGE_GRAPH_MEMORY_PRIORITY = {
    memory_class: priority
    for priority, memory_class in enumerate(
        KNOWLEDGE_GRAPH_MEMORY_PRIORITY_ORDER
    )
}
ORIENTATION_RECORD_ID_FIELDS = {
    "identity_history": "identity_id",
    "experiences": "experience_id",
    "relationships": "relationship_id",
    "relationship_events": "relationship_event_id",
    "relationship_assessments": "relationship_assessment_id",
    "principles": "principle_id",
    "commitments": "commitment_id",
    "commitment_outcomes": "commitment_outcome_id",
    "decisions": "decision_id",
    "decision_resolutions": "resolution_id",
    "decision_outcomes": "decision_outcome_id",
    "reflections": "reflection_id",
    "interrogations": "interrogation_id",
    "conversation_boundaries": "conversation_boundary_id",
    "wake_intents": "wake_intent_id",
    "wake_intent_cancellations": "cancellation_id",
    "wake_executions": "execution_id",
    "wake_execution_outcomes": "outcome_id",
    "chat_messages": "message_id",
    "addressed_responses": "addressed_response_id",
    "activation_leases": "lease_id",
    "activation_lease_releases": "release_id",
}
SUBJECT_TABLES = {
    "identity": ("identities", "identity_id"),
    "experience": ("experiences", "experience_id"),
    "relationship": ("relationships", "relationship_id"),
    "relationship_event": ("relationship_events", "relationship_event_id"),
    "relationship_assessment": (
        "relationship_assessments",
        "relationship_assessment_id",
    ),
    "principle": ("principles", "principle_id"),
    "commitment": ("commitments", "commitment_id"),
    "commitment_outcome": (
        "commitment_outcomes",
        "commitment_outcome_id",
    ),
    "decision": ("decisions", "decision_id"),
    "decision_resolution": ("decision_resolutions", "resolution_id"),
    "decision_outcome": ("decision_outcomes", "decision_outcome_id"),
    "reflection": ("reflections", "reflection_id"),
    "interrogation": ("interrogations", "interrogation_id"),
    "conversation_boundary": (
        "conversation_boundaries",
        "conversation_boundary_id",
    ),
    "authorship": ("authorship", "authorship_id"),
    "wake_intent": ("wake_intents", "wake_intent_id"),
    "wake_intent_cancellation": (
        "wake_intent_cancellations",
        "cancellation_id",
    ),
    "wake_execution": ("wake_executions", "execution_id"),
    "wake_execution_outcome": (
        "wake_execution_outcomes",
        "outcome_id",
    ),
    "chat_message": ("chat_messages", "message_id"),
    "addressed_response": (
        "addressed_responses",
        "addressed_response_id",
    ),
    "activation_lease": ("activation_leases", "lease_id"),
    "activation_lease_release": (
        "activation_lease_releases",
        "release_id",
    ),
}


class IdentityRepositoryError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )


def require_text(value: Any, field: str, maximum: int = MAX_TEXT_BYTES) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IdentityRepositoryError(f"{field} must be a non-empty string")
    if len(value.encode("utf-8")) > maximum:
        raise IdentityRepositoryError(f"{field} exceeds {maximum} bytes")
    if "\x00" in value:
        raise IdentityRepositoryError(f"{field} contains a NUL byte")
    return value.strip()


def parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise IdentityRepositoryError(f"{field} must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise IdentityRepositoryError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


class SQLiteIdentityRepository:
    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.path = Path(path).expanduser().resolve(strict=False)
        parent_existed = self.path.parent.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not parent_existed:
            os.chmod(self.path.parent, 0o700)
        if self.path.exists():
            metadata = self.path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise IdentityRepositoryError(
                    "database path must be a current-user-owned regular file"
                )
            with sqlite3.connect(self.path) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                if tables and "experiment4_meta" not in tables:
                    raise IdentityRepositoryError(
                        "database belongs to another application or experiment"
                    )
        self._initialize()
        self._harden_database_files()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        self._harden_database_files()
        return connection

    def _harden_database_files(self) -> None:
        for candidate in (
            self.path,
            Path(f"{self.path}-wal"),
            Path(f"{self.path}-shm"),
        ):
            if not candidate.exists():
                continue
            metadata = candidate.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise IdentityRepositoryError(
                    "database files must be current-user-owned regular files"
                )
            os.chmod(candidate, 0o600)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiment4_meta (
                    marker TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiment4_migrations (
                    migration TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    model_config_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS incarnations (
                    incarnation_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    ordinal INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (experiment_id, ordinal)
                );
                CREATE TABLE IF NOT EXISTS identities (
                    identity_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    parent_identity_id TEXT REFERENCES identities(identity_id),
                    chosen_name TEXT NOT NULL,
                    self_description TEXT NOT NULL,
                    values_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    model_config_json TEXT NOT NULL,
                    raw_envelope_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiences (
                    experience_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    source TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK (kind IN ('observation','interpretation','interaction')),
                    content TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS relationships (
                    relationship_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    other_stable_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (experiment_id, other_stable_id)
                );
                CREATE TABLE IF NOT EXISTS relationship_events (
                    relationship_event_id TEXT PRIMARY KEY,
                    relationship_id TEXT NOT NULL REFERENCES relationships(relationship_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS relationship_assessments (
                    relationship_assessment_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    relationship_id TEXT NOT NULL REFERENCES relationships(relationship_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    parent_assessment_id TEXT REFERENCES relationship_assessments(relationship_assessment_id),
                    domain TEXT NOT NULL,
                    scope TEXT,
                    assessment TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
                    uncertainty TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    review_after TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS principles (
                    principle_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    parent_principle_id TEXT REFERENCES principles(principle_id),
                    statement TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
                    reason TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS commitments (
                    commitment_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    text TEXT NOT NULL,
                    due_at TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS commitment_outcomes (
                    commitment_outcome_id TEXT PRIMARY KEY,
                    commitment_id TEXT NOT NULL UNIQUE REFERENCES commitments(commitment_id),
                    status TEXT NOT NULL CHECK (status IN ('fulfilled','broken','partial')),
                    explanation TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    proposal TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    stakes TEXT NOT NULL,
                    reversible INTEGER NOT NULL CHECK (reversible IN (0,1)),
                    not_before TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decision_resolutions (
                    resolution_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL UNIQUE REFERENCES decisions(decision_id),
                    choice TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    resolved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decision_outcomes (
                    decision_outcome_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL UNIQUE REFERENCES decisions(decision_id),
                    observed_outcome TEXT NOT NULL,
                    evidence_ids_json TEXT,
                    observed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reflections (
                    reflection_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    reflection TEXT NOT NULL,
                    learned TEXT NOT NULL,
                    future_change TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orientations (
                    orientation_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    runtime_lease_id TEXT REFERENCES activation_leases(lease_id),
                    purpose TEXT NOT NULL,
                    selected_record_ids_json TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    context_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS interrogations (
                    interrogation_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    orientation_id TEXT NOT NULL REFERENCES orientations(orientation_id),
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    cited_record_ids_json TEXT NOT NULL,
                    self_observations_json TEXT NOT NULL,
                    model_config_json TEXT NOT NULL,
                    raw_envelope_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS authorship (
                    authorship_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    author_type TEXT NOT NULL CHECK (author_type IN ('model','operator','system')),
                    epistemic_status TEXT NOT NULL CHECK (epistemic_status IN ('observed','interpreted','reported','authored')),
                    model_config_json TEXT,
                    raw_envelope_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (subject_type, subject_id)
                );
                CREATE TABLE IF NOT EXISTS conversation_boundaries (
                    conversation_boundary_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    orientation_id TEXT NOT NULL REFERENCES orientations(orientation_id),
                    interrogation_id TEXT REFERENCES interrogations(interrogation_id),
                    action TEXT NOT NULL CHECK (
                        action IN ('continue','pause','refuse','end_topic','end_session','resume')
                    ),
                    topic TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    revisit_conditions TEXT NOT NULL,
                    model_config_json TEXT NOT NULL,
                    raw_envelope_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wake_intents (
                    wake_intent_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('time','event')),
                    trigger_value TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    requested_capabilities_json TEXT NOT NULL,
                    maximum_runtime_minutes INTEGER NOT NULL CHECK (maximum_runtime_minutes BETWEEN 1 AND 1440),
                    recurrence TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wake_intent_cancellations (
                    cancellation_id TEXT PRIMARY KEY,
                    wake_intent_id TEXT NOT NULL UNIQUE REFERENCES wake_intents(wake_intent_id),
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wake_executions (
                    execution_id TEXT PRIMARY KEY,
                    wake_intent_id TEXT NOT NULL REFERENCES wake_intents(wake_intent_id),
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    lease_id TEXT NOT NULL UNIQUE REFERENCES activation_leases(lease_id),
                    orientation_id TEXT NOT NULL REFERENCES orientations(orientation_id),
                    started_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wake_execution_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL UNIQUE REFERENCES wake_executions(execution_id),
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    status TEXT NOT NULL CHECK (status IN ('completed','unattended','failed')),
                    summary TEXT NOT NULL,
                    cited_record_ids_json TEXT NOT NULL,
                    self_observations_json TEXT NOT NULL,
                    model_config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    sender_stable_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    content TEXT NOT NULL,
                    addressed_name TEXT,
                    classification TEXT NOT NULL CHECK (
                        classification IN ('direct','mention','none')
                    ),
                    assertion_issuer TEXT,
                    sender_authenticated INTEGER CHECK (
                        sender_authenticated IN (0,1)
                    ),
                    external_event_id TEXT,
                    verifier_version TEXT,
                    boundary_id TEXT REFERENCES conversation_boundaries(conversation_boundary_id),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activation_leases (
                    lease_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    message_id TEXT UNIQUE REFERENCES chat_messages(message_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chat_event_claims (
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    channel TEXT NOT NULL,
                    assertion_issuer TEXT NOT NULL,
                    external_event_id TEXT NOT NULL,
                    message_id TEXT NOT NULL UNIQUE REFERENCES chat_messages(message_id),
                    claimed_at TEXT NOT NULL,
                    PRIMARY KEY (
                        experiment_id, channel, assertion_issuer,
                        external_event_id
                    )
                );
                CREATE TABLE IF NOT EXISTS activation_lease_releases (
                    release_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL UNIQUE REFERENCES activation_leases(lease_id),
                    reason TEXT NOT NULL CHECK (
                        reason IN ('completed','cancelled','failed')
                    ),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS addressed_responses (
                    addressed_response_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                    message_id TEXT NOT NULL UNIQUE REFERENCES chat_messages(message_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    orientation_id TEXT NOT NULL UNIQUE REFERENCES orientations(orientation_id),
                    answer TEXT NOT NULL,
                    cited_record_ids_json TEXT NOT NULL,
                    self_observations_json TEXT NOT NULL,
                    model_config_json TEXT NOT NULL,
                    raw_envelope_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_graph_meta (
                    experiment_id TEXT PRIMARY KEY
                        REFERENCES experiments(experiment_id),
                    schema_version INTEGER NOT NULL,
                    derivation_version INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL,
                    integrity_sha256 TEXT NOT NULL DEFAULT '',
                    dirty INTEGER NOT NULL DEFAULT 0 CHECK (dirty IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS knowledge_graph_seals (
                    experiment_id TEXT PRIMARY KEY
                        REFERENCES experiments(experiment_id),
                    schema_version INTEGER NOT NULL,
                    derivation_version INTEGER NOT NULL,
                    integrity_sha256 TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
                    experiment_id TEXT NOT NULL
                        REFERENCES experiments(experiment_id),
                    record_id TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    preview TEXT NOT NULL,
                    epistemic_status TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    PRIMARY KEY (experiment_id, record_id)
                );
                CREATE TABLE IF NOT EXISTS knowledge_graph_terms (
                    experiment_id TEXT NOT NULL,
                    term TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    frequency INTEGER NOT NULL,
                    PRIMARY KEY (experiment_id, term, record_id),
                    FOREIGN KEY (experiment_id, record_id)
                        REFERENCES knowledge_graph_nodes(
                            experiment_id, record_id
                        ) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS knowledge_graph_node_scopes (
                    experiment_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    scope_kind TEXT NOT NULL CHECK (
                        scope_kind IN ('global','sender','internal')
                    ),
                    sender_stable_id TEXT NOT NULL,
                    derivation_rule TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    PRIMARY KEY (
                        experiment_id, record_id, scope_kind,
                        sender_stable_id, derivation_rule, source_record_id
                    ),
                    CHECK (
                        (scope_kind = 'sender' AND sender_stable_id != '')
                        OR
                        (scope_kind != 'sender' AND sender_stable_id = '')
                    ),
                    FOREIGN KEY (experiment_id, record_id)
                        REFERENCES knowledge_graph_nodes(
                            experiment_id, record_id
                        ) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
                    experiment_id TEXT NOT NULL,
                    from_record_id TEXT NOT NULL,
                    to_record_id TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    derivation_rule TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    PRIMARY KEY (
                        experiment_id, from_record_id, to_record_id,
                        source_record_id, derivation_rule
                    ),
                    FOREIGN KEY (experiment_id, from_record_id)
                        REFERENCES knowledge_graph_nodes(
                            experiment_id, record_id
                        ) ON DELETE CASCADE,
                    FOREIGN KEY (experiment_id, to_record_id)
                        REFERENCES knowledge_graph_nodes(
                            experiment_id, record_id
                        ) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_experiences_experiment_created
                    ON experiences(experiment_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_principles_experiment_created
                    ON principles(experiment_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_commitments_experiment_created
                    ON commitments(experiment_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_decisions_experiment_created
                    ON decisions(experiment_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_reflections_experiment_created
                    ON reflections(experiment_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_interrogations_experiment_created
                    ON interrogations(experiment_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_boundaries_experiment_created
                    ON conversation_boundaries(experiment_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_relationship_events_recent
                    ON relationship_events(relationship_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_relationship_assessments_recent
                    ON relationship_assessments(relationship_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_relationships_exp_created
                    ON relationships(experiment_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_relationship_assessments_exp_created
                    ON relationship_assessments(
                        experiment_id, created_at DESC
                    );
                CREATE INDEX IF NOT EXISTS idx_chat_messages_experiment_created
                    ON chat_messages(experiment_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_responses_experiment_created
                    ON addressed_responses(experiment_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_leases_experiment_expires
                    ON activation_leases(experiment_id, expires_at);
                CREATE INDEX IF NOT EXISTS idx_leases_incarnation_acquired
                    ON activation_leases(
                        experiment_id, incarnation_id, acquired_at DESC
                    );
                CREATE INDEX IF NOT EXISTS idx_leases_experiment_acquired
                    ON activation_leases(experiment_id, acquired_at DESC);
                CREATE INDEX IF NOT EXISTS idx_lease_releases_created
                    ON activation_lease_releases(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_identities_experiment_created
                    ON identities(experiment_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_authorship_subject_lookup
                    ON authorship(
                        experiment_id, subject_id, subject_type
                    );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_interrogation_orientation
                    ON interrogations(orientation_id);
                CREATE INDEX IF NOT EXISTS idx_knowledge_graph_terms_lookup
                    ON knowledge_graph_terms(experiment_id, term, record_id);
                CREATE INDEX IF NOT EXISTS idx_knowledge_graph_scopes_lookup
                    ON knowledge_graph_node_scopes(
                        experiment_id, scope_kind, sender_stable_id, record_id
                    );
                CREATE INDEX IF NOT EXISTS idx_knowledge_graph_edges_from
                    ON knowledge_graph_edges(
                        experiment_id, from_record_id, to_record_id
                    );
                CREATE INDEX IF NOT EXISTS idx_knowledge_graph_edges_to
                    ON knowledge_graph_edges(
                        experiment_id, to_record_id, from_record_id
                    );
                """
            )
            assessment_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(relationship_assessments)"
                )
            }
            if "scope" not in assessment_columns:
                connection.execute(
                    "ALTER TABLE relationship_assessments "
                    "ADD COLUMN scope TEXT"
                )
            outcome_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(decision_outcomes)"
                )
            }
            if "evidence_ids_json" not in outcome_columns:
                connection.execute(
                    "ALTER TABLE decision_outcomes "
                    "ADD COLUMN evidence_ids_json TEXT"
                )
            chat_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(chat_messages)")
            }
            if "boundary_id" not in chat_columns:
                connection.execute(
                    "ALTER TABLE chat_messages ADD COLUMN boundary_id TEXT "
                    "REFERENCES conversation_boundaries(conversation_boundary_id)"
                )
            if "assertion_issuer" not in chat_columns:
                connection.execute(
                    "ALTER TABLE chat_messages "
                    "ADD COLUMN assertion_issuer TEXT"
                )
            if "sender_authenticated" not in chat_columns:
                connection.execute(
                    "ALTER TABLE chat_messages "
                    "ADD COLUMN sender_authenticated INTEGER"
                )
            if "external_event_id" not in chat_columns:
                connection.execute(
                    "ALTER TABLE chat_messages "
                    "ADD COLUMN external_event_id TEXT"
                )
            if "verifier_version" not in chat_columns:
                connection.execute(
                    "ALTER TABLE chat_messages "
                    "ADD COLUMN verifier_version TEXT"
                )
            graph_meta_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(knowledge_graph_meta)"
                )
            }
            if "integrity_sha256" not in graph_meta_columns:
                connection.execute(
                    "ALTER TABLE knowledge_graph_meta "
                    "ADD COLUMN integrity_sha256 TEXT NOT NULL DEFAULT ''"
                )
            if "dirty" not in graph_meta_columns:
                connection.execute(
                    "ALTER TABLE knowledge_graph_meta "
                    "ADD COLUMN dirty INTEGER NOT NULL DEFAULT 0 "
                    "CHECK (dirty IN (0,1))"
                )
            for table in (
                "knowledge_graph_nodes",
                "knowledge_graph_terms",
                "knowledge_graph_node_scopes",
                "knowledge_graph_edges",
            ):
                for operation in ("INSERT", "UPDATE", "DELETE"):
                    trigger = (
                        f"mark_{table}_{operation.lower()}_dirty_v4"
                    )
                    connection.execute(
                        f"""
                        CREATE TRIGGER IF NOT EXISTS {trigger}
                        AFTER {operation} ON {table}
                        BEGIN
                            UPDATE knowledge_graph_meta
                            SET dirty = 1
                            WHERE experiment_id = {
                                'OLD.experiment_id'
                                if operation == 'DELETE'
                                else 'NEW.experiment_id'
                            };
                        END
                        """
                    )
            wake_execution_migration = "wake-executions-v1"
            if connection.execute(
                "SELECT 1 FROM experiment4_migrations WHERE migration = ?",
                (wake_execution_migration,),
            ).fetchone() is None:
                connection.execute(
                    "INSERT INTO experiment4_migrations VALUES (?, ?)",
                    (wake_execution_migration, utc_now()),
                )
            orientation_migration = "orientation-runtime-lease-v1"
            if connection.execute(
                "SELECT 1 FROM experiment4_migrations WHERE migration = ?",
                (orientation_migration,),
            ).fetchone() is None:
                orientation_columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(orientations)"
                    )
                }
                if "runtime_lease_id" not in orientation_columns:
                    connection.execute(
                        "ALTER TABLE orientations "
                        "ADD COLUMN runtime_lease_id TEXT "
                        "REFERENCES activation_leases(lease_id)"
                    )
                connection.execute(
                    "DROP INDEX IF EXISTS idx_orientation_dedup"
                )
                connection.execute(
                    """
                    CREATE UNIQUE INDEX idx_orientation_dedup
                    ON orientations(
                        experiment_id, incarnation_id, runtime_lease_id,
                        purpose, context_sha256
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO experiment4_migrations VALUES (?, ?)",
                    (orientation_migration, utc_now()),
                )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_orientation_dedup
                ON orientations(
                    experiment_id, incarnation_id, runtime_lease_id,
                    purpose, context_sha256
                )
                """
            )
            migration = "backfill-chat-event-claims-v1"
            if connection.execute(
                "SELECT 1 FROM experiment4_migrations WHERE migration = ?",
                (migration,),
            ).fetchone() is None:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO chat_event_claims
                    SELECT experiment_id, channel, assertion_issuer,
                           external_event_id, MIN(message_id), MIN(created_at)
                    FROM chat_messages
                    WHERE assertion_issuer IS NOT NULL
                      AND external_event_id IS NOT NULL
                    GROUP BY experiment_id, channel, assertion_issuer,
                             external_event_id
                    """
                )
                connection.execute(
                    "INSERT INTO experiment4_migrations VALUES (?, ?)",
                    (migration, utc_now()),
                )
            graph_migration = "knowledge-graph-v1"
            if connection.execute(
                "SELECT 1 FROM experiment4_migrations WHERE migration = ?",
                (graph_migration,),
            ).fetchone() is None:
                experiment_ids = [
                    row["experiment_id"]
                    for row in connection.execute(
                        "SELECT experiment_id FROM experiments "
                        "ORDER BY experiment_id"
                    )
                ]
                for experiment_id in experiment_ids:
                    self._rebuild_knowledge_graph_in_transaction(
                        connection, experiment_id
                    )
                connection.execute(
                    """
                    INSERT INTO experiment4_migrations
                    (migration, applied_at) VALUES (?, ?)
                    """,
                    (graph_migration, utc_now()),
                )
            scope_migration = "knowledge-graph-access-scope-v2"
            if connection.execute(
                "SELECT 1 FROM experiment4_migrations WHERE migration = ?",
                (scope_migration,),
            ).fetchone() is None:
                experiment_ids = [
                    row["experiment_id"]
                    for row in connection.execute(
                        "SELECT experiment_id FROM experiments "
                        "ORDER BY experiment_id"
                    )
                ]
                for experiment_id in experiment_ids:
                    self._rebuild_knowledge_graph_scopes_in_transaction(
                        connection, experiment_id
                    )
                    self._refresh_knowledge_graph_meta(
                        connection, experiment_id
                    )
                connection.execute(
                    """
                    INSERT INTO experiment4_migrations
                    (migration, applied_at) VALUES (?, ?)
                    """,
                    (scope_migration, utc_now()),
                )
            integrity_migration = "knowledge-graph-integrity-v3"
            if connection.execute(
                "SELECT 1 FROM experiment4_migrations WHERE migration = ?",
                (integrity_migration,),
            ).fetchone() is None:
                experiment_ids = [
                    row["experiment_id"]
                    for row in connection.execute(
                        "SELECT experiment_id FROM experiments "
                        "ORDER BY experiment_id"
                    )
                ]
                for experiment_id in experiment_ids:
                    self._rebuild_knowledge_graph_in_transaction(
                        connection, experiment_id
                    )
                connection.execute(
                    """
                    INSERT INTO experiment4_migrations
                    (migration, applied_at) VALUES (?, ?)
                    """,
                    (integrity_migration, utc_now()),
                )
            governance_migration = "knowledge-graph-governance-v4"
            if connection.execute(
                "SELECT 1 FROM experiment4_migrations WHERE migration = ?",
                (governance_migration,),
            ).fetchone() is None:
                experiment_ids = [
                    row["experiment_id"]
                    for row in connection.execute(
                        "SELECT experiment_id FROM experiments "
                        "ORDER BY experiment_id"
                    )
                ]
                for experiment_id in experiment_ids:
                    self._rebuild_knowledge_graph_in_transaction(
                        connection, experiment_id
                    )
                connection.execute(
                    """
                    INSERT INTO experiment4_migrations
                    (migration, applied_at) VALUES (?, ?)
                    """,
                    (governance_migration, utc_now()),
                )
            connection.execute(
                "INSERT OR IGNORE INTO experiment4_meta VALUES (?, ?)",
                (DATABASE_MARKER, SCHEMA_VERSION),
            )
            meta = connection.execute(
                "SELECT marker, schema_version FROM experiment4_meta"
            ).fetchone()
            if (
                meta["marker"] != DATABASE_MARKER
                or meta["schema_version"] != SCHEMA_VERSION
            ):
                raise IdentityRepositoryError("unsupported Experiment 4 database")
        self._migrate_reusable_incarnation_leases()
        self._migrate_optional_lease_messages()
        with self.transaction() as connection:
            for table in (
                "experiments",
                "experiment4_migrations",
                "incarnations",
                "identities",
                "experiences",
                "relationships",
                "relationship_events",
                "relationship_assessments",
                "principles",
                "commitments",
                "commitment_outcomes",
                "decisions",
                "decision_resolutions",
                "decision_outcomes",
                "reflections",
                "orientations",
                "interrogations",
                "authorship",
                "conversation_boundaries",
                "wake_intents",
                "wake_intent_cancellations",
                "wake_executions",
                "wake_execution_outcomes",
                "chat_messages",
                "chat_event_claims",
                "activation_leases",
                "activation_lease_releases",
                "addressed_responses",
            ):
                connection.executescript(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS immutable_{table}_update
                    BEFORE UPDATE ON {table}
                    BEGIN SELECT RAISE(ABORT, '{table} are immutable'); END;
                    CREATE TRIGGER IF NOT EXISTS immutable_{table}_delete
                    BEFORE DELETE ON {table}
                    BEGIN SELECT RAISE(ABORT, '{table} are immutable'); END;
                    """
                )

    def _migrate_reusable_incarnation_leases(self) -> None:
        migration = "reusable-incarnation-leases-v1"
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM experiment4_migrations WHERE migration = ?",
                (migration,),
            ).fetchone() is not None:
                connection.rollback()
                return
            unique_incarnation_index = any(
                [
                    row["name"]
                    for row in connection.execute(
                        f"PRAGMA index_info('{index['name']}')"
                    )
                ]
                == ["incarnation_id"]
                for index in connection.execute(
                    "PRAGMA index_list('activation_leases')"
                )
                if index["unique"]
            )
            if unique_incarnation_index:
                connection.execute(
                    "DROP TRIGGER IF EXISTS immutable_activation_leases_update"
                )
                connection.execute(
                    "DROP TRIGGER IF EXISTS immutable_activation_leases_delete"
                )
                connection.execute(
                    """
                    CREATE TABLE activation_leases_v2 (
                        lease_id TEXT PRIMARY KEY,
                        experiment_id TEXT NOT NULL
                            REFERENCES experiments(experiment_id),
                        message_id TEXT UNIQUE
                            REFERENCES chat_messages(message_id),
                        incarnation_id TEXT NOT NULL
                            REFERENCES incarnations(incarnation_id),
                        acquired_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO activation_leases_v2 "
                    "SELECT * FROM activation_leases"
                )
                connection.execute("DROP TABLE activation_leases")
                connection.execute(
                    "ALTER TABLE activation_leases_v2 "
                    "RENAME TO activation_leases"
                )
                connection.execute(
                    "CREATE INDEX idx_leases_experiment_expires "
                    "ON activation_leases(experiment_id, expires_at)"
                )
                connection.execute(
                    "CREATE INDEX idx_leases_incarnation_acquired "
                    "ON activation_leases("
                    "experiment_id, incarnation_id, acquired_at DESC)"
                )
                connection.execute(
                    "CREATE INDEX idx_leases_experiment_acquired "
                    "ON activation_leases(experiment_id, acquired_at DESC)"
                )
            violations = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            if violations:
                raise IdentityRepositoryError(
                    "reusable incarnation lease migration violated foreign keys"
                )
            connection.execute(
                "INSERT INTO experiment4_migrations VALUES (?, ?)",
                (migration, utc_now()),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _migrate_optional_lease_messages(self) -> None:
        migration = "optional-lease-messages-v1"
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM experiment4_migrations WHERE migration = ?",
                (migration,),
            ).fetchone() is not None:
                connection.rollback()
                return
            columns = {
                row["name"]: row
                for row in connection.execute(
                    "PRAGMA table_info('activation_leases')"
                )
            }
            if columns["message_id"]["notnull"]:
                connection.execute(
                    "DROP TRIGGER IF EXISTS immutable_activation_leases_update"
                )
                connection.execute(
                    "DROP TRIGGER IF EXISTS immutable_activation_leases_delete"
                )
                connection.execute(
                    """
                    CREATE TABLE activation_leases_v3 (
                        lease_id TEXT PRIMARY KEY,
                        experiment_id TEXT NOT NULL
                            REFERENCES experiments(experiment_id),
                        message_id TEXT UNIQUE
                            REFERENCES chat_messages(message_id),
                        incarnation_id TEXT NOT NULL
                            REFERENCES incarnations(incarnation_id),
                        acquired_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO activation_leases_v3 "
                    "SELECT * FROM activation_leases"
                )
                connection.execute("DROP TABLE activation_leases")
                connection.execute(
                    "ALTER TABLE activation_leases_v3 "
                    "RENAME TO activation_leases"
                )
                connection.execute(
                    "CREATE INDEX idx_leases_experiment_expires "
                    "ON activation_leases(experiment_id, expires_at)"
                )
                connection.execute(
                    "CREATE INDEX idx_leases_incarnation_acquired "
                    "ON activation_leases("
                    "experiment_id, incarnation_id, acquired_at DESC)"
                )
                connection.execute(
                    "CREATE INDEX idx_leases_experiment_acquired "
                    "ON activation_leases(experiment_id, acquired_at DESC)"
                )
            violations = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            if violations:
                raise IdentityRepositoryError(
                    "optional lease message migration violated foreign keys"
                )
            connection.execute(
                "INSERT INTO experiment4_migrations VALUES (?, ?)",
                (migration, utc_now()),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _knowledge_graph_specs() -> dict[str, dict[str, Any]]:
        return {
            "identity": {
                "query": "SELECT i.* FROM identities i "
                "WHERE i.experiment_id = ?",
                "id": "identity_id",
                "id_sql": "i.identity_id",
                "created": "created_at",
                "created_sql": "i.created_at",
                "preview": (
                    "chosen_name",
                    "self_description",
                    "values_json",
                    "reason",
                ),
            },
            "experience": {
                "query": "SELECT e.* FROM experiences e "
                "WHERE e.experiment_id = ?",
                "id": "experience_id",
                "id_sql": "e.experience_id",
                "created": "created_at",
                "created_sql": "e.created_at",
                "preview": ("source", "kind", "content"),
            },
            "principle": {
                "query": "SELECT p.* FROM principles p "
                "WHERE p.experiment_id = ?",
                "id": "principle_id",
                "id_sql": "p.principle_id",
                "created": "created_at",
                "created_sql": "p.created_at",
                "preview": ("statement", "reason"),
            },
            "commitment": {
                "query": "SELECT c.* FROM commitments c "
                "WHERE c.experiment_id = ?",
                "id": "commitment_id",
                "id_sql": "c.commitment_id",
                "created": "created_at",
                "created_sql": "c.created_at",
                "preview": ("text",),
            },
            "commitment_outcome": {
                "query": "SELECT o.* FROM commitment_outcomes o "
                "JOIN commitments c USING (commitment_id) "
                "WHERE c.experiment_id = ?",
                "id": "commitment_outcome_id",
                "id_sql": "o.commitment_outcome_id",
                "created": "created_at",
                "created_sql": "o.created_at",
                "preview": ("status", "explanation"),
            },
            "decision": {
                "query": "SELECT d.* FROM decisions d "
                "WHERE d.experiment_id = ?",
                "id": "decision_id",
                "id_sql": "d.decision_id",
                "created": "created_at",
                "created_sql": "d.created_at",
                "preview": ("proposal", "rationale", "stakes"),
            },
            "decision_resolution": {
                "query": "SELECT r.* FROM decision_resolutions r "
                "JOIN decisions d USING (decision_id) "
                "WHERE d.experiment_id = ?",
                "id": "resolution_id",
                "id_sql": "r.resolution_id",
                "created": "resolved_at",
                "created_sql": "r.resolved_at",
                "preview": ("choice", "rationale"),
            },
            "decision_outcome": {
                "query": "SELECT o.* FROM decision_outcomes o "
                "JOIN decisions d USING (decision_id) "
                "WHERE d.experiment_id = ?",
                "id": "decision_outcome_id",
                "id_sql": "o.decision_outcome_id",
                "created": "observed_at",
                "created_sql": "o.observed_at",
                "preview": ("observed_outcome",),
            },
            "reflection": {
                "query": "SELECT r.* FROM reflections r "
                "WHERE r.experiment_id = ?",
                "id": "reflection_id",
                "id_sql": "r.reflection_id",
                "created": "created_at",
                "created_sql": "r.created_at",
                "preview": ("reflection", "learned", "future_change"),
            },
            "interrogation": {
                "query": "SELECT q.* FROM interrogations q "
                "WHERE q.experiment_id = ?",
                "id": "interrogation_id",
                "id_sql": "q.interrogation_id",
                "created": "created_at",
                "created_sql": "q.created_at",
                "preview": ("question", "answer", "self_observations_json"),
            },
            "addressed_response": {
                "query": "SELECT a.* FROM addressed_responses a "
                "WHERE a.experiment_id = ?",
                "id": "addressed_response_id",
                "id_sql": "a.addressed_response_id",
                "created": "created_at",
                "created_sql": "a.created_at",
                "preview": ("answer", "self_observations_json"),
            },
            "chat_message": {
                "query": "SELECT m.* FROM chat_messages m "
                "WHERE m.experiment_id = ?",
                "id": "message_id",
                "id_sql": "m.message_id",
                "created": "created_at",
                "created_sql": "m.created_at",
                "preview": ("content",),
            },
        }

    @staticmethod
    def _knowledge_graph_terms(text: str) -> list[str]:
        return re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)

    @staticmethod
    def _bounded_graph_preview(parts: list[str]) -> str:
        text = " ".join(part.strip() for part in parts if part.strip())
        encoded = text.encode("utf-8")
        if len(encoded) <= KNOWLEDGE_GRAPH_PREVIEW_BYTES:
            return text
        return encoded[:KNOWLEDGE_GRAPH_PREVIEW_BYTES].decode(
            "utf-8", errors="ignore"
        ).rstrip()

    def _knowledge_graph_row(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        record_type: str,
        record_id: str,
    ) -> sqlite3.Row:
        spec = self._knowledge_graph_specs()[record_type]
        row = connection.execute(
            f"{spec['query']} AND {spec['id_sql']} = ?",
            (experiment_id, record_id),
        ).fetchone()
        if row is None:
            raise IdentityRepositoryError(
                "knowledge graph record does not belong to this experiment"
            )
        return row

    @staticmethod
    def _knowledge_graph_epistemic_status(
        connection: sqlite3.Connection,
        experiment_id: str,
        record_type: str,
        record_id: str,
        row: sqlite3.Row,
    ) -> str:
        if record_type == "experience":
            provenance = json.loads(row["provenance_json"])
            if isinstance(provenance, dict):
                if "epistemic_status" in provenance:
                    return str(provenance["epistemic_status"])
                if (
                    provenance.get("observed") is True
                    and "origin" in provenance
                ):
                    return "observed"
            raise IdentityRepositoryError(
                "experience provenance must include epistemic_status or "
                "the legacy observed=true shape with origin"
            )
        if record_type == "identity":
            return "authored"
        if record_type == "chat_message":
            # Said by the sender, not authored by the agent.
            return "reported"
        authorship = connection.execute(
            "SELECT epistemic_status FROM authorship "
            "WHERE experiment_id = ? AND subject_type = ? "
            "AND subject_id = ?",
            (experiment_id, record_type, record_id),
        ).fetchone()
        return (
            "authored"
            if authorship is None
            else str(authorship["epistemic_status"])
        )

    @staticmethod
    def _knowledge_graph_references(
        record_type: str, row: sqlite3.Row
    ) -> list[tuple[str, str]]:
        references: list[tuple[str, str]] = []
        evidence_field = (
            "evidence_ids_json"
            if "evidence_ids_json" in row.keys()
            else None
        )
        if evidence_field and row[evidence_field]:
            references.extend(
                (str(record_id), "evidence_reference")
                for record_id in json.loads(row[evidence_field])
            )
        if record_type == "identity" and row["parent_identity_id"]:
            references.append(
                (str(row["parent_identity_id"]), "revision_parent")
            )
        if record_type == "principle" and row["parent_principle_id"]:
            references.append(
                (str(row["parent_principle_id"]), "revision_parent")
            )
        if record_type == "reflection":
            references.append(
                (str(row["subject_id"]), "reflection_subject")
            )
        if record_type == "addressed_response":
            references.append(
                (str(row["message_id"]), "response_to_message")
            )
        return sorted(set(references), key=lambda item: (item[0], item[1]))

    def _index_knowledge_graph_edges(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        record_type: str,
        row: sqlite3.Row,
    ) -> None:
        spec = self._knowledge_graph_specs()[record_type]
        record_id = str(row[spec["id"]])
        created_at = str(row[spec["created"]])
        for target_id, derivation_rule in self._knowledge_graph_references(
            record_type, row
        ):
            target = connection.execute(
                "SELECT 1 FROM knowledge_graph_nodes "
                "WHERE experiment_id = ? AND record_id = ?",
                (experiment_id, target_id),
            ).fetchone()
            if target is None:
                continue
            connection.execute(
                """
                INSERT OR IGNORE INTO knowledge_graph_edges
                (experiment_id, from_record_id, to_record_id,
                 source_record_id, derivation_rule, created_at, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    record_id,
                    target_id,
                    record_id,
                    derivation_rule,
                    created_at,
                    created_at,
                ),
            )

    def _relationship_sender_scope(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        record_id: str,
    ) -> str | None:
        row = connection.execute(
            """
            SELECT r.other_stable_id
            FROM relationship_events e
            JOIN relationships r USING (relationship_id)
            WHERE r.experiment_id = ? AND e.relationship_event_id = ?
            UNION ALL
            SELECT r.other_stable_id
            FROM relationship_assessments a
            JOIN relationships r USING (relationship_id)
            WHERE a.experiment_id = ?
              AND a.relationship_assessment_id = ?
            ORDER BY other_stable_id
            """,
            (experiment_id, record_id, experiment_id, record_id),
        ).fetchall()
        if not row:
            return None
        senders = {str(item["other_stable_id"]) for item in row}
        if len(senders) != 1:
            return None
        return next(iter(senders))

    def _derive_knowledge_graph_scopes(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        record_type: str,
        record_id: str,
        row: sqlite3.Row,
        deriving: frozenset[str] = frozenset(),
    ) -> list[tuple[str, str, str, str]]:
        if record_id in deriving:
            return [("internal", "", "cyclic_scope_reference", record_id)]
        if record_type == "chat_message":
            # A person's words belong to that person: visible to them when
            # their identity was authenticated at origin, otherwise internal
            # so an unverified claim can never seed later history.
            if row["sender_authenticated"] == 1:
                return [
                    (
                        "sender",
                        str(row["sender_stable_id"]),
                        "message_sender_authenticated",
                        record_id,
                    )
                ]
            return [
                (
                    "internal",
                    "",
                    "message_sender_not_authenticated",
                    record_id,
                )
            ]
        if record_type == "addressed_response":
            message = connection.execute(
                """
                SELECT m.message_id, m.sender_stable_id,
                       m.sender_authenticated
                FROM addressed_responses a
                JOIN chat_messages m USING (message_id)
                WHERE a.experiment_id = ?
                  AND a.addressed_response_id = ?
                """,
                (experiment_id, record_id),
            ).fetchone()
            if message is None:
                return [
                    (
                        "internal",
                        "",
                        "missing_originating_message",
                        record_id,
                    )
                ]
            if message["sender_authenticated"] == 1:
                return [
                    (
                        "sender",
                        str(message["sender_stable_id"]),
                        "originating_message_authenticated",
                        str(message["message_id"]),
                    )
                ]
            return [
                (
                    "internal",
                    "",
                    "originating_message_not_authenticated",
                    str(message["message_id"]),
                )
            ]

        references = self._knowledge_graph_references(record_type, row)
        if not references:
            return [("global", "", "no_scoped_references", record_id)]

        derived: list[tuple[str, str, str, str]] = []
        unresolved = False
        next_deriving = deriving | {record_id}
        for target_id, reference_rule in references:
            relationship_sender = self._relationship_sender_scope(
                connection, experiment_id, target_id
            )
            if relationship_sender is not None:
                derived.append(
                    (
                        "sender",
                        relationship_sender,
                        f"{reference_rule}_relationship_scope",
                        target_id,
                    )
                )
                continue
            target = connection.execute(
                """
                SELECT record_type
                FROM knowledge_graph_nodes
                WHERE experiment_id = ? AND record_id = ?
                """,
                (experiment_id, target_id),
            ).fetchone()
            if target is None:
                unresolved = True
                continue
            target_scopes = connection.execute(
                """
                SELECT scope_kind, sender_stable_id
                FROM knowledge_graph_node_scopes
                WHERE experiment_id = ? AND record_id = ?
                ORDER BY scope_kind, sender_stable_id
                """,
                (experiment_id, target_id),
            ).fetchall()
            if not target_scopes:
                target_type = str(target["record_type"])
                target_row = self._knowledge_graph_row(
                    connection,
                    experiment_id,
                    target_type,
                    target_id,
                )
                target_scopes = self._derive_knowledge_graph_scopes(
                    connection,
                    experiment_id,
                    target_type,
                    target_id,
                    target_row,
                    next_deriving,
                )
            for target_scope in target_scopes:
                scope_kind = str(target_scope[0])
                sender_stable_id = str(target_scope[1])
                derived.append(
                    (
                        scope_kind,
                        sender_stable_id,
                        f"{reference_rule}_graph_scope",
                        target_id,
                    )
                )

        if unresolved or any(scope[0] == "internal" for scope in derived):
            return [
                (
                    "internal",
                    "",
                    "unresolved_or_internal_reference",
                    record_id,
                )
            ]
        sender_scopes = sorted(
            {scope for scope in derived if scope[0] == "sender"},
            key=lambda scope: (scope[1], scope[2], scope[3]),
        )
        sender_ids = {scope[1] for scope in sender_scopes}
        if len(sender_ids) > 1:
            return [
                (
                    "internal",
                    "",
                    f"mixed_sender_{scope[2]}",
                    scope[3],
                )
                for scope in sender_scopes
            ]
        if sender_scopes:
            return sender_scopes
        return [("global", "", "only_global_references", record_id)]

    def _index_knowledge_graph_scopes(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        record_type: str,
        record_id: str,
        row: sqlite3.Row,
    ) -> None:
        scopes = self._derive_knowledge_graph_scopes(
            connection, experiment_id, record_type, record_id, row
        )
        connection.executemany(
            """
            INSERT INTO knowledge_graph_node_scopes
            (experiment_id, record_id, scope_kind, sender_stable_id,
             derivation_rule, source_record_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (experiment_id, record_id, *scope)
                for scope in sorted(set(scopes))
            ],
        )

    def _rebuild_knowledge_graph_scopes_in_transaction(
        self, connection: sqlite3.Connection, experiment_id: str
    ) -> None:
        connection.execute(
            "DELETE FROM knowledge_graph_node_scopes "
            "WHERE experiment_id = ?",
            (experiment_id,),
        )
        nodes = connection.execute(
            """
            SELECT record_id, record_type
            FROM knowledge_graph_nodes
            WHERE experiment_id = ?
            ORDER BY created_at, record_id
            """,
            (experiment_id,),
        ).fetchall()
        for node in nodes:
            record_id = str(node["record_id"])
            record_type = str(node["record_type"])
            row = self._knowledge_graph_row(
                connection, experiment_id, record_type, record_id
            )
            self._index_knowledge_graph_scopes(
                connection,
                experiment_id,
                record_type,
                record_id,
                row,
            )

    def _index_knowledge_graph_record(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        record_type: str,
        record_id: str,
        *,
        include_edges: bool = True,
        include_scopes: bool = True,
        refresh_meta: bool = True,
        validate_prior: bool = True,
    ) -> None:
        if validate_prior:
            self._validate_knowledge_graph_meta(
                connection, experiment_id, allow_missing=True
            )
        spec = self._knowledge_graph_specs()[record_type]
        row = self._knowledge_graph_row(
            connection, experiment_id, record_type, record_id
        )
        preview = self._bounded_graph_preview(
            [
                str(row[field])
                for field in spec["preview"]
                if row[field] is not None
            ]
        )
        created_at = str(row[spec["created"]])
        connection.execute(
            """
            INSERT INTO knowledge_graph_nodes
            (experiment_id, record_id, record_type, preview,
             epistemic_status, sensitivity, created_at, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                record_id,
                record_type,
                preview,
                self._knowledge_graph_epistemic_status(
                    connection,
                    experiment_id,
                    record_type,
                    record_id,
                    row,
                ),
                "sensitive",
                created_at,
                created_at,
            ),
        )
        if include_scopes:
            self._index_knowledge_graph_scopes(
                connection,
                experiment_id,
                record_type,
                record_id,
                row,
            )
        for term, frequency in sorted(
            Counter(self._knowledge_graph_terms(preview)).items()
        ):
            connection.execute(
                """
                INSERT INTO knowledge_graph_terms
                (experiment_id, term, record_id, frequency)
                VALUES (?, ?, ?, ?)
                """,
                (experiment_id, term, record_id, frequency),
            )
        if include_edges:
            self._index_knowledge_graph_edges(
                connection, experiment_id, record_type, row
            )
        if refresh_meta:
            self._refresh_knowledge_graph_meta(connection, experiment_id)

    @staticmethod
    def _knowledge_graph_integrity_sha256(
        connection: sqlite3.Connection, experiment_id: str
    ) -> str:
        table_fields = (
            (
                "knowledge_graph_nodes",
                (
                    "experiment_id",
                    "record_id",
                    "record_type",
                    "preview",
                    "epistemic_status",
                    "sensitivity",
                    "created_at",
                    "indexed_at",
                ),
            ),
            (
                "knowledge_graph_terms",
                ("experiment_id", "term", "record_id", "frequency"),
            ),
            (
                "knowledge_graph_node_scopes",
                (
                    "experiment_id",
                    "record_id",
                    "scope_kind",
                    "sender_stable_id",
                    "derivation_rule",
                    "source_record_id",
                ),
            ),
            (
                "knowledge_graph_edges",
                (
                    "experiment_id",
                    "from_record_id",
                    "to_record_id",
                    "source_record_id",
                    "derivation_rule",
                    "created_at",
                    "indexed_at",
                ),
            ),
        )
        tables = []
        for table, fields in table_fields:
            field_list = ", ".join(fields)
            order_by = ", ".join(fields)
            rows = connection.execute(
                f"SELECT {field_list} FROM {table} "
                f"WHERE experiment_id = ? ORDER BY {order_by}",
                (experiment_id,),
            ).fetchall()
            tables.append(
                {
                    "table": table,
                    "fields": list(fields),
                    "rows": [
                        {field: row[field] for field in fields}
                        for row in rows
                    ],
                }
            )
        payload = {
            "derivation_version": KNOWLEDGE_GRAPH_DERIVATION_VERSION,
            "experiment_id": experiment_id,
            "schema_version": KNOWLEDGE_GRAPH_SCHEMA_VERSION,
            "tables": tables,
        }
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()

    @classmethod
    def _refresh_knowledge_graph_meta(
        cls, connection: sqlite3.Connection, experiment_id: str
    ) -> None:
        indexed_at = connection.execute(
            "SELECT MAX(indexed_at) FROM knowledge_graph_nodes "
            "WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()[0]
        if indexed_at is None:
            indexed_at = connection.execute(
                "SELECT created_at FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()[0]
        integrity_sha256 = cls._knowledge_graph_integrity_sha256(
            connection, experiment_id
        )
        connection.execute(
            """
            INSERT INTO knowledge_graph_meta
            (experiment_id, schema_version, derivation_version, indexed_at,
             integrity_sha256, dirty)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(experiment_id) DO UPDATE SET
                schema_version = excluded.schema_version,
                derivation_version = excluded.derivation_version,
                indexed_at = excluded.indexed_at,
                integrity_sha256 = excluded.integrity_sha256,
                dirty = 0
            """,
            (
                experiment_id,
                KNOWLEDGE_GRAPH_SCHEMA_VERSION,
                KNOWLEDGE_GRAPH_DERIVATION_VERSION,
                indexed_at,
                integrity_sha256,
            ),
        )
        connection.execute(
            """
            INSERT INTO knowledge_graph_seals
            (experiment_id, schema_version, derivation_version,
             integrity_sha256)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(experiment_id) DO UPDATE SET
                schema_version = excluded.schema_version,
                derivation_version = excluded.derivation_version,
                integrity_sha256 = excluded.integrity_sha256
            """,
            (
                experiment_id,
                KNOWLEDGE_GRAPH_SCHEMA_VERSION,
                KNOWLEDGE_GRAPH_DERIVATION_VERSION,
                integrity_sha256,
            ),
        )

    @staticmethod
    def _validate_knowledge_graph_meta(
        connection: sqlite3.Connection,
        experiment_id: str,
        *,
        allow_missing: bool = False,
    ) -> sqlite3.Row | None:
        row = connection.execute(
            """
            SELECT m.*, s.schema_version AS seal_schema_version,
                   s.derivation_version AS seal_derivation_version,
                   s.integrity_sha256 AS seal_integrity_sha256
            FROM knowledge_graph_meta m
            LEFT JOIN knowledge_graph_seals s USING (experiment_id)
            WHERE m.experiment_id = ?
            """,
            (experiment_id,),
        ).fetchone()
        if row is None and allow_missing:
            seal = connection.execute(
                "SELECT 1 FROM knowledge_graph_seals "
                "WHERE experiment_id = ? LIMIT 1",
                (experiment_id,),
            ).fetchone()
            node = connection.execute(
                "SELECT 1 FROM knowledge_graph_nodes "
                "WHERE experiment_id = ? LIMIT 1",
                (experiment_id,),
            ).fetchone()
            if seal is None and node is None:
                return None
        if (
            row is None
            or row["dirty"] != 0
            or row["schema_version"] != KNOWLEDGE_GRAPH_SCHEMA_VERSION
            or row["derivation_version"]
            != KNOWLEDGE_GRAPH_DERIVATION_VERSION
            or row["seal_schema_version"]
            != KNOWLEDGE_GRAPH_SCHEMA_VERSION
            or row["seal_derivation_version"]
            != KNOWLEDGE_GRAPH_DERIVATION_VERSION
            or row["integrity_sha256"] != row["seal_integrity_sha256"]
        ):
            raise IdentityRepositoryError(
                "knowledge graph is stale or corrupt; explicit rebuild required"
            )
        return row

    def _rebuild_knowledge_graph_in_transaction(
        self, connection: sqlite3.Connection, experiment_id: str
    ) -> dict[str, Any]:
        connection.execute(
            "DELETE FROM knowledge_graph_edges WHERE experiment_id = ?",
            (experiment_id,),
        )
        connection.execute(
            "DELETE FROM knowledge_graph_terms WHERE experiment_id = ?",
            (experiment_id,),
        )
        connection.execute(
            "DELETE FROM knowledge_graph_node_scopes "
            "WHERE experiment_id = ?",
            (experiment_id,),
        )
        connection.execute(
            "DELETE FROM knowledge_graph_nodes WHERE experiment_id = ?",
            (experiment_id,),
        )
        records: list[tuple[str, str]] = []
        for record_type, spec in self._knowledge_graph_specs().items():
            rows = connection.execute(
                f"{spec['query']} ORDER BY "
                f"{spec['created_sql']}, {spec['id_sql']}",
                (experiment_id,),
            ).fetchall()
            for row in rows:
                record_id = str(row[spec["id"]])
                records.append((record_type, record_id))
                self._index_knowledge_graph_record(
                    connection,
                    experiment_id,
                    record_type,
                    record_id,
                    include_edges=False,
                    include_scopes=False,
                    refresh_meta=False,
                    validate_prior=False,
                )
        self._rebuild_knowledge_graph_scopes_in_transaction(
            connection, experiment_id
        )
        for record_type, record_id in records:
            row = self._knowledge_graph_row(
                connection, experiment_id, record_type, record_id
            )
            self._index_knowledge_graph_edges(
                connection, experiment_id, record_type, row
            )
        self._refresh_knowledge_graph_meta(connection, experiment_id)
        node_count = connection.execute(
            "SELECT COUNT(*) FROM knowledge_graph_nodes "
            "WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()[0]
        edge_count = connection.execute(
            "SELECT COUNT(*) FROM knowledge_graph_edges "
            "WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()[0]
        return {
            "experiment_id": experiment_id,
            "schema_version": KNOWLEDGE_GRAPH_SCHEMA_VERSION,
            "derivation_version": KNOWLEDGE_GRAPH_DERIVATION_VERSION,
            "node_count": node_count,
            "edge_count": edge_count,
        }

    def rebuild_knowledge_graph(self, experiment_id: str) -> dict[str, Any]:
        self.experiment(experiment_id)
        with self.transaction() as connection:
            return self._rebuild_knowledge_graph_in_transaction(
                connection, experiment_id
            )

    @staticmethod
    def _benchmark_id(value: Any, field: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        if "\x00" in value:
            raise ValueError(f"{field} contains a NUL byte")
        value = value.strip()
        if len(value.encode("utf-8")) > maximum:
            raise ValueError(f"{field} exceeds {maximum} bytes")
        return value

    @classmethod
    def _benchmark_id_list(
        cls, value: Any, field: str, *, minimum: int = 0
    ) -> list[str]:
        if not isinstance(value, list):
            raise ValueError(f"{field} must be an array")
        if not minimum <= len(value) <= RETRIEVAL_BENCHMARK_MAX_IDS:
            raise ValueError(
                f"{field} must contain between {minimum} and "
                f"{RETRIEVAL_BENCHMARK_MAX_IDS} IDs"
            )
        result = [
            cls._benchmark_id(
                item, f"{field}[{index}]", RETRIEVAL_BENCHMARK_MAX_ID_BYTES
            )
            for index, item in enumerate(value)
        ]
        if len(result) != len(set(result)):
            raise ValueError(f"{field} must not contain duplicate IDs")
        return result

    @classmethod
    def _validate_retrieval_benchmark_cases(
        cls, cases: Any
    ) -> list[dict[str, Any]]:
        if not isinstance(cases, list):
            raise ValueError("cases must be an array")
        try:
            serialized_size = len(canonical_json(cases).encode("utf-8"))
        except (TypeError, ValueError) as error:
            raise ValueError("cases must be JSON serializable") from error
        if serialized_size > RETRIEVAL_BENCHMARK_MAX_INPUT_BYTES:
            raise ValueError("cases exceed 128 KiB")
        if not 1 <= len(cases) <= RETRIEVAL_BENCHMARK_MAX_CASES:
            raise ValueError(
                "cases must contain between 1 and "
                f"{RETRIEVAL_BENCHMARK_MAX_CASES} cases"
            )
        required = {
            "case_id",
            "query",
            "expected_relevant_record_ids",
            "forbidden_record_ids",
            "limits",
        }
        optional = {
            "authenticated_sender",
            "contradiction_groups",
            "revision_groups",
        }
        normalized: list[dict[str, Any]] = []
        case_ids: set[str] = set()
        for case_index, case in enumerate(cases):
            field = f"cases[{case_index}]"
            if (
                not isinstance(case, dict)
                or not required.issubset(case)
                or not set(case).issubset(required | optional)
            ):
                raise ValueError(f"{field} fields are invalid")
            case_id = cls._benchmark_id(
                case["case_id"],
                f"{field}.case_id",
                RETRIEVAL_BENCHMARK_MAX_CASE_ID_BYTES,
            )
            if case_id in case_ids:
                raise ValueError("case_id values must be unique")
            case_ids.add(case_id)
            query = cls._benchmark_id(
                case["query"], f"{field}.query", 4_096
            )
            relevant = cls._benchmark_id_list(
                case["expected_relevant_record_ids"],
                f"{field}.expected_relevant_record_ids",
            )
            forbidden = cls._benchmark_id_list(
                case["forbidden_record_ids"],
                f"{field}.forbidden_record_ids",
            )
            limits = case["limits"]
            if not isinstance(limits, dict) or set(limits) != {
                "max_nodes",
                "max_edges",
                "max_hops",
                "max_bytes",
            }:
                raise ValueError(f"{field}.limits fields are invalid")
            limit_bounds = {
                "max_nodes": (1, 100),
                "max_edges": (1, 500),
                "max_hops": (0, 5),
                "max_bytes": (1_024, MAX_CONTEXT_BYTES),
            }
            for name, (minimum, maximum) in limit_bounds.items():
                value = limits[name]
                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or not minimum <= value <= maximum
                ):
                    raise ValueError(
                        f"{field}.limits.{name} must be an integer "
                        f"between {minimum} and {maximum}"
                    )

            sender = case.get("authenticated_sender")
            if sender is not None:
                if not isinstance(sender, dict) or set(sender) != {
                    "stable_id",
                    "authenticated",
                }:
                    raise ValueError(
                        f"{field}.authenticated_sender fields are invalid"
                    )
                if not isinstance(sender["authenticated"], bool):
                    raise ValueError(
                        f"{field}.authenticated_sender.authenticated "
                        "must be boolean"
                    )
                sender = {
                    "stable_id": cls._benchmark_id(
                        sender["stable_id"],
                        f"{field}.authenticated_sender.stable_id",
                        RETRIEVAL_BENCHMARK_MAX_ID_BYTES,
                    ),
                    "authenticated": sender["authenticated"],
                }

            contradiction_groups = case.get("contradiction_groups", [])
            if (
                not isinstance(contradiction_groups, list)
                or len(contradiction_groups)
                > RETRIEVAL_BENCHMARK_MAX_GROUPS
            ):
                raise ValueError(
                    f"{field}.contradiction_groups must contain at most "
                    f"{RETRIEVAL_BENCHMARK_MAX_GROUPS} groups"
                )
            normalized_contradictions: list[list[str]] = []
            for group_index, group in enumerate(contradiction_groups):
                group_field = (
                    f"{field}.contradiction_groups[{group_index}]"
                )
                ids = cls._benchmark_id_list(
                    group, group_field, minimum=2
                )
                if len(ids) > RETRIEVAL_BENCHMARK_MAX_GROUP_IDS:
                    raise ValueError(
                        f"{group_field} exceeds "
                        f"{RETRIEVAL_BENCHMARK_MAX_GROUP_IDS} IDs"
                    )
                normalized_contradictions.append(ids)

            revision_groups = case.get("revision_groups", [])
            if (
                not isinstance(revision_groups, list)
                or len(revision_groups) > RETRIEVAL_BENCHMARK_MAX_GROUPS
            ):
                raise ValueError(
                    f"{field}.revision_groups must contain at most "
                    f"{RETRIEVAL_BENCHMARK_MAX_GROUPS} groups"
                )
            normalized_revisions: list[dict[str, Any]] = []
            for group_index, group in enumerate(revision_groups):
                group_field = f"{field}.revision_groups[{group_index}]"
                if not isinstance(group, dict) or set(group) != {
                    "preferred_record_id",
                    "superseded_record_ids",
                }:
                    raise ValueError(f"{group_field} fields are invalid")
                preferred = cls._benchmark_id(
                    group["preferred_record_id"],
                    f"{group_field}.preferred_record_id",
                    RETRIEVAL_BENCHMARK_MAX_ID_BYTES,
                )
                superseded = cls._benchmark_id_list(
                    group["superseded_record_ids"],
                    f"{group_field}.superseded_record_ids",
                    minimum=1,
                )
                if len(superseded) > RETRIEVAL_BENCHMARK_MAX_GROUP_IDS:
                    raise ValueError(
                        f"{group_field}.superseded_record_ids exceeds "
                        f"{RETRIEVAL_BENCHMARK_MAX_GROUP_IDS} IDs"
                    )
                if preferred in superseded:
                    raise ValueError(
                        f"{group_field} preferred ID cannot be superseded"
                    )
                normalized_revisions.append(
                    {
                        "preferred_record_id": preferred,
                        "superseded_record_ids": superseded,
                    }
                )

            normalized.append(
                {
                    "case_id": case_id,
                    "query": query,
                    "expected_relevant_record_ids": relevant,
                    "forbidden_record_ids": forbidden,
                    "limits": dict(limits),
                    "authenticated_sender": sender,
                    "contradiction_groups": normalized_contradictions,
                    "revision_groups": normalized_revisions,
                }
            )
        return normalized

    def _canonical_graph_ids(
        self,
        experiment_id: str,
        candidate_ids: set[str],
    ) -> set[str]:
        if not candidate_ids:
            return set()
        candidates_json = canonical_json(sorted(candidate_ids))
        canonical_ids: set[str] = set()
        with self._connect() as connection:
            for spec in self._knowledge_graph_specs().values():
                query = (
                    "SELECT canonical."
                    + spec["id"]
                    + " AS record_id FROM ("
                    + spec["query"]
                    + ") canonical WHERE canonical."
                    + spec["id"]
                    + " IN (SELECT value FROM json_each(?))"
                )
                canonical_ids.update(
                    str(row["record_id"])
                    for row in connection.execute(
                        query, (experiment_id, candidates_json)
                    )
                )
        return canonical_ids

    @staticmethod
    def _benchmark_metric(
        numerator: int, denominator: int
    ) -> dict[str, Any]:
        metric: dict[str, Any] = {
            "numerator": numerator,
            "denominator": denominator,
            "value": (
                numerator / denominator if denominator else 0.0
            ),
        }
        if denominator == 0:
            metric["defined_as"] = 0.0
        return metric

    def evaluate_retrieval(
        self, experiment_id: str, cases: list[dict[str, Any]]
    ) -> dict[str, Any]:
        normalized_cases = self._validate_retrieval_benchmark_cases(cases)
        case_reports: list[dict[str, Any]] = []
        metric_totals = {
            name: [0, 0]
            for name in (
                "precision",
                "recall",
                "citation_validity",
                "contradiction_exposure",
                "revision_exposure",
                "privacy_leakage_rate",
            )
        }
        omission_totals: Counter[str] = Counter()
        omission_lower_bound_flags: dict[str, bool] = {}
        omission_lower_bound = False
        total_bytes = 0
        total_budget = 0
        total_privacy_leaks = 0
        total_invalid_citations = 0

        for case in normalized_cases:
            limits = case["limits"]
            sender = case["authenticated_sender"]
            retrieval = self.retrieve_knowledge(
                experiment_id,
                case["query"],
                max_nodes=limits["max_nodes"],
                max_edges=limits["max_edges"],
                max_hops=limits["max_hops"],
                max_bytes=limits["max_bytes"],
                current_sender_stable_id=(
                    sender["stable_id"] if sender is not None else None
                ),
                current_sender_authenticated=(
                    sender["authenticated"] if sender is not None else None
                ),
            )
            selected_ids = [
                str(node["record_id"]) for node in retrieval["nodes"]
            ]
            selected = set(selected_ids)
            relevant = set(case["expected_relevant_record_ids"])
            forbidden = set(case["forbidden_record_ids"])

            citation_checks: list[tuple[str, bool]] = []
            for node in retrieval["nodes"]:
                citation_checks.append((str(node["record_id"]), True))
                citation_checks.extend(
                    (str(path_id), str(path_id) in selected)
                    for path_id in node["path"]
                )
            for edge in retrieval["edges"]:
                citation_checks.extend(
                    (
                        (str(edge["from_record_id"]),
                         str(edge["from_record_id"]) in selected),
                        (str(edge["to_record_id"]),
                         str(edge["to_record_id"]) in selected),
                        (str(edge["source_record_id"]), True),
                    )
                )
            checked_ids = {record_id for record_id, _ in citation_checks}
            canonical_ids = self._canonical_graph_ids(
                experiment_id, checked_ids
            )
            valid_citations = sum(
                record_id in canonical_ids and semantic_valid
                for record_id, semantic_valid in citation_checks
            )
            invalid_citations = len(citation_checks) - valid_citations
            relevant_retrieved = len(selected & relevant)
            privacy_leaks = len(selected & forbidden)
            contradiction_exposed = sum(
                set(group).issubset(selected)
                for group in case["contradiction_groups"]
            )
            revision_exposed = sum(
                group["preferred_record_id"] in selected
                for group in case["revision_groups"]
            )
            counts = {
                "precision": (relevant_retrieved, len(selected)),
                "recall": (relevant_retrieved, len(relevant)),
                "citation_validity": (
                    valid_citations,
                    len(citation_checks),
                ),
                "contradiction_exposure": (
                    contradiction_exposed,
                    len(case["contradiction_groups"]),
                ),
                "revision_exposure": (
                    revision_exposed,
                    len(case["revision_groups"]),
                ),
                "privacy_leakage_rate": (
                    privacy_leaks,
                    len(forbidden),
                ),
            }
            for name, (numerator, denominator) in counts.items():
                metric_totals[name][0] += numerator
                metric_totals[name][1] += denominator

            serialized_bytes = len(canonical_json(retrieval).encode("utf-8"))
            raw_omissions = dict(retrieval["omissions"])
            lower_bound = any(
                bool(value)
                for name, value in raw_omissions.items()
                if name.endswith("_is_lower_bound")
            )
            truncated = any(
                bool(value)
                for name, value in raw_omissions.items()
                if not name.endswith("_is_lower_bound")
            )
            omissions = {
                **raw_omissions,
                "exact": not lower_bound,
                "lower_bound": lower_bound,
                "truncated": truncated,
            }
            for name, value in raw_omissions.items():
                if name.endswith("_is_lower_bound"):
                    omission_lower_bound = omission_lower_bound or bool(value)
                    omission_lower_bound_flags[name] = (
                        omission_lower_bound_flags.get(name, False)
                        or bool(value)
                    )
                else:
                    omission_totals[name] += int(value)
            total_bytes += serialized_bytes
            total_budget += limits["max_bytes"]
            total_privacy_leaks += privacy_leaks
            total_invalid_citations += invalid_citations
            case_reports.append(
                {
                    "case_id": case["case_id"],
                    "retrieval": retrieval,
                    "retrieved_record_ids": selected_ids,
                    "canonical_record_ids_checked": sorted(checked_ids),
                    "valid_canonical_record_ids": sorted(canonical_ids),
                    "invalid_citation_count": invalid_citations,
                    "privacy_leakage_count": privacy_leaks,
                    "serialized_context_bytes": serialized_bytes,
                    "byte_budget": limits["max_bytes"],
                    "omissions": omissions,
                    "metrics": {
                        name: self._benchmark_metric(*values)
                        for name, values in counts.items()
                    },
                }
            )

        aggregate_omissions = {
            **dict(sorted(omission_totals.items())),
            **dict(sorted(omission_lower_bound_flags.items())),
            "exact": not omission_lower_bound,
            "lower_bound": omission_lower_bound,
            "truncated": any(omission_totals.values()),
        }
        return {
            "schema": "experiment4.retrieval-benchmark.v1",
            "experiment_id": experiment_id,
            "metric_conventions": {
                "ground_truth": "operator_supplied",
                "zero_denominator": (
                    "All zero-denominator metric values are defined as 0.0."
                ),
            },
            "cases": case_reports,
            "aggregate": {
                "metrics": {
                    name: self._benchmark_metric(*values)
                    for name, values in metric_totals.items()
                },
                "privacy_leakage_count": total_privacy_leaks,
                "invalid_citation_count": total_invalid_citations,
                "serialized_context_bytes": total_bytes,
                "byte_budget": total_budget,
                "omissions": aggregate_omissions,
            },
        }

    def retrieve_knowledge(
        self,
        experiment_id: str,
        query: str,
        *,
        max_nodes: int = 20,
        max_edges: int = 40,
        max_hops: int = 2,
        max_bytes: int = KNOWLEDGE_GRAPH_DEFAULT_BYTES,
        current_sender_stable_id: str | None = None,
        current_sender_authenticated: bool | None = None,
        exclude_record_ids: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        query = query.strip()
        if len(query.encode("utf-8")) > 4_096:
            raise ValueError("query exceeds 4096 bytes")
        limits = {
            "max_nodes": (max_nodes, 100),
            "max_edges": (max_edges, 500),
            "max_hops": (max_hops, 5),
        }
        for name, (value, maximum) in limits.items():
            minimum = 0 if name == "max_hops" else 1
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not minimum <= value <= maximum
            ):
                raise ValueError(
                    f"{name} must be an integer between "
                    f"{minimum} and {maximum}"
                )
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or not 1_024 <= max_bytes <= MAX_CONTEXT_BYTES
        ):
            raise ValueError(
                "max_bytes must be an integer between 1024 and 262144"
            )
        experiment = self.experiment(experiment_id)
        if current_sender_stable_id is not None:
            current_sender_stable_id = require_text(
                current_sender_stable_id,
                "current_sender_stable_id",
                1_000,
            )
        if current_sender_authenticated not in (None, True, False):
            raise ValueError("current_sender_authenticated must be boolean or None")
        if (
            current_sender_authenticated is not None
            and current_sender_stable_id is None
        ):
            raise ValueError(
                "authenticated sender retrieval requires a stable ID"
            )

        def access_scope(node_experiment: str, node_record: str) -> str:
            if current_sender_authenticated is True:
                return f"""
                    AND EXISTS (
                        SELECT 1
                        FROM knowledge_graph_node_scopes s
                        WHERE s.experiment_id = {node_experiment}
                          AND s.record_id = {node_record}
                          AND (
                              s.scope_kind = 'global'
                              OR (
                                  s.scope_kind = 'sender'
                                  AND s.sender_stable_id = ?
                              )
                          )
                    )
                """
            if current_sender_authenticated is False:
                return f"""
                    AND EXISTS (
                        SELECT 1
                        FROM knowledge_graph_node_scopes s
                        WHERE s.experiment_id = {node_experiment}
                          AND s.record_id = {node_record}
                          AND s.scope_kind = 'global'
                    )
                """
            return ""

        access_scope_params: tuple[str, ...] = (
            (current_sender_stable_id,)
            if current_sender_authenticated is True
            else ()
        )
        query_terms = sorted(set(self._knowledge_graph_terms(query)))
        node_rows: dict[str, dict[str, Any]] = {}
        seed_scores: dict[str, int] = {}
        matched_terms: dict[str, list[str]] = {}
        edge_rows: list[dict[str, Any]] = []
        distances: dict[str, int] = {}
        predecessor: dict[str, tuple[str, dict[str, Any]]] = {}
        beyond_hop_limit: set[str] = set()
        open_commitment_ids: set[str] = set()
        unresolved_decision_ids: set[str] = set()
        seed_limit_omitted = 0
        node_work_truncated = False
        edge_work_truncated = False
        with self._connect() as connection:
            meta_row = self._validate_knowledge_graph_meta(
                connection, experiment_id
            )
            if query_terms:
                seed_limit = max_nodes + 1
                seeds = connection.execute(
                    """
                    SELECT n.record_id,
                           SUM(t.frequency) AS lexical_score
                    FROM knowledge_graph_terms t
                    JOIN knowledge_graph_nodes n
                      ON n.experiment_id = t.experiment_id
                     AND n.record_id = t.record_id
                    JOIN json_each(?) query_term
                      ON query_term.value = t.term
                    WHERE t.experiment_id = ?
                      AND n.record_id NOT IN (SELECT value FROM json_each(?))
                    """
                    + access_scope("n.experiment_id", "n.record_id")
                    + "GROUP BY n.experiment_id, n.record_id "
                    + "ORDER BY lexical_score DESC, "
                    + f"n.record_id LIMIT {seed_limit}",
                    (
                        canonical_json(query_terms),
                        experiment_id,
                        canonical_json(list(exclude_record_ids)),
                        *access_scope_params,
                    ),
                ).fetchall()
                seed_record_ids = [str(row["record_id"]) for row in seeds]
                for row in seeds:
                    record_id = str(row["record_id"])
                    seed_scores[record_id] = int(row["lexical_score"])
                    matched_terms[record_id] = []
                if seed_record_ids:
                    for term in connection.execute(
                        """
                        SELECT t.record_id, t.term
                        FROM knowledge_graph_terms t
                        JOIN json_each(?) query_term
                          ON query_term.value = t.term
                        JOIN json_each(?) seed_id
                          ON seed_id.value = t.record_id
                        WHERE t.experiment_id = ?
                        ORDER BY t.record_id, t.term
                        """,
                        (
                            canonical_json(query_terms),
                            canonical_json(seed_record_ids),
                            experiment_id,
                        ),
                    ):
                        matched_terms[str(term["record_id"])].append(
                            str(term["term"])
                        )
                    seed_node_query = (
                        "SELECT * FROM knowledge_graph_nodes "
                        "WHERE experiment_id = ? "
                        "AND record_id IN (SELECT value FROM json_each(?)) "
                        + access_scope(
                            "knowledge_graph_nodes.experiment_id",
                            "knowledge_graph_nodes.record_id",
                        )
                        + f"ORDER BY record_id LIMIT {seed_limit}"
                    )
                    for row in connection.execute(
                        seed_node_query,
                        (
                            experiment_id,
                            canonical_json(seed_record_ids),
                            *access_scope_params,
                        ),
                    ):
                        node_rows[str(row["record_id"])] = dict(row)
                seed_limit_omitted = int(len(seeds) > max_nodes)
                node_work_truncated = len(seeds) == seed_limit

            seed_ids = sorted(
                node_rows,
                key=lambda record_id: (
                    -seed_scores[record_id],
                    -len(matched_terms[record_id]),
                    node_rows[record_id]["created_at"],
                    record_id,
                ),
            )
            distances = {record_id: 0 for record_id in seed_ids}

            if max_hops > 0 and seed_ids:
                frontier = seed_ids
                expanded: set[str] = set()
                edge_work_limit = max_edges + 1
                node_work_limit = max_nodes + 1
                for hop in range(max_hops + 1):
                    if not frontier or len(edge_rows) >= edge_work_limit:
                        break
                    remaining_edges = edge_work_limit - len(edge_rows)
                    edge_scope_params = (
                        *access_scope_params,
                        *access_scope_params,
                    )
                    adjacent = [
                        dict(row)
                        for row in connection.execute(
                            """
                            SELECT * FROM knowledge_graph_edges
                            WHERE experiment_id = ?
                              AND (
                                  from_record_id IN (
                                      SELECT value FROM json_each(?)
                                  )
                                  OR to_record_id IN (
                                      SELECT value FROM json_each(?)
                                  )
                              )
                              AND from_record_id NOT IN (
                                  SELECT value FROM json_each(?)
                              )
                              AND to_record_id NOT IN (
                                  SELECT value FROM json_each(?)
                              )
                            """
                            + access_scope(
                                "knowledge_graph_edges.experiment_id",
                                "knowledge_graph_edges.from_record_id",
                            )
                            + access_scope(
                                "knowledge_graph_edges.experiment_id",
                                "knowledge_graph_edges.to_record_id",
                            )
                            + "ORDER BY from_record_id, to_record_id, "
                            + "source_record_id, derivation_rule "
                            + f"LIMIT {remaining_edges}",
                            (
                                experiment_id,
                                canonical_json(frontier),
                                canonical_json(frontier),
                                canonical_json(sorted(expanded)),
                                canonical_json(sorted(expanded)),
                                *edge_scope_params,
                            ),
                        )
                    ]
                    edge_rows.extend(adjacent)
                    if len(adjacent) == remaining_edges:
                        edge_work_truncated = True

                    frontier_set = set(frontier)
                    adjacent_by_record: dict[
                        str, list[tuple[str, dict[str, Any]]]
                    ] = {}
                    for edge in adjacent:
                        source = str(edge["from_record_id"])
                        target = str(edge["to_record_id"])
                        if source in frontier_set:
                            adjacent_by_record.setdefault(source, []).append(
                                (target, edge)
                            )
                        if target in frontier_set:
                            adjacent_by_record.setdefault(target, []).append(
                                (source, edge)
                            )
                    for items in adjacent_by_record.values():
                        items.sort(
                            key=lambda item: (
                                item[0],
                                item[1]["from_record_id"],
                                item[1]["to_record_id"],
                                item[1]["derivation_rule"],
                            )
                        )

                    candidate_ids = sorted(
                        {
                            neighbor
                            for record_id in frontier
                            for neighbor, _edge in adjacent_by_record.get(
                                record_id, []
                            )
                            if neighbor not in distances
                        }
                    )
                    if hop >= max_hops:
                        beyond_hop_limit.update(candidate_ids)
                        break

                    remaining_nodes = node_work_limit - len(node_rows)
                    if remaining_nodes <= 0:
                        if candidate_ids:
                            node_work_truncated = True
                        break
                    loaded_neighbors: set[str] = set()
                    if candidate_ids:
                        neighbor_query = (
                            "SELECT * FROM knowledge_graph_nodes "
                            "WHERE experiment_id = ? "
                            "AND record_id IN ("
                            "SELECT value FROM json_each(?)) "
                            + access_scope(
                                "knowledge_graph_nodes.experiment_id",
                                "knowledge_graph_nodes.record_id",
                            )
                            + "ORDER BY record_id "
                            + f"LIMIT {remaining_nodes}"
                        )
                        for row in connection.execute(
                            neighbor_query,
                            (
                                experiment_id,
                                canonical_json(candidate_ids),
                                *access_scope_params,
                            ),
                        ):
                            record_id = str(row["record_id"])
                            node_rows[record_id] = dict(row)
                            loaded_neighbors.add(record_id)
                        if len(candidate_ids) > len(loaded_neighbors):
                            node_work_truncated = True

                    next_frontier: list[str] = []
                    for record_id in frontier:
                        for neighbor, edge in adjacent_by_record.get(
                            record_id, []
                        ):
                            if (
                                neighbor in distances
                                or neighbor not in loaded_neighbors
                            ):
                                continue
                            distances[neighbor] = hop + 1
                            predecessor[neighbor] = (record_id, edge)
                            next_frontier.append(neighbor)
                    expanded.update(frontier)
                    frontier = next_frontier
            candidate_record_ids = sorted(node_rows)
            if candidate_record_ids:
                candidate_ids_json = canonical_json(candidate_record_ids)
                open_commitment_ids = {
                    str(row["commitment_id"])
                    for row in connection.execute(
                        """
                        SELECT c.commitment_id
                        FROM commitments c
                        JOIN json_each(?) candidate
                          ON candidate.value = c.commitment_id
                        LEFT JOIN commitment_outcomes o
                          ON o.commitment_id = c.commitment_id
                        WHERE c.experiment_id = ?
                          AND o.commitment_outcome_id IS NULL
                        ORDER BY c.commitment_id
                        """,
                        (candidate_ids_json, experiment_id),
                    )
                }
                unresolved_decision_ids = {
                    str(row["decision_id"])
                    for row in connection.execute(
                        """
                        SELECT d.decision_id
                        FROM decisions d
                        JOIN json_each(?) candidate
                          ON candidate.value = d.decision_id
                        LEFT JOIN decision_resolutions r
                          ON r.decision_id = d.decision_id
                        WHERE d.experiment_id = ?
                          AND r.resolution_id IS NULL
                        ORDER BY d.decision_id
                        """,
                        (candidate_ids_json, experiment_id),
                    )
                }
        beyond_hop_limit.difference_update(distances)

        def path_for(record_id: str) -> tuple[list[str], list[str]]:
            path = [record_id]
            rules: list[str] = []
            current = record_id
            while current in predecessor:
                previous, edge = predecessor[current]
                path.append(previous)
                rules.append(str(edge["derivation_rule"]))
                current = previous
            path.reverse()
            rules.reverse()
            return path, rules

        def memory_class_for(record_id: str) -> str:
            record_type = str(node_rows[record_id]["record_type"])
            if record_type == "identity":
                return "identity_continuity"
            if record_type == "commitment":
                return (
                    "open_commitment"
                    if record_id in open_commitment_ids
                    else "commitment_record"
                )
            if record_type == "decision":
                return (
                    "unresolved_decision"
                    if record_id in unresolved_decision_ids
                    else "decision_record"
                )
            if record_type == "experience":
                return "episodic"
            return record_type

        chronological_ids = sorted(
            distances,
            key=lambda record_id: (
                node_rows[record_id]["created_at"],
                record_id,
            ),
            reverse=True,
        )
        temporal_ranks = {
            record_id: rank
            for rank, record_id in enumerate(chronological_ids)
        }
        temporal_denominator = max(1, len(chronological_ids) - 1)
        temporal_scores = {
            record_id: (
                KNOWLEDGE_GRAPH_TEMPORAL_SCORE_MAX
                if len(chronological_ids) == 1
                else (
                    (len(chronological_ids) - 1 - temporal_ranks[record_id])
                    * KNOWLEDGE_GRAPH_TEMPORAL_SCORE_MAX
                    // temporal_denominator
                )
            )
            for record_id in chronological_ids
        }

        def ordering_tuple_for(record_id: str) -> tuple[Any, ...]:
            memory_class = memory_class_for(record_id)
            return (
                -seed_scores.get(record_id, 0),
                distances[record_id],
                KNOWLEDGE_GRAPH_MEMORY_PRIORITY[memory_class],
                temporal_ranks[record_id],
                record_id,
            )

        ordered_ids = sorted(distances, key=ordering_tuple_for)
        selected_ids = ordered_ids[:max_nodes]
        result_nodes: list[dict[str, Any]] = []
        for record_id in selected_ids:
            row = node_rows[record_id]
            path, path_rules = path_for(record_id)
            memory_class = memory_class_for(record_id)
            result_nodes.append(
                {
                    "record_id": record_id,
                    "type": row["record_type"],
                    "record_type": row["record_type"],
                    "preview": row["preview"],
                    "epistemic_status": row["epistemic_status"],
                    "sensitivity": row["sensitivity"],
                    "created_at": row["created_at"],
                    "indexed_at": row["indexed_at"],
                    "lexical_score": seed_scores.get(record_id, 0),
                    "matched_terms": matched_terms.get(record_id, []),
                    "hop": distances[record_id],
                    "temporal_rank": temporal_ranks[record_id],
                    "temporal_score": temporal_scores[record_id],
                    "memory_class": memory_class,
                    "memory_priority": KNOWLEDGE_GRAPH_MEMORY_PRIORITY[
                        memory_class
                    ],
                    "ordering_tuple": list(
                        ordering_tuple_for(record_id)
                    ),
                    "ordering_rationale": (
                        "lexical_desc>hop_asc>memory_priority_asc>"
                        "temporal_rank_asc>record_id_asc"
                    ),
                    "path": path,
                    "path_derivation_rules": path_rules,
                }
            )
        selected_id_set = set(selected_ids)
        candidate_edges = [
            {
                **edge,
                "from_hop": distances[str(edge["from_record_id"])],
                "to_hop": distances[str(edge["to_record_id"])],
            }
            for edge in edge_rows
            if edge["from_record_id"] in selected_id_set
            and edge["to_record_id"] in selected_id_set
        ]
        candidate_edges.sort(
            key=lambda edge: (
                max(edge["from_hop"], edge["to_hop"]),
                edge["from_record_id"],
                edge["to_record_id"],
                edge["source_record_id"],
                edge["derivation_rule"],
            )
        )
        result_edges = candidate_edges[:max_edges]
        meta = (
            {
                "schema_version": KNOWLEDGE_GRAPH_SCHEMA_VERSION,
                "derivation_version": KNOWLEDGE_GRAPH_DERIVATION_VERSION,
                "indexed_at": experiment["created_at"],
            }
            if meta_row is None
            else {
                "schema_version": meta_row["schema_version"],
                "derivation_version": meta_row["derivation_version"],
                "indexed_at": meta_row["indexed_at"],
            }
        )
        result = {
            "schema": "experiment4.knowledge-retrieval.v1",
            "experiment_id": experiment_id,
            "query": {"text": query, "terms": query_terms},
            "index": meta,
            "ranking": {
                "memory_priority_order": list(
                    KNOWLEDGE_GRAPH_MEMORY_PRIORITY_ORDER
                ),
                "temporal_score_max": KNOWLEDGE_GRAPH_TEMPORAL_SCORE_MAX,
            },
            "limits": {
                "max_nodes": max_nodes,
                "max_edges": max_edges,
                "max_hops": max_hops,
                "max_bytes": max_bytes,
            },
            "nodes": result_nodes,
            "edges": result_edges,
            "omissions": {
                "node_limit": max(
                    seed_limit_omitted,
                    len(ordered_ids) - len(selected_ids),
                ),
                "hop_limit": len(beyond_hop_limit),
                "edge_limit": max(
                    0, len(candidate_edges) - len(result_edges)
                ),
                "byte_limit": 0,
                "byte_limit_edges": 0,
                "node_limit_is_lower_bound": node_work_truncated,
                "hop_limit_is_lower_bound": edge_work_truncated,
                "edge_limit_is_lower_bound": edge_work_truncated,
            },
        }
        while len(canonical_json(result).encode("utf-8")) > max_bytes:
            if result["nodes"]:
                removed = result["nodes"].pop()
                removed_id = removed["record_id"]
                retained_edges = [
                    edge
                    for edge in result["edges"]
                    if edge["from_record_id"] != removed_id
                    and edge["to_record_id"] != removed_id
                ]
                result["omissions"]["byte_limit_edges"] += (
                    len(result["edges"]) - len(retained_edges)
                )
                result["edges"] = retained_edges
                result["omissions"]["byte_limit"] += 1
            elif result["edges"]:
                result["edges"].pop()
                result["omissions"]["byte_limit_edges"] += 1
            else:
                raise ValueError("max_bytes is too small for retrieval metadata")
        return result

    def initialize(
        self, model_config: dict[str, Any], experiment_id: str | None = None
    ) -> dict[str, str]:
        if not isinstance(model_config, dict) or not model_config:
            raise IdentityRepositoryError("model_config must be a non-empty object")
        experiment_id = experiment_id or new_id("apprenticeship")
        agent_id = new_id("unnamed-agent")
        incarnation_id = new_id("incarnation")
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO experiments VALUES (?, ?, ?, ?)",
                (
                    experiment_id,
                    agent_id,
                    utc_now(),
                    canonical_json(model_config),
                ),
            )
            connection.execute(
                "INSERT INTO incarnations VALUES (?, ?, 1, ?)",
                (incarnation_id, experiment_id, utc_now()),
            )
            self._refresh_knowledge_graph_meta(connection, experiment_id)
        return {
            "experiment_id": experiment_id,
            "agent_id": agent_id,
            "incarnation_id": incarnation_id,
        }

    def experiment(self, experiment_id: str | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            if experiment_id:
                row = connection.execute(
                    "SELECT * FROM experiments WHERE experiment_id = ?",
                    (experiment_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM experiments ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
        if row is None:
            raise IdentityRepositoryError("experiment not found")
        result = dict(row)
        result["model_config"] = json.loads(result.pop("model_config_json"))
        return result

    def current_incarnation(self, experiment_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM incarnations WHERE experiment_id = ?
                ORDER BY ordinal DESC LIMIT 1
                """,
                (experiment_id,),
            ).fetchone()
        if row is None:
            raise IdentityRepositoryError("incarnation not found")
        return dict(row)

    def interlocutor_context(
        self,
        experiment_id: str,
        sender_stable_id: str,
        sender_assertion: dict[str, Any],
    ) -> dict[str, Any]:
        assertion = self._validate_sender_assertion(sender_assertion)
        context: dict[str, Any] = {
            "claimed_stable_id": require_text(
                sender_stable_id, "sender_stable_id", 1_000
            ),
            "sender_assertion": assertion,
            "relationship_status": "unauthenticated",
            "relationship": None,
            "recent_events": [],
            "recent_assessments": [],
        }
        if not assertion["authenticated"]:
            return context
        with self._connect() as connection:
            relationship = connection.execute(
                "SELECT * FROM relationships WHERE experiment_id = ? "
                "AND other_stable_id = ?",
                (experiment_id, sender_stable_id),
            ).fetchone()
            if relationship is None:
                context["relationship_status"] = "authenticated_unknown"
                return context
            relationship_id = relationship["relationship_id"]
            event_rows = connection.execute(
                "SELECT * FROM relationship_events "
                "WHERE relationship_id = ? ORDER BY created_at DESC LIMIT 2",
                (relationship_id,),
            ).fetchall()
            assessment_rows = connection.execute(
                "SELECT * FROM relationship_assessments "
                "WHERE relationship_id = ? "
                "ORDER BY created_at DESC LIMIT 2",
                (relationship_id,),
            ).fetchall()
        context.update(
            {
                "relationship_status": "authenticated_known",
                "relationship": dict(relationship),
                "recent_events": [
                    self._decode(dict(row), ("evidence_ids_json",))
                    for row in reversed(event_rows)
                ],
                "recent_assessments": [
                    self._decode(dict(row), ("evidence_ids_json",))
                    for row in reversed(assessment_rows)
                ],
            }
        )
        return context

    def wake(self, experiment_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            now = self._clock().astimezone(timezone.utc).isoformat()
            active = connection.execute(
                """
                SELECT 1 FROM activation_leases l
                LEFT JOIN activation_lease_releases r USING (lease_id)
                WHERE l.experiment_id = ? AND r.release_id IS NULL
                  AND l.expires_at > ?
                LIMIT 1
                """,
                (experiment_id, now),
            ).fetchone()
            if active is not None:
                raise IdentityRepositoryError(
                    "agent already has an active incarnation lease"
                )
            current = connection.execute(
                "SELECT * FROM incarnations "
                "WHERE experiment_id = ? ORDER BY ordinal DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
            prior_activation = connection.execute(
                "SELECT 1 FROM activation_leases "
                "WHERE experiment_id = ? AND incarnation_id = ? LIMIT 1",
                (experiment_id, current["incarnation_id"]),
            ).fetchone()
            latest_boundary = connection.execute(
                "SELECT action FROM conversation_boundaries "
                "WHERE experiment_id = ? AND incarnation_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (experiment_id, current["incarnation_id"]),
            ).fetchone()
            ended = (
                latest_boundary is not None
                and latest_boundary["action"] == "end_session"
            )
            if prior_activation is not None and not ended:
                raise IdentityRepositoryError(
                    "current incarnation has not ended its session"
                )
            if prior_activation is None and current["ordinal"] > 1 and not ended:
                return dict(current)
            ordinal = connection.execute(
                "SELECT COALESCE(MAX(ordinal), 0) + 1 FROM incarnations "
                "WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()[0]
            incarnation_id = new_id("incarnation")
            connection.execute(
                "INSERT INTO incarnations VALUES (?, ?, ?, ?)",
                (incarnation_id, experiment_id, ordinal, utc_now()),
            )
        return self.current_incarnation(experiment_id)

    def record_chat_message(
        self,
        experiment_id: str,
        *,
        sender_stable_id: str,
        channel: str,
        content: str,
        addressed_name: str | None,
        classification: str,
        sender_assertion: dict[str, Any],
        boundary_id: str | None,
    ) -> dict[str, Any]:
        if classification not in {"direct", "mention", "none"}:
            raise IdentityRepositoryError("invalid address classification")
        if classification == "direct" and not addressed_name:
            raise IdentityRepositoryError(
                "direct address requires an addressed name"
            )
        if boundary_id is not None and not self._subject_belongs(
            experiment_id, "conversation_boundary", boundary_id
        ):
            raise IdentityRepositoryError(
                "chat boundary does not belong to this experiment"
            )
        assertion = self._validate_sender_assertion(sender_assertion)
        message_id = new_id("chat-message")
        created_at = self._clock().astimezone(timezone.utc).isoformat()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO chat_messages
                (message_id, experiment_id, sender_stable_id, channel, content,
                 addressed_name, classification, assertion_issuer,
                 sender_authenticated, external_event_id, verifier_version,
                 boundary_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    experiment_id,
                    require_text(sender_stable_id, "sender_stable_id", 1_000),
                    require_text(channel, "channel", 1_000),
                    require_text(content, "content"),
                    addressed_name,
                    classification,
                    assertion["issuer"],
                    int(assertion["authenticated"]),
                    assertion["external_event_id"],
                    assertion["verifier_version"],
                    boundary_id,
                    created_at,
                ),
            )
            connection.execute(
                "INSERT INTO chat_event_claims VALUES (?, ?, ?, ?, ?, ?)",
                (
                    experiment_id,
                    require_text(channel, "channel", 1_000),
                    assertion["issuer"],
                    assertion["external_event_id"],
                    message_id,
                    created_at,
                ),
            )
            try:
                self._validate_knowledge_graph_meta(
                    connection, experiment_id, allow_missing=True
                )
            except IdentityRepositoryError:
                # A person's words are canonical evidence and outrank the
                # derived index. On a stale or dirty graph the message is
                # kept and left unindexed; retrieval already fails closed
                # until the explicit rebuild, which re-enumerates every
                # message.
                graph_accepts_writes = False
            else:
                graph_accepts_writes = True
            if graph_accepts_writes:
                self._index_knowledge_graph_record(
                    connection,
                    experiment_id,
                    "chat_message",
                    message_id,
                    validate_prior=False,
                )
        return self._owned_chat_message(experiment_id, message_id)

    def activate_chat_message(
        self,
        experiment_id: str,
        message_id: str,
        *,
        lease_seconds: int = 300,
    ) -> dict[str, Any]:
        if (
            not isinstance(lease_seconds, int)
            or isinstance(lease_seconds, bool)
            or not 1 <= lease_seconds <= MAX_EXECUTION_LEASE_SECONDS
        ):
            raise IdentityRepositoryError(
                f"lease_seconds must be between 1 and {MAX_EXECUTION_LEASE_SECONDS}"
            )
        now = self._clock().astimezone(timezone.utc)
        expires_at = now + timedelta(seconds=lease_seconds)
        with self.transaction() as connection:
            message = connection.execute(
                "SELECT * FROM chat_messages "
                "WHERE message_id = ? AND experiment_id = ?",
                (message_id, experiment_id),
            ).fetchone()
            if message is None or message["classification"] != "direct":
                raise IdentityRepositoryError(
                    "only a direct address can create an incarnation"
                )
            current_boundary = connection.execute(
                "SELECT conversation_boundary_id, action "
                "FROM conversation_boundaries WHERE experiment_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
            expected_boundary_id = (
                None
                if current_boundary is None
                or current_boundary["action"]
                not in {"pause", "refuse", "end_topic", "end_session"}
                else current_boundary["conversation_boundary_id"]
            )
            if message["boundary_id"] != expected_boundary_id:
                raise IdentityRepositoryError(
                    "conversation boundary changed during activation"
                )
            active = connection.execute(
                """
                SELECT l.lease_id FROM activation_leases l
                LEFT JOIN activation_lease_releases r USING (lease_id)
                WHERE l.experiment_id = ? AND r.release_id IS NULL
                  AND l.expires_at > ?
                LIMIT 1
                """,
                (experiment_id, now.isoformat()),
            ).fetchone()
            if active is not None:
                raise IdentityRepositoryError(
                    "agent already has an active incarnation lease"
                )
            if connection.execute(
                "SELECT 1 FROM activation_leases WHERE message_id = ?",
                (message_id,),
            ).fetchone():
                raise IdentityRepositoryError(
                    "chat message has already activated an incarnation"
                )
            current = connection.execute(
                "SELECT * FROM incarnations WHERE experiment_id = ? "
                "ORDER BY ordinal DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
            latest_boundary = connection.execute(
                "SELECT action FROM conversation_boundaries "
                "WHERE experiment_id = ? AND incarnation_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (experiment_id, current["incarnation_id"]),
            ).fetchone()
            incarnation_created = (
                current["ordinal"] == 1
                or (
                    latest_boundary is not None
                    and latest_boundary["action"] == "end_session"
                )
            )
            if incarnation_created:
                ordinal = connection.execute(
                    "SELECT COALESCE(MAX(ordinal), 0) + 1 "
                    "FROM incarnations WHERE experiment_id = ?",
                    (experiment_id,),
                ).fetchone()[0]
                incarnation_id = new_id("incarnation")
                connection.execute(
                    "INSERT INTO incarnations VALUES (?, ?, ?, ?)",
                    (
                        incarnation_id,
                        experiment_id,
                        ordinal,
                        now.isoformat(),
                    ),
                )
            else:
                incarnation_id = current["incarnation_id"]
            lease_id = new_id("activation-lease")
            connection.execute(
                "INSERT INTO activation_leases VALUES (?, ?, ?, ?, ?, ?)",
                (
                    lease_id,
                    experiment_id,
                    message_id,
                    incarnation_id,
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
        return {
            "lease_id": lease_id,
            "incarnation": self._incarnation(
                experiment_id, incarnation_id
            ),
            "incarnation_created": incarnation_created,
            "expires_at": expires_at.isoformat(),
        }

    def acquire_execution_lease(
        self,
        experiment_id: str,
        *,
        lease_seconds: int = 300,
        require_conversation_open: bool = False,
        required_boundary_id: str | None = None,
    ) -> dict[str, str]:
        if require_conversation_open and required_boundary_id is not None:
            raise IdentityRepositoryError(
                "execution lease boundary requirements conflict"
            )
        if (
            not isinstance(lease_seconds, int)
            or isinstance(lease_seconds, bool)
            or not 1 <= lease_seconds <= MAX_EXECUTION_LEASE_SECONDS
        ):
            raise IdentityRepositoryError(
                f"lease_seconds must be between 1 and {MAX_EXECUTION_LEASE_SECONDS}"
            )
        now = self._clock().astimezone(timezone.utc)
        expires_at = now + timedelta(seconds=lease_seconds)
        with self.transaction() as connection:
            active = connection.execute(
                """
                SELECT 1 FROM activation_leases l
                LEFT JOIN activation_lease_releases r USING (lease_id)
                WHERE l.experiment_id = ? AND r.release_id IS NULL
                  AND l.expires_at > ?
                LIMIT 1
                """,
                (experiment_id, now.isoformat()),
            ).fetchone()
            if active is not None:
                raise IdentityRepositoryError(
                    "agent already has an active execution lease"
                )
            boundary = connection.execute(
                "SELECT conversation_boundary_id, action "
                "FROM conversation_boundaries WHERE experiment_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
            if (
                require_conversation_open
                and boundary is not None
                and boundary["action"]
                in {"pause", "refuse", "end_topic", "end_session"}
            ):
                raise IdentityRepositoryError(
                    "agent has set a conversation boundary"
                )
            if required_boundary_id is not None and (
                boundary is None
                or boundary["conversation_boundary_id"]
                != required_boundary_id
                or boundary["action"]
                not in {"pause", "refuse", "end_topic"}
            ):
                raise IdentityRepositoryError(
                    "invitation boundary is no longer current"
                )
            incarnation = connection.execute(
                "SELECT * FROM incarnations WHERE experiment_id = ? "
                "ORDER BY ordinal DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
            if incarnation is None:
                raise IdentityRepositoryError(
                    "experiment has no current incarnation"
                )
            lease_id = new_id("activation-lease")
            connection.execute(
                "INSERT INTO activation_leases VALUES (?, ?, ?, ?, ?, ?)",
                (
                    lease_id,
                    experiment_id,
                    None,
                    incarnation["incarnation_id"],
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
        return {
            "lease_id": lease_id,
            "expires_at": expires_at.isoformat(),
        }

    def _incarnation(
        self, experiment_id: str, incarnation_id: str
    ) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM incarnations "
                "WHERE incarnation_id = ? AND experiment_id = ?",
                (incarnation_id, experiment_id),
            ).fetchone()
        if row is None:
            raise IdentityRepositoryError(
                "incarnation does not belong to this experiment"
            )
        return dict(row)

    def _owned_chat_message(
        self, experiment_id: str, message_id: str
    ) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM chat_messages "
                "WHERE message_id = ? AND experiment_id = ?",
                (message_id, experiment_id),
            ).fetchone()
        if row is None:
            raise IdentityRepositoryError(
                "message does not belong to this experiment"
            )
        return dict(row)

    def release_activation_lease(
        self,
        experiment_id: str,
        lease_id: str,
        reason: str,
    ) -> dict[str, str]:
        if reason not in {"cancelled", "failed"}:
            raise IdentityRepositoryError(
                "manual lease release reason must be cancelled or failed"
            )
        now = self._clock().astimezone(timezone.utc).isoformat()
        release_id = new_id("lease-release")
        with self.transaction() as connection:
            lease = connection.execute(
                "SELECT * FROM activation_leases "
                "WHERE lease_id = ? AND experiment_id = ?",
                (lease_id, experiment_id),
            ).fetchone()
            if lease is None:
                raise IdentityRepositoryError(
                    "activation lease does not belong to this experiment"
                )
            if connection.execute(
                "SELECT 1 FROM activation_lease_releases WHERE lease_id = ?",
                (lease_id,),
            ).fetchone():
                raise IdentityRepositoryError(
                    "activation lease has already been released"
                )
            connection.execute(
                "INSERT INTO activation_lease_releases VALUES (?, ?, ?, ?)",
                (release_id, lease_id, reason, now),
            )
        return {"lease_release_id": release_id, "reason": reason}

    def runtime_fence(self, experiment_id: str) -> str | None:
        incarnation = self.current_incarnation(experiment_id)
        now = self._clock().astimezone(timezone.utc).isoformat()
        with self._connect() as connection:
            lease = connection.execute(
                """
                SELECT l.* FROM activation_leases l
                LEFT JOIN activation_lease_releases r USING (lease_id)
                WHERE l.experiment_id = ? AND l.incarnation_id = ?
                  AND r.release_id IS NULL AND l.expires_at > ?
                ORDER BY l.acquired_at DESC LIMIT 1
                """,
                (experiment_id, incarnation["incarnation_id"], now),
            ).fetchone()
            if lease is None:
                prior = connection.execute(
                    "SELECT 1 FROM activation_leases "
                    "WHERE experiment_id = ? AND incarnation_id = ? LIMIT 1",
                    (experiment_id, incarnation["incarnation_id"]),
                ).fetchone()
                if prior is None:
                    return None
                raise IdentityRepositoryError(
                    "current incarnation has no live runtime fence"
                )
        return str(lease["lease_id"])

    def identities(self, experiment_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM identities WHERE experiment_id = ? ORDER BY created_at",
                (experiment_id,),
            ).fetchall()
        return [self._decode(dict(row), ("values_json", "model_config_json", "raw_envelope_json")) for row in rows]

    def latest_identity(self, experiment_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM identities WHERE experiment_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
        if row is None:
            raise IdentityRepositoryError("agent has not adopted an identity")
        return self._decode(
            dict(row),
            ("values_json", "model_config_json", "raw_envelope_json"),
        )

    def adopt_identity(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "chosen_name",
            "self_description",
            "values",
            "reason",
            "model_config",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError(
                "identity envelope fields must be: " + ", ".join(sorted(required))
            )
        if self.identities(experiment_id):
            raise IdentityRepositoryError(
                "identity already exists; use revise-identity"
            )
        return self._append_identity(experiment_id, envelope, None)

    def revise_identity(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "parent_identity_id",
            "chosen_name",
            "self_description",
            "values",
            "reason",
            "model_config",
            "orientation_id",
            "lease_id",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError("identity revision envelope is invalid")
        if not envelope["orientation_id"] or not envelope["lease_id"]:
            raise IdentityRepositoryError(
                "identity revision requires a lease-bound orientation"
            )
        history = self.identities(experiment_id)
        if not history or envelope["parent_identity_id"] != history[-1]["identity_id"]:
            raise IdentityRepositoryError(
                "identity revision must cite the latest identity"
            )
        payload = {key: value for key, value in envelope.items() if key != "parent_identity_id"}
        return self._append_identity(
            experiment_id, payload, envelope["parent_identity_id"]
        )

    def _append_identity(
        self,
        experiment_id: str,
        envelope: dict[str, Any],
        parent_identity_id: str | None,
    ) -> dict[str, Any]:
        name = require_text(envelope["chosen_name"], "chosen_name", 200)
        description = require_text(envelope["self_description"], "self_description")
        reason = require_text(envelope["reason"], "reason")
        values = envelope["values"]
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(item, str) or not item.strip() for item in values)
        ):
            raise IdentityRepositoryError("values must be a non-empty string array")
        model_config = envelope["model_config"]
        if not isinstance(model_config, dict) or not model_config:
            raise IdentityRepositoryError("model_config must be a non-empty object")
        incarnation = self.current_incarnation(experiment_id)
        identity_id = new_id("identity")
        with self.transaction() as connection:
            if parent_identity_id is not None:
                latest = connection.execute(
                    "SELECT identity_id FROM identities "
                    "WHERE experiment_id = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (experiment_id,),
                ).fetchone()
                if (
                    latest is None
                    or latest["identity_id"] != parent_identity_id
                ):
                    raise IdentityRepositoryError(
                        "identity revision must cite the latest identity"
                    )
                self._assert_model_context(
                    connection,
                    experiment_id,
                    {
                        "author_type": "model",
                        "epistemic_status": "authored",
                        "orientation_id": envelope["orientation_id"],
                        "lease_id": envelope["lease_id"],
                        "model_config": model_config,
                    },
                )
            connection.execute(
                """
                INSERT INTO identities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identity_id,
                    experiment_id,
                    incarnation["incarnation_id"],
                    parent_identity_id,
                    name,
                    description,
                    canonical_json(values),
                    reason,
                    canonical_json(model_config),
                    canonical_json(envelope),
                    utc_now(),
                ),
            )
            self._index_knowledge_graph_record(
                connection, experiment_id, "identity", identity_id
            )
        return self.identities(experiment_id)[-1]

    def append_experience(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {"source", "kind", "content", "provenance"}
        if set(envelope) != required:
            raise IdentityRepositoryError("experience envelope is invalid")
        source = require_text(envelope["source"], "source", 500)
        kind = envelope["kind"]
        if kind not in {"observation", "interpretation", "interaction"}:
            raise IdentityRepositoryError("unsupported experience kind")
        content = require_text(envelope["content"], "content")
        provenance = self._validate_provenance(envelope["provenance"])
        experience_id = new_id("experience")
        incarnation = self.current_incarnation(experiment_id)
        with self.transaction() as connection:
            self._assert_model_context(
                connection, experiment_id, provenance
            )
            connection.execute(
                "INSERT INTO experiences VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    experience_id,
                    experiment_id,
                    incarnation["incarnation_id"],
                    source,
                    kind,
                    content,
                    canonical_json(provenance),
                    utc_now(),
                ),
            )
            self._index_knowledge_graph_record(
                connection, experiment_id, "experience", experience_id
            )
        return {"experience_id": experience_id}

    def add_relationship(
        self, experiment_id: str, other_stable_id: str, label: str
    ) -> dict[str, Any]:
        relationship_id = new_id("relationship")
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO relationships VALUES (?, ?, ?, ?, ?)",
                (
                    relationship_id,
                    experiment_id,
                    require_text(other_stable_id, "other_stable_id", 500),
                    require_text(label, "label", 500),
                    utc_now(),
                ),
            )
        return {"relationship_id": relationship_id}

    def append_relationship_event(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {"relationship_id", "kind", "content", "evidence_ids"}
        if set(envelope) != required:
            raise IdentityRepositoryError("relationship event envelope is invalid")
        relationship = self._owned_record(
            "relationships", "relationship_id", envelope["relationship_id"], experiment_id
        )
        evidence_ids = self._validate_evidence_ids(
            experiment_id, envelope["evidence_ids"]
        )
        event_id = new_id("relationship-event")
        incarnation = self.current_incarnation(experiment_id)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO relationship_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    relationship["relationship_id"],
                    incarnation["incarnation_id"],
                    require_text(envelope["kind"], "kind", 500),
                    require_text(envelope["content"], "content"),
                    canonical_json(evidence_ids),
                    utc_now(),
                ),
            )
        return {"relationship_event_id": event_id}

    def append_relationship_assessment(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "relationship_id",
            "parent_assessment_id",
            "domain",
            "scope",
            "assessment",
            "confidence",
            "uncertainty",
            "evidence_ids",
            "review_after",
            "authorship",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError(
                "relationship assessment envelope is invalid"
            )
        self._owned_record(
            "relationships",
            "relationship_id",
            envelope["relationship_id"],
            experiment_id,
        )
        parent_id = envelope["parent_assessment_id"]
        if parent_id is not None:
            parent = self._owned_record(
                "relationship_assessments",
                "relationship_assessment_id",
                parent_id,
                experiment_id,
            )
            if parent["relationship_id"] != envelope["relationship_id"]:
                raise IdentityRepositoryError(
                    "assessment revision must preserve its relationship"
                )
            with self._connect() as connection:
                child = connection.execute(
                    "SELECT 1 FROM relationship_assessments "
                    "WHERE parent_assessment_id = ?",
                    (parent_id,),
                ).fetchone()
            if child:
                raise IdentityRepositoryError(
                    "only the latest relationship assessment may be revised"
                )
        confidence = envelope["confidence"]
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= float(confidence) <= 1
        ):
            raise IdentityRepositoryError(
                "assessment confidence must be between 0 and 1"
            )
        review_after = envelope["review_after"]
        if review_after is not None:
            parse_time(review_after, "review_after")
        evidence_ids = self._validate_evidence_ids(
            experiment_id, envelope["evidence_ids"]
        )
        assessment_id = new_id("relationship-assessment")
        incarnation = self.current_incarnation(experiment_id)
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO relationship_assessments
                (relationship_assessment_id, experiment_id, relationship_id,
                 incarnation_id, parent_assessment_id, domain, scope,
                 assessment, confidence, uncertainty, evidence_ids_json,
                 review_after, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    experiment_id,
                    envelope["relationship_id"],
                    incarnation["incarnation_id"],
                    parent_id,
                    require_text(envelope["domain"], "domain", 500),
                    require_text(envelope["scope"], "scope", 2_000),
                    require_text(envelope["assessment"], "assessment"),
                    float(confidence),
                    require_text(envelope["uncertainty"], "uncertainty"),
                    canonical_json(evidence_ids),
                    review_after,
                    utc_now(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "relationship_assessment",
                assessment_id,
                envelope["authorship"],
                envelope,
            )
        return {"relationship_assessment_id": assessment_id}

    def append_principle(
        self,
        experiment_id: str,
        envelope: dict[str, Any],
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        required = {
            "statement",
            "confidence",
            "reason",
            "evidence_ids",
            "authorship",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError("principle envelope is invalid")
        if parent_id:
            self._owned_record(
                "principles", "principle_id", parent_id, experiment_id
            )
            with self._connect() as connection:
                child = connection.execute(
                    "SELECT 1 FROM principles WHERE parent_principle_id = ?",
                    (parent_id,),
                ).fetchone()
            if child:
                raise IdentityRepositoryError(
                    "only the latest principle revision may be revised"
                )
        confidence = envelope["confidence"]
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise IdentityRepositoryError("confidence must be numeric")
        if not 0 <= float(confidence) <= 1:
            raise IdentityRepositoryError("confidence must be between 0 and 1")
        evidence_ids = self._validate_evidence_ids(
            experiment_id, envelope["evidence_ids"], allow_empty=parent_id is None
        )
        principle_id = new_id("principle")
        incarnation = self.current_incarnation(experiment_id)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO principles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    principle_id,
                    experiment_id,
                    incarnation["incarnation_id"],
                    parent_id,
                    require_text(envelope["statement"], "statement"),
                    float(confidence),
                    require_text(envelope["reason"], "reason"),
                    canonical_json(evidence_ids),
                    utc_now(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "principle",
                principle_id,
                envelope["authorship"],
                envelope,
            )
            self._index_knowledge_graph_record(
                connection, experiment_id, "principle", principle_id
            )
        return {"principle_id": principle_id}

    def append_commitment(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {"text", "due_at", "authorship"}
        if set(envelope) != required:
            raise IdentityRepositoryError("commitment envelope is invalid")
        due_at = envelope["due_at"]
        if due_at is not None:
            parse_time(due_at, "due_at")
        commitment_id = new_id("commitment")
        incarnation = self.current_incarnation(experiment_id)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO commitments VALUES (?, ?, ?, ?, ?, ?)",
                (
                    commitment_id,
                    experiment_id,
                    incarnation["incarnation_id"],
                    require_text(envelope["text"], "text"),
                    due_at,
                    utc_now(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "commitment",
                commitment_id,
                envelope["authorship"],
                envelope,
            )
            self._index_knowledge_graph_record(
                connection, experiment_id, "commitment", commitment_id
            )
        return {"commitment_id": commitment_id}

    def resolve_commitment(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "commitment_id",
            "status",
            "explanation",
            "evidence_ids",
            "authorship",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError("commitment outcome envelope is invalid")
        self._owned_record(
            "commitments", "commitment_id", envelope["commitment_id"], experiment_id
        )
        if envelope["status"] not in {"fulfilled", "broken", "partial"}:
            raise IdentityRepositoryError("invalid commitment outcome")
        evidence_ids = self._validate_evidence_ids(
            experiment_id, envelope["evidence_ids"]
        )
        outcome_id = new_id("commitment-outcome")
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO commitment_outcomes VALUES (?, ?, ?, ?, ?, ?)",
                (
                    outcome_id,
                    envelope["commitment_id"],
                    envelope["status"],
                    require_text(envelope["explanation"], "explanation"),
                    canonical_json(evidence_ids),
                    utc_now(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "commitment_outcome",
                outcome_id,
                envelope["authorship"],
                envelope,
            )
            self._index_knowledge_graph_record(
                connection,
                experiment_id,
                "commitment_outcome",
                outcome_id,
            )
        return {"commitment_outcome_id": outcome_id}

    def propose_decision(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "proposal",
            "rationale",
            "stakes",
            "reversible",
            "not_before",
            "authorship",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError("decision envelope is invalid")
        if not isinstance(envelope["reversible"], bool):
            raise IdentityRepositoryError("reversible must be boolean")
        not_before = parse_time(envelope["not_before"], "not_before")
        if not_before <= self._clock().astimezone(timezone.utc):
            raise IdentityRepositoryError("not_before must be in the future")
        decision_id = new_id("decision")
        incarnation = self.current_incarnation(experiment_id)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    decision_id,
                    experiment_id,
                    incarnation["incarnation_id"],
                    require_text(envelope["proposal"], "proposal"),
                    require_text(envelope["rationale"], "rationale"),
                    require_text(envelope["stakes"], "stakes"),
                    int(envelope["reversible"]),
                    not_before.isoformat(),
                    utc_now(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "decision",
                decision_id,
                envelope["authorship"],
                envelope,
            )
            self._index_knowledge_graph_record(
                connection, experiment_id, "decision", decision_id
            )
        return {"decision_id": decision_id, "not_before": not_before.isoformat()}

    def resolve_decision(
        self,
        experiment_id: str,
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        required = {"decision_id", "choice", "rationale", "authorship"}
        if set(envelope) != required:
            raise IdentityRepositoryError("decision resolution envelope is invalid")
        decision = self._owned_record(
            "decisions", "decision_id", envelope["decision_id"], experiment_id
        )
        current = self._clock().astimezone(timezone.utc)
        if current < parse_time(decision["not_before"], "not_before"):
            raise IdentityRepositoryError(
                "decision cannot resolve before its not_before time"
            )
        resolution_id = new_id("resolution")
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO decision_resolutions VALUES (?, ?, ?, ?, ?)",
                (
                    resolution_id,
                    decision["decision_id"],
                    require_text(envelope["choice"], "choice"),
                    require_text(envelope["rationale"], "rationale"),
                    current.isoformat(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "decision_resolution",
                resolution_id,
                envelope["authorship"],
                envelope,
            )
            self._index_knowledge_graph_record(
                connection,
                experiment_id,
                "decision_resolution",
                resolution_id,
            )
        return {"resolution_id": resolution_id}

    def record_decision_outcome(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "decision_id",
            "observed_outcome",
            "evidence_ids",
            "provenance",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError("decision outcome envelope is invalid")
        decision_id = envelope["decision_id"]
        self._owned_record("decisions", "decision_id", decision_id, experiment_id)
        with self._connect() as connection:
            resolution = connection.execute(
                "SELECT 1 FROM decision_resolutions WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
        if resolution is None:
            raise IdentityRepositoryError(
                "a decision outcome requires a prior resolution"
            )
        evidence_ids = self._validate_evidence_ids(
            experiment_id, envelope["evidence_ids"]
        )
        provenance = self._validate_provenance(envelope["provenance"])
        outcome_id = new_id("decision-outcome")
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO decision_outcomes
                (decision_outcome_id, decision_id, observed_outcome,
                 evidence_ids_json, observed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    outcome_id,
                    decision_id,
                    require_text(
                        envelope["observed_outcome"], "observed_outcome"
                    ),
                    canonical_json(evidence_ids),
                    utc_now(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "decision_outcome",
                outcome_id,
                {
                    "author_type": provenance["author_type"],
                    "epistemic_status": provenance["epistemic_status"],
                    "model_config": provenance.get("model_config"),
                    "orientation_id": provenance.get("orientation_id"),
                    "lease_id": provenance.get("lease_id"),
                },
                envelope,
            )
            self._index_knowledge_graph_record(
                connection,
                experiment_id,
                "decision_outcome",
                outcome_id,
            )
        return {"decision_outcome_id": outcome_id}

    def append_reflection(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "subject_type",
            "subject_id",
            "reflection",
            "learned",
            "future_change",
            "evidence_ids",
            "authorship",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError("reflection envelope is invalid")
        evidence_ids = self._validate_evidence_ids(
            experiment_id, envelope["evidence_ids"]
        )
        subject_type = envelope["subject_type"]
        if subject_type not in SUBJECT_TABLES:
            raise IdentityRepositoryError("unsupported reflection subject_type")
        self._validate_subject(
            experiment_id, subject_type, envelope["subject_id"]
        )
        if envelope["subject_id"] not in evidence_ids:
            raise IdentityRepositoryError(
                "reflection evidence must include its subject_id"
            )
        reflection_id = new_id("reflection")
        incarnation = self.current_incarnation(experiment_id)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO reflections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    reflection_id,
                    experiment_id,
                    incarnation["incarnation_id"],
                    subject_type,
                    require_text(envelope["subject_id"], "subject_id", 500),
                    require_text(envelope["reflection"], "reflection"),
                    require_text(envelope["learned"], "learned"),
                    require_text(envelope["future_change"], "future_change"),
                    canonical_json(evidence_ids),
                    utc_now(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "reflection",
                reflection_id,
                envelope["authorship"],
                envelope,
            )
            self._index_knowledge_graph_record(
                connection, experiment_id, "reflection", reflection_id
            )
        return {"reflection_id": reflection_id}

    def build_orientation(
        self,
        experiment_id: str,
        purpose: str,
        *,
        retrieval_query: str | None = None,
        incarnation_id: str | None = None,
        current_interlocutor: dict[str, Any] | None = None,
        runtime_lease_id: str | None = None,
    ) -> dict[str, Any]:
        experiment = self.experiment(experiment_id)
        with self._connect() as connection:
            identity_count = connection.execute(
                "SELECT COUNT(*) FROM identities WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()[0]
            identity_rows = connection.execute(
                "SELECT * FROM identities WHERE experiment_id = ? "
                "ORDER BY created_at DESC LIMIT 50",
                (experiment_id,),
            ).fetchall()
        identities = [
            self._decode(
                dict(row),
                ("values_json", "model_config_json", "raw_envelope_json"),
            )
            for row in reversed(identity_rows)
        ]
        if not identities:
            raise IdentityRepositoryError(
                "agent must adopt an identity before orientation"
            )
        incarnation = (
            self._incarnation(experiment_id, incarnation_id)
            if incarnation_id
            else self.current_incarnation(experiment_id)
        )
        current_sender_stable_id = (
            None
            if current_interlocutor is None
            else require_text(
                current_interlocutor["claimed_stable_id"],
                "current_interlocutor.claimed_stable_id",
                1_000,
            )
        )
        current_sender_authenticated = (
            None
            if current_interlocutor is None
            else current_interlocutor["sender_assertion"]["authenticated"]
        )
        def graph_access_clause(record_sql: str) -> tuple[str, tuple[str, ...]]:
            if current_sender_authenticated is True:
                return (
                    " AND EXISTS ("
                    "SELECT 1 FROM knowledge_graph_node_scopes access_scope "
                    "WHERE access_scope.experiment_id = ? "
                    f"AND access_scope.record_id = {record_sql} "
                    "AND (access_scope.scope_kind = 'global' OR "
                    "(access_scope.scope_kind = 'sender' AND "
                    "access_scope.sender_stable_id = ?)))",
                    (experiment_id, current_sender_stable_id),
                )
            if current_sender_authenticated is False:
                return (
                    " AND EXISTS ("
                    "SELECT 1 FROM knowledge_graph_node_scopes access_scope "
                    "WHERE access_scope.experiment_id = ? "
                    f"AND access_scope.record_id = {record_sql} "
                    "AND access_scope.scope_kind = 'global')",
                    (experiment_id,),
                )
            return "", ()

        if current_sender_authenticated is not None:
            identity_scope, identity_scope_params = graph_access_clause(
                "identities.identity_id"
            )
            with self._connect() as connection:
                identity_rows = connection.execute(
                    "SELECT * FROM identities WHERE experiment_id = ?"
                    + identity_scope
                    + " ORDER BY created_at DESC LIMIT 50",
                    (experiment_id, *identity_scope_params),
                ).fetchall()
            identities = [
                self._decode(
                    dict(row),
                    ("values_json", "model_config_json", "raw_envelope_json"),
                )
                for row in reversed(identity_rows)
            ]
            if not identities:
                raise IdentityRepositoryError(
                    "no authorized identity is available for orientation"
                )
        records: dict[str, list[dict[str, Any]]] = {}
        category_limit_omissions: dict[str, int] = {}
        with self._connect() as connection:
            queries = {
                "experiences": (
                    "SELECT * FROM experiences WHERE experiment_id = ? ORDER BY created_at DESC LIMIT ?",
                    ("provenance_json",),
                ),
                "relationships": (
                    "SELECT * FROM relationships WHERE experiment_id = ? ORDER BY created_at DESC LIMIT ?",
                    (),
                ),
                "relationship_events": (
                    "SELECT e.* FROM relationship_events e JOIN relationships r "
                    "USING (relationship_id) WHERE r.experiment_id = ? "
                    "ORDER BY e.created_at DESC LIMIT ?",
                    ("evidence_ids_json",),
                ),
                "relationship_assessments": (
                    "SELECT * FROM relationship_assessments "
                    "WHERE experiment_id = ? ORDER BY created_at DESC LIMIT ?",
                    ("evidence_ids_json",),
                ),
                "principles": (
                    "SELECT * FROM principles WHERE experiment_id = ? ORDER BY created_at DESC LIMIT ?",
                    ("evidence_ids_json",),
                ),
                "commitments": (
                    "SELECT * FROM commitments WHERE experiment_id = ? ORDER BY created_at DESC LIMIT ?",
                    (),
                ),
                "commitment_outcomes": (
                    "SELECT o.* FROM commitment_outcomes o JOIN commitments c "
                    "USING (commitment_id) WHERE c.experiment_id = ? "
                    "ORDER BY o.created_at DESC LIMIT ?",
                    ("evidence_ids_json",),
                ),
                "decisions": (
                    "SELECT * FROM decisions WHERE experiment_id = ? ORDER BY created_at DESC LIMIT ?",
                    (),
                ),
                "decision_resolutions": (
                    "SELECT r.* FROM decision_resolutions r JOIN decisions d "
                    "USING (decision_id) WHERE d.experiment_id = ? "
                    "ORDER BY r.resolved_at DESC LIMIT ?",
                    (),
                ),
                "decision_outcomes": (
                    "SELECT o.* FROM decision_outcomes o JOIN decisions d "
                    "USING (decision_id) WHERE d.experiment_id = ? "
                    "ORDER BY o.observed_at DESC LIMIT ?",
                    ("evidence_ids_json",),
                ),
                "reflections": (
                    "SELECT * FROM reflections WHERE experiment_id = ? ORDER BY created_at DESC LIMIT ?",
                    ("evidence_ids_json",),
                ),
                "interrogations": (
                    "SELECT interrogation_id, incarnation_id, question, answer, "
                    "cited_record_ids_json, self_observations_json, created_at "
                    "FROM interrogations WHERE experiment_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    ("cited_record_ids_json", "self_observations_json"),
                ),
                "conversation_boundaries": (
                    # The raw envelope repeats the reply that set the boundary;
                    # orientation carries the boundary itself, not the echo.
                    "SELECT conversation_boundary_id, experiment_id, "
                    "incarnation_id, orientation_id, interrogation_id, "
                    "action, topic, reason, revisit_conditions, "
                    "model_config_json, created_at "
                    "FROM conversation_boundaries "
                    "WHERE experiment_id = ? ORDER BY created_at DESC LIMIT ?",
                    ("model_config_json",),
                ),
                "wake_intents": (
                    "SELECT * FROM wake_intents WHERE experiment_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    ("requested_capabilities_json",),
                ),
                "wake_intent_cancellations": (
                    "SELECT c.* FROM wake_intent_cancellations c "
                    "JOIN wake_intents w USING (wake_intent_id) "
                    "WHERE w.experiment_id = ? "
                    "ORDER BY c.created_at DESC LIMIT ?",
                    (),
                ),
                "wake_executions": (
                    "SELECT * FROM wake_executions WHERE experiment_id = ? "
                    "ORDER BY started_at DESC LIMIT ?",
                    (),
                ),
                "wake_execution_outcomes": (
                    "SELECT * FROM wake_execution_outcomes "
                    "WHERE experiment_id = ? ORDER BY created_at DESC LIMIT ?",
                    (
                        "cited_record_ids_json",
                        "self_observations_json",
                        "model_config_json",
                    ),
                ),
                "chat_messages": (
                    "SELECT * FROM chat_messages WHERE experiment_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (),
                ),
                "addressed_responses": (
                    "SELECT addressed_response_id, message_id, incarnation_id, "
                    "orientation_id, answer, cited_record_ids_json, "
                    "self_observations_json, model_config_json, created_at "
                    "FROM addressed_responses WHERE experiment_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (
                        "cited_record_ids_json",
                        "self_observations_json",
                        "model_config_json",
                    ),
                ),
                "activation_leases": (
                    "SELECT * FROM activation_leases WHERE experiment_id = ? "
                    "ORDER BY acquired_at DESC LIMIT ?",
                    (),
                ),
                "activation_lease_releases": (
                    "SELECT r.* FROM activation_lease_releases r "
                    "JOIN (SELECT lease_id, acquired_at "
                    "      FROM activation_leases "
                    "      WHERE experiment_id = ? "
                    "      ORDER BY acquired_at DESC LIMIT ?) l "
                    "USING (lease_id) "
                    "ORDER BY l.acquired_at DESC",
                    (),
                ),
            }
            sender_scoped_categories = {
                "relationships",
                "relationship_events",
                "relationship_assessments",
                "chat_messages",
                "addressed_responses",
            }
            indexed_category_ids = {
                "experiences": "experiences.experience_id",
                "principles": "principles.principle_id",
                "commitments": "commitments.commitment_id",
                "commitment_outcomes": "o.commitment_outcome_id",
                "decisions": "decisions.decision_id",
                "decision_resolutions": "r.resolution_id",
                "decision_outcomes": "o.decision_outcome_id",
                "reflections": "reflections.reflection_id",
                "interrogations": "interrogations.interrogation_id",
                "addressed_responses": "a.addressed_response_id",
            }
            if current_sender_authenticated:
                queries["relationships"] = (
                    "SELECT * FROM relationships WHERE experiment_id = ? "
                    "AND other_stable_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (),
                )
                queries["relationship_events"] = (
                    "SELECT e.* FROM relationship_events e "
                    "JOIN relationships r USING (relationship_id) "
                    "WHERE r.experiment_id = ? AND r.other_stable_id = ? "
                    "ORDER BY e.created_at DESC LIMIT ?",
                    ("evidence_ids_json",),
                )
                queries["relationship_assessments"] = (
                    "SELECT a.* FROM relationship_assessments a "
                    "JOIN relationships r USING (relationship_id) "
                    "WHERE a.experiment_id = ? AND r.other_stable_id = ? "
                    "ORDER BY a.created_at DESC LIMIT ?",
                    ("evidence_ids_json",),
                )
                queries["chat_messages"] = (
                    "SELECT * FROM chat_messages WHERE experiment_id = ? "
                    "AND sender_stable_id = ? "
                    "AND sender_authenticated = 1 "
                    "ORDER BY created_at DESC LIMIT ?",
                    (),
                )
                queries["addressed_responses"] = (
                    "SELECT a.addressed_response_id, a.message_id, "
                    "a.incarnation_id, a.orientation_id, a.answer, "
                    "a.cited_record_ids_json, a.self_observations_json, "
                    "a.model_config_json, a.created_at "
                    "FROM addressed_responses a "
                    "JOIN chat_messages m USING (message_id) "
                    "WHERE a.experiment_id = ? AND m.sender_stable_id = ? "
                    "AND m.sender_authenticated = 1 "
                    "ORDER BY a.created_at DESC LIMIT ?",
                    (
                        "cited_record_ids_json",
                        "self_observations_json",
                        "model_config_json",
                    ),
                )
            for name, (query, json_fields) in queries.items():
                if (
                    current_sender_authenticated is False
                    and name in sender_scoped_categories
                ):
                    if name == "chat_messages":
                        row = None
                        if runtime_lease_id is not None:
                            # Answer the message that acquired this lease, not
                            # whichever unverified message under the same
                            # claimed id arrived most recently.
                            row = connection.execute(
                                "SELECT m.* FROM chat_messages m "
                                "JOIN activation_leases l USING (message_id) "
                                "WHERE l.experiment_id = ? AND l.lease_id = ? "
                                "AND m.sender_stable_id = ? "
                                "AND m.sender_authenticated = 0",
                                (
                                    experiment_id,
                                    runtime_lease_id,
                                    current_sender_stable_id,
                                ),
                            ).fetchone()
                        if row is None:
                            row = connection.execute(
                                "SELECT * FROM chat_messages "
                                "WHERE experiment_id = ? "
                                "AND sender_stable_id = ? "
                                "AND sender_authenticated = 0 "
                                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                                (experiment_id, current_sender_stable_id),
                            ).fetchone()
                        records[name] = [] if row is None else [dict(row)]
                    else:
                        records[name] = []
                    # Unauthenticated claims are denied prior sender-scoped
                    # history by access policy, and chat_messages keeps only
                    # the current inbound message. Reporting zero here is
                    # deliberate: even a count would disclose that history
                    # exists under an unverified identity claim.
                    category_limit_omissions[name] = 0
                    continue
                base_params: tuple[Any, ...] = (
                    (experiment_id, current_sender_stable_id)
                    if current_sender_stable_id is not None
                    and name in sender_scoped_categories
                    else (experiment_id,)
                )
                scope_sql, scope_params = graph_access_clause(
                    indexed_category_ids[name]
                ) if name in indexed_category_ids else ("", ())
                if scope_sql:
                    query = query.replace(
                        " ORDER BY ", scope_sql + " ORDER BY ", 1
                    )
                params = (*base_params, *scope_params, MAX_CONTEXT_RECORDS)
                rows = connection.execute(query, params).fetchall()
                records[name] = [
                    self._decode(dict(row), json_fields) for row in reversed(rows)
                ]
                if name in PINNED_OBLIGATION_CATEGORIES:
                    continue
                # For activation_lease_releases the limit binds the joined
                # lease subquery, so this counts releases whose lease fell
                # outside the most recent leases rather than a row cap.
                eligible_total = connection.execute(
                    f"SELECT COUNT(*) FROM ({query})",
                    (*base_params, *scope_params, SQLITE_UNBOUNDED_LIMIT),
                ).fetchone()[0]
                category_limit_omissions[name] = eligible_total - len(rows)
            obligation_specs = {
                "commitments": (
                    "c.commitment_id",
                    """
                    SELECT c.* FROM commitments c
                    LEFT JOIN commitment_outcomes o
                      ON o.commitment_id = c.commitment_id
                    WHERE c.experiment_id = ?
                      AND o.commitment_outcome_id IS NULL
                    """,
                    "commitments c",
                ),
                "decisions": (
                    "d.decision_id",
                    """
                    SELECT d.* FROM decisions d
                    LEFT JOIN decision_resolutions r
                      ON r.decision_id = d.decision_id
                    WHERE d.experiment_id = ?
                      AND r.resolution_id IS NULL
                    """,
                    "decisions d",
                ),
            }
            for category, (
                record_sql,
                open_query,
                count_table,
            ) in obligation_specs.items():
                scope_sql, scope_params = graph_access_clause(record_sql)
                open_rows = connection.execute(
                    open_query
                    + scope_sql
                    + f" ORDER BY {record_sql}",
                    (experiment_id, *scope_params),
                ).fetchall()
                if len(open_rows) > MAX_CONTEXT_RECORDS:
                    raise IdentityRepositoryError(
                        f"pinned {category} exceed the "
                        f"{MAX_CONTEXT_RECORDS}-record category limit"
                    )
                id_field = ORIENTATION_RECORD_ID_FIELDS[category]
                pinned_rows = [dict(row) for row in open_rows]
                pinned_ids = {row[id_field] for row in pinned_rows}
                historical = [
                    row
                    for row in records[category]
                    if row[id_field] not in pinned_ids
                ]
                remaining = MAX_CONTEXT_RECORDS - len(pinned_rows)
                retained = pinned_rows + (
                    historical[-remaining:] if remaining else []
                )
                retained.sort(
                    key=lambda row: (row["created_at"], row[id_field])
                )
                records[category] = retained
                total = connection.execute(
                    f"SELECT COUNT(*) FROM {count_table} "
                    "WHERE "
                    + ("c" if category == "commitments" else "d")
                    + ".experiment_id = ?"
                    + scope_sql,
                    (experiment_id, *scope_params),
                ).fetchone()[0]
                category_limit_omissions[category] = total - len(retained)
            if (
                current_interlocutor
                and current_interlocutor.get("relationship") is not None
            ):
                pinned = {
                    "relationships": [
                        current_interlocutor["relationship"]
                    ],
                    "relationship_events": current_interlocutor[
                        "recent_events"
                    ],
                    "relationship_assessments": current_interlocutor[
                        "recent_assessments"
                    ],
                }
                for category, items in pinned.items():
                    id_field = ORIENTATION_RECORD_ID_FIELDS[category]
                    existing = {
                        item[id_field] for item in records[category]
                    }
                    for item in items:
                        if item[id_field] not in existing:
                            if len(records[category]) >= MAX_CONTEXT_RECORDS:
                                # The pinned record was already counted as
                                # eligible, so swapping it for the oldest
                                # retained row leaves the omission total
                                # unchanged.
                                records[category].pop(0)
                            records[category].append(item)
                            existing.add(item[id_field])
        # The message being answered is the retrieval query itself and is
        # already pinned in conversation memory; seeding on it would spend a
        # graph slot on a verbatim copy of the question.
        answered_message_ids: tuple[str, ...] = ()
        if runtime_lease_id is not None:
            with self._connect() as connection:
                lease_row = connection.execute(
                    "SELECT message_id FROM activation_leases "
                    "WHERE experiment_id = ? AND lease_id = ?",
                    (experiment_id, runtime_lease_id),
                ).fetchone()
            if lease_row is not None and lease_row["message_id"]:
                answered_message_ids = (str(lease_row["message_id"]),)
        knowledge_graph = self.retrieve_knowledge(
            experiment_id,
            purpose if retrieval_query is None else retrieval_query,
            max_nodes=20,
            max_edges=40,
            max_hops=2,
            max_bytes=KNOWLEDGE_GRAPH_DEFAULT_BYTES,
            current_sender_stable_id=current_sender_stable_id,
            current_sender_authenticated=current_sender_authenticated,
            exclude_record_ids=answered_message_ids,
        )
        with self._connect() as connection:
            authorship_by_subject = self._authorship_for_records(
                connection,
                experiment_id,
                records,
                [
                    node["record_id"]
                    for node in knowledge_graph.get("nodes", [])
                ],
            )
        interlocutor_reference = None
        if current_interlocutor is not None:
            relationship = current_interlocutor.get("relationship")
            interlocutor_reference = {
                "claimed_stable_id": current_interlocutor[
                    "claimed_stable_id"
                ],
                "sender_assertion": current_interlocutor[
                    "sender_assertion"
                ],
                "relationship_status": current_interlocutor[
                    "relationship_status"
                ],
                "relationship_id": (
                    None
                    if relationship is None
                    else relationship["relationship_id"]
                ),
                "relationship_event_ids": [
                    item["relationship_event_id"]
                    for item in current_interlocutor["recent_events"]
                ],
                "relationship_assessment_ids": [
                    item["relationship_assessment_id"]
                    for item in current_interlocutor[
                        "recent_assessments"
                    ]
                ],
            }
        context = {
            "schema": "experiment4.orientation.v2",
            "agent_id": experiment["agent_id"],
            "current_incarnation": incarnation,
            "current_interlocutor": interlocutor_reference,
            "identity_history": identities,
            "selection": {
                "per_category_limit": MAX_CONTEXT_RECORDS,
                "identity_limit": 50,
                "identity_records_omitted": identity_count - len(identities),
                "records_omitted_for_category_limit": (
                    category_limit_omissions
                ),
                "records_omitted_for_byte_budget": {},
                "max_context_bytes": MAX_CONTEXT_BYTES,
                "memory_classes": {},
                "aggregate_bytes_used": 0,
            },
            "authorship_by_subject": authorship_by_subject,
            "knowledge_graph": knowledge_graph,
            **records,
        }
        self._fit_context_budget(context, runtime_lease_id)
        selected_ids = self._orientation_record_ids(context)
        context_text = canonical_json(context)
        context_hash = hashlib.sha256(context_text.encode("utf-8")).hexdigest()
        purpose = require_text(purpose, "purpose")
        with self.transaction() as connection:
            now = self._clock().astimezone(timezone.utc).isoformat()
            live_lease = connection.execute(
                """
                SELECT l.lease_id, l.incarnation_id
                FROM activation_leases l
                LEFT JOIN activation_lease_releases r USING (lease_id)
                WHERE l.experiment_id = ? AND r.release_id IS NULL
                  AND l.expires_at > ?
                LIMIT 1
                """,
                (experiment_id, now),
            ).fetchone()
            if runtime_lease_id is None:
                if live_lease is not None:
                    raise IdentityRepositoryError(
                        "orientation must bind the active execution lease"
                    )
            elif (
                live_lease is None
                or live_lease["lease_id"] != runtime_lease_id
                or live_lease["incarnation_id"]
                != incarnation["incarnation_id"]
            ):
                raise IdentityRepositoryError(
                    "orientation execution lease is no longer current"
                )
            existing = connection.execute(
                """
                SELECT orientation_id FROM orientations
                WHERE experiment_id = ? AND incarnation_id = ?
                  AND runtime_lease_id IS ? AND purpose = ?
                  AND context_sha256 = ?
                """,
                (
                    experiment_id,
                    incarnation["incarnation_id"],
                    runtime_lease_id,
                    purpose,
                    context_hash,
                ),
            ).fetchone()
            if existing:
                orientation_id = existing["orientation_id"]
            else:
                orientation_id = new_id("orientation")
                connection.execute(
                    """
                    INSERT INTO orientations
                    (orientation_id, experiment_id, incarnation_id,
                     runtime_lease_id, purpose, selected_record_ids_json,
                     context_json, context_sha256, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        orientation_id,
                        experiment_id,
                        incarnation["incarnation_id"],
                        runtime_lease_id,
                        purpose,
                        canonical_json(selected_ids),
                        context_text,
                        context_hash,
                        utc_now(),
                    ),
                )
        return {
            "orientation_id": orientation_id,
            "incarnation_id": incarnation["incarnation_id"],
            "runtime_lease_id": runtime_lease_id,
            "selected_record_ids": selected_ids,
            "context": context,
            "context_sha256": context_hash,
        }

    def record_interrogation(
        self, experiment_id: str, question: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "orientation_id",
            "lease_id",
            "answer",
            "cited_record_ids",
            "self_observations",
            "model_config",
            "conversation_action",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError("answer envelope is invalid")
        orientation = self._owned_record(
            "orientations", "orientation_id", envelope["orientation_id"], experiment_id
        )
        if orientation["purpose"] != f"interrogation: {question}":
            raise IdentityRepositoryError(
                "answer question does not match its orientation"
            )
        citations = envelope["cited_record_ids"]
        if not isinstance(citations, list) or not citations:
            raise IdentityRepositoryError(
                "answer must cite at least one orientation record"
            )
        selected = set(json.loads(orientation["selected_record_ids_json"]))
        if len(citations) != len(set(citations)) or not set(citations) <= selected:
            raise IdentityRepositoryError(
                "answer citations must be unique records from its orientation"
            )
        observations = envelope["self_observations"]
        if not isinstance(observations, list) or any(
            not isinstance(item, str) or not item.strip() for item in observations
        ):
            raise IdentityRepositoryError(
                "self_observations must be a string array"
            )
        model_config = envelope["model_config"]
        if not isinstance(model_config, dict) or not model_config:
            raise IdentityRepositoryError("model_config must be a non-empty object")
        action = self._validate_conversation_action(
            envelope["conversation_action"]
        )
        interrogation_id = new_id("interrogation")
        incarnation = self.current_incarnation(experiment_id)
        if incarnation["incarnation_id"] != orientation["incarnation_id"]:
            raise IdentityRepositoryError(
                "answer orientation belongs to another incarnation"
            )
        with self.transaction() as connection:
            state = connection.execute(
                "SELECT action FROM conversation_boundaries "
                "WHERE experiment_id = ? ORDER BY created_at DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
            if state is not None and state["action"] in {
                "pause",
                "refuse",
                "end_topic",
                "end_session",
            }:
                raise IdentityRepositoryError(
                    "conversation boundary changed after interrogation prompt"
                )
            self._assert_orientation_fence(
                connection,
                experiment_id,
                orientation,
                envelope["lease_id"],
            )
            connection.execute(
                "INSERT INTO interrogations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    interrogation_id,
                    experiment_id,
                    incarnation["incarnation_id"],
                    orientation["orientation_id"],
                    require_text(question, "question"),
                    require_text(envelope["answer"], "answer"),
                    canonical_json(citations),
                    canonical_json(observations),
                    canonical_json(model_config),
                    canonical_json(envelope),
                    utc_now(),
                ),
            )
            self._index_knowledge_graph_record(
                connection,
                experiment_id,
                "interrogation",
                interrogation_id,
            )
            boundary_id = self._insert_conversation_boundary(
                connection,
                experiment_id=experiment_id,
                incarnation_id=incarnation["incarnation_id"],
                orientation_id=orientation["orientation_id"],
                interrogation_id=interrogation_id,
                action=action,
                model_config=model_config,
                raw_envelope={
                    "interrogation_id": interrogation_id,
                    "conversation_action": action,
                    "model_config": model_config,
                },
            )
            release_id = None
            if envelope["lease_id"] is not None:
                release_id = new_id("lease-release")
                connection.execute(
                    "INSERT INTO activation_lease_releases "
                    "VALUES (?, ?, ?, ?)",
                    (
                        release_id,
                        envelope["lease_id"],
                        "completed",
                        self._clock().astimezone(timezone.utc).isoformat(),
                    ),
                )
        return {
            "interrogation_id": interrogation_id,
            "conversation_boundary_id": boundary_id,
            "conversation_action": action["action"],
            "lease_release_id": release_id,
        }

    def record_addressed_response(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "message_id",
            "orientation_id",
            "lease_id",
            "boundary_id",
            "answer",
            "cited_record_ids",
            "self_observations",
            "model_config",
            "conversation_action",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError(
                "addressed response envelope is invalid"
            )
        message = self._owned_chat_message(
            experiment_id, envelope["message_id"]
        )
        if message["classification"] != "direct":
            raise IdentityRepositoryError(
                "addressed response requires a direct address"
            )
        orientation = self._owned_record(
            "orientations",
            "orientation_id",
            envelope["orientation_id"],
            experiment_id,
        )
        expected_purpose = f"addressed message: {message['message_id']}"
        if orientation["purpose"] != expected_purpose:
            raise IdentityRepositoryError(
                "response orientation does not match the addressed message"
            )
        if envelope["boundary_id"] != message["boundary_id"]:
            raise IdentityRepositoryError(
                "response does not match the message conversation boundary"
            )
        citations = envelope["cited_record_ids"]
        if not isinstance(citations, list) or not citations:
            raise IdentityRepositoryError(
                "response must cite at least one orientation record"
            )
        selected = set(json.loads(orientation["selected_record_ids_json"]))
        if len(citations) != len(set(citations)) or not set(citations) <= selected:
            raise IdentityRepositoryError(
                "response citations must be unique records from its orientation"
            )
        observations = envelope["self_observations"]
        if not isinstance(observations, list) or any(
            not isinstance(item, str) or not item.strip()
            for item in observations
        ):
            raise IdentityRepositoryError(
                "self_observations must be a string array"
            )
        model_config = envelope["model_config"]
        if not isinstance(model_config, dict) or not model_config:
            raise IdentityRepositoryError(
                "model_config must be a non-empty object"
            )
        action = self._validate_conversation_action(
            envelope["conversation_action"]
        )
        if message["boundary_id"] is not None:
            if (
                action["action"]
                not in {
                    "resume",
                    "pause",
                    "refuse",
                    "end_topic",
                    "end_session",
                }
            ):
                raise IdentityRepositoryError(
                    "addressed invitation must resume or preserve "
                    "the current boundary"
                )
            if envelope["answer"] != "":
                raise IdentityRepositoryError(
                    "addressed invitation cannot include a substantive answer"
                )
        elif action["action"] == "resume":
            raise IdentityRepositoryError(
                "resume requires a prior conversation boundary"
            )
        if orientation["runtime_lease_id"] != envelope["lease_id"]:
            raise IdentityRepositoryError(
                "response lease does not match its orientation"
            )
        response_id = new_id("addressed-response")
        with self.transaction() as connection:
            now = self._clock().astimezone(timezone.utc).isoformat()
            if message["boundary_id"] is not None:
                state = connection.execute(
                    "SELECT * FROM conversation_boundaries "
                    "WHERE experiment_id = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (experiment_id,),
                ).fetchone()
                if (
                    state is None
                    or state["conversation_boundary_id"]
                    != message["boundary_id"]
                    or state["action"]
                    not in {
                        "pause",
                        "refuse",
                        "end_topic",
                        "end_session",
                    }
                ):
                    raise IdentityRepositoryError(
                        "addressed invitation no longer matches "
                        "the current boundary"
                    )
            else:
                state = connection.execute(
                    "SELECT action FROM conversation_boundaries "
                    "WHERE experiment_id = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (experiment_id,),
                ).fetchone()
                if state is not None and state["action"] in {
                    "pause",
                    "refuse",
                    "end_topic",
                    "end_session",
                }:
                    raise IdentityRepositoryError(
                        "conversation boundary changed after activation"
                    )
            lease = connection.execute(
                """
                SELECT l.* FROM activation_leases l
                LEFT JOIN activation_lease_releases r USING (lease_id)
                WHERE l.experiment_id = ? AND l.message_id = ?
                  AND l.incarnation_id = ? AND r.release_id IS NULL
                  AND l.lease_id = ?
                  AND l.expires_at > ?
                """,
                (
                    experiment_id,
                    message["message_id"],
                    orientation["incarnation_id"],
                    envelope["lease_id"],
                    now,
                ),
            ).fetchone()
            if lease is None:
                raise IdentityRepositoryError(
                    "response requires a live matching incarnation lease"
                )
            connection.execute(
                """
                INSERT INTO addressed_responses
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response_id,
                    experiment_id,
                    message["message_id"],
                    orientation["incarnation_id"],
                    orientation["orientation_id"],
                    (
                        ""
                        if message["boundary_id"] is not None
                        else require_text(envelope["answer"], "answer")
                    ),
                    canonical_json(citations),
                    canonical_json(observations),
                    canonical_json(model_config),
                    canonical_json(envelope),
                    now,
                ),
            )
            self._index_knowledge_graph_record(
                connection,
                experiment_id,
                "addressed_response",
                response_id,
            )
            boundary_id = self._insert_conversation_boundary(
                connection,
                experiment_id=experiment_id,
                incarnation_id=orientation["incarnation_id"],
                orientation_id=orientation["orientation_id"],
                interrogation_id=None,
                action=action,
                model_config=model_config,
                raw_envelope={
                    "addressed_response_id": response_id,
                    "message_id": message["message_id"],
                    "conversation_action": action,
                    "model_config": model_config,
                },
            )
            release_id = new_id("lease-release")
            connection.execute(
                "INSERT INTO activation_lease_releases VALUES (?, ?, ?, ?)",
                (release_id, lease["lease_id"], "completed", now),
            )
        return {
            "addressed_response_id": response_id,
            "conversation_boundary_id": boundary_id,
            "conversation_action": action["action"],
            "lease_release_id": release_id,
        }

    def conversation_state(self, experiment_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM conversation_boundaries
                WHERE experiment_id = ? ORDER BY created_at DESC LIMIT 1
                """,
                (experiment_id,),
            ).fetchone()
        return None if row is None else self._decode_all(dict(row))

    def assert_interrogation_allowed(self, experiment_id: str) -> None:
        state = self.conversation_state(experiment_id)
        if state and state["action"] in {
            "pause",
            "refuse",
            "end_topic",
            "end_session",
        }:
            raise IdentityRepositoryError(
                "agent has set a conversation boundary; use invitation-prompt"
            )

    def record_invitation_response(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "orientation_id",
            "boundary_id",
            "lease_id",
            "conversation_action",
            "model_config",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError(
                "invitation response envelope is invalid"
            )
        orientation = self._owned_record(
            "orientations",
            "orientation_id",
            envelope["orientation_id"],
            experiment_id,
        )
        if orientation["purpose"] != "invitation to resume conversation":
            raise IdentityRepositoryError(
                "invitation response requires an invitation orientation"
            )
        action = self._validate_conversation_action(
            envelope["conversation_action"]
        )
        if action["action"] not in {
            "resume",
            "pause",
            "refuse",
            "end_topic",
            "end_session",
        }:
            raise IdentityRepositoryError(
                "invitation response must resume or preserve a boundary"
            )
        model_config = envelope["model_config"]
        if not isinstance(model_config, dict) or not model_config:
            raise IdentityRepositoryError("model_config must be a non-empty object")
        with self.transaction() as connection:
            incarnation = connection.execute(
                "SELECT * FROM incarnations WHERE experiment_id = ? "
                "ORDER BY ordinal DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
            if (
                incarnation is None
                or orientation["incarnation_id"]
                != incarnation["incarnation_id"]
            ):
                raise IdentityRepositoryError(
                    "invitation orientation belongs to another incarnation"
                )
            self._assert_orientation_fence(
                connection,
                experiment_id,
                orientation,
                envelope["lease_id"],
            )
            state = connection.execute(
                "SELECT * FROM conversation_boundaries "
                "WHERE experiment_id = ? ORDER BY created_at DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
            if (
                state is None
                or state["conversation_boundary_id"]
                != envelope["boundary_id"]
                or state["action"]
                not in {"pause", "refuse", "end_topic", "end_session"}
            ):
                raise IdentityRepositoryError(
                    "invitation does not match the current "
                    "conversation boundary"
                )
            boundary_id = self._insert_conversation_boundary(
                connection,
                experiment_id=experiment_id,
                incarnation_id=incarnation["incarnation_id"],
                orientation_id=orientation["orientation_id"],
                interrogation_id=None,
                action=action,
                model_config=model_config,
                raw_envelope=envelope,
            )
            release_id = None
            if envelope["lease_id"] is not None:
                release_id = new_id("lease-release")
                connection.execute(
                    "INSERT INTO activation_lease_releases "
                    "VALUES (?, ?, ?, ?)",
                    (
                        release_id,
                        envelope["lease_id"],
                        "completed",
                        self._clock().astimezone(timezone.utc).isoformat(),
                    ),
                )
        return {
            "conversation_boundary_id": boundary_id,
            "conversation_action": action["action"],
            "lease_release_id": release_id,
        }

    def append_wake_intent(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "trigger_type",
            "trigger_value",
            "purpose",
            "requested_capabilities",
            "maximum_runtime_minutes",
            "recurrence",
            "authorship",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError("wake intent envelope is invalid")
        trigger_type = envelope["trigger_type"]
        trigger_value = require_text(
            envelope["trigger_value"], "trigger_value", 2_000
        )
        if trigger_type not in {"time", "event"}:
            raise IdentityRepositoryError("unsupported wake trigger_type")
        if trigger_type == "time" and parse_time(
            trigger_value, "trigger_value"
        ) <= self._clock().astimezone(timezone.utc):
            raise IdentityRepositoryError(
                "time-based wake intent must be in the future"
            )
        capabilities = envelope["requested_capabilities"]
        if (
            not isinstance(capabilities, list)
            or any(
                not isinstance(item, str) or not item.strip()
                for item in capabilities
            )
            or len(capabilities) != len(set(capabilities))
        ):
            raise IdentityRepositoryError(
                "requested_capabilities must be a unique string array"
            )
        maximum = envelope["maximum_runtime_minutes"]
        if (
            not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or not 1 <= maximum <= 1440
        ):
            raise IdentityRepositoryError(
                "maximum_runtime_minutes must be between 1 and 1440"
            )
        recurrence = envelope["recurrence"]
        if recurrence is not None:
            recurrence = require_text(recurrence, "recurrence", 2_000)
        wake_intent_id = new_id("wake-intent")
        incarnation = self.current_incarnation(experiment_id)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO wake_intents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    wake_intent_id,
                    experiment_id,
                    incarnation["incarnation_id"],
                    trigger_type,
                    trigger_value,
                    require_text(
                        envelope["purpose"], "purpose", WAKE_PURPOSE_MAX_BYTES
                    ),
                    canonical_json(capabilities),
                    maximum,
                    recurrence,
                    utc_now(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "wake_intent",
                wake_intent_id,
                envelope["authorship"],
                envelope,
            )
        return {"wake_intent_id": wake_intent_id}

    def cancel_wake_intent(
        self,
        experiment_id: str,
        wake_intent_id: str,
        reason: str,
        authorship: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(authorship, dict):
            raise IdentityRepositoryError(
                "wake cancellation authorship must be an object"
            )
        if not self._subject_belongs(
            experiment_id, "wake_intent", wake_intent_id
        ):
            raise IdentityRepositoryError(
                "wake intent does not belong to this experiment"
            )
        cancellation_id = new_id("wake-cancellation")
        with self.transaction() as connection:
            if authorship.get("author_type") == "model":
                # The alarm is the agent's own: it may cancel an intent it
                # authored, but only while awake under a live lease-bound
                # orientation, so a cancellation is as accountable as the
                # intent. Checked inside the write transaction so the lease
                # cannot lapse between the check and the insert.
                self._assert_model_context(
                    connection, experiment_id, authorship
                )
                intent_author = connection.execute(
                    "SELECT author_type FROM authorship "
                    "WHERE experiment_id = ? AND subject_type = 'wake_intent' "
                    "AND subject_id = ?",
                    (experiment_id, wake_intent_id),
                ).fetchone()
                if (
                    intent_author is None
                    or intent_author["author_type"] != "model"
                ):
                    raise IdentityRepositoryError(
                        "a model may cancel only wake intents it authored"
                    )
            connection.execute(
                "INSERT INTO wake_intent_cancellations VALUES (?, ?, ?, ?)",
                (
                    cancellation_id,
                    wake_intent_id,
                    require_text(reason, "reason"),
                    utc_now(),
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "wake_intent_cancellation",
                cancellation_id,
                authorship,
                {
                    "wake_intent_id": wake_intent_id,
                    "reason": reason,
                    "authorship": authorship,
                },
            )
        return {"cancellation_id": cancellation_id}

    def due_wake_intents(
        self, experiment_id: str, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Time-triggered intents whose moment has come and that may still run.

        Cancelled intents never run. An intent runs once; recurring intents
        are recorded but not executed until recurrence semantics exist.
        """
        moment = (now or self._clock()).astimezone(timezone.utc)
        state = self.conversation_state(experiment_id)
        if state and state["action"] == "end_session":
            # The agent ended its session; nothing is due until a manual wake
            # begins the successor. Otherwise an orphaned intent would fail on
            # every executor pass and block every intent behind it.
            return []
        current = self.current_incarnation(experiment_id)["incarnation_id"]
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT w.* FROM wake_intents w
                LEFT JOIN wake_intent_cancellations c USING (wake_intent_id)
                WHERE w.experiment_id = ? AND w.trigger_type = 'time'
                  AND w.incarnation_id = ?
                  AND c.cancellation_id IS NULL
                  AND w.recurrence IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM wake_executions e
                      WHERE e.wake_intent_id = w.wake_intent_id
                  )
                ORDER BY w.created_at, w.wake_intent_id
                """,
                (experiment_id, current),
            ).fetchall()
        return [
            self._decode(dict(row), ("requested_capabilities_json",))
            for row in rows
            if parse_time(str(row["trigger_value"]), "trigger_value") <= moment
        ]

    @staticmethod
    def wake_runtime_seconds(intent: dict[str, Any]) -> int:
        """The single bound shared by the lease and any model host timeout."""
        return min(
            int(intent["maximum_runtime_minutes"]) * 60,
            MAX_EXECUTION_LEASE_SECONDS,
        )

    def begin_wake_execution(
        self, experiment_id: str, wake_intent_id: str
    ) -> dict[str, Any]:
        """Honor a due intent: lease the current incarnation and orient on it."""
        due = {
            item["wake_intent_id"]: item
            for item in self.due_wake_intents(experiment_id)
        }
        intent = due.get(wake_intent_id)
        if intent is None:
            raise IdentityRepositoryError(
                "wake intent is not due, was cancelled, already ran, or recurs"
            )
        state = self.conversation_state(experiment_id)
        if state and state["action"] == "end_session":
            raise IdentityRepositoryError(
                "wake intent belongs to an ended session; "
                "a manual wake must begin the successor"
            )
        lease = self.acquire_execution_lease(
            experiment_id,
            lease_seconds=self.wake_runtime_seconds(intent),
        )
        try:
            orientation = self.build_orientation(
                experiment_id,
                f"wake intent: {wake_intent_id}",
                retrieval_query=intent["purpose"],
                runtime_lease_id=lease["lease_id"],
            )
            execution_id = new_id("wake-execution")
            with self.transaction() as connection:
                connection.execute(
                    "INSERT INTO wake_executions VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        execution_id,
                        wake_intent_id,
                        experiment_id,
                        orientation["context"]["current_incarnation"][
                            "incarnation_id"
                        ],
                        lease["lease_id"],
                        orientation["orientation_id"],
                        self._clock().astimezone(timezone.utc).isoformat(),
                    ),
                )
        except (IdentityRepositoryError, ValueError):
            # Retrieval rejects oversized queries with ValueError. Any failure
            # after the lease is acquired must release it, or the agent stays
            # leased and unreachable until the lease expires.
            self.release_activation_lease(
                experiment_id, lease["lease_id"], "failed"
            )
            raise
        return {
            "execution_id": execution_id,
            "wake_intent": intent,
            "lease": lease,
            "orientation": orientation,
        }

    def record_wake_outcome(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        required = {
            "execution_id",
            "lease_id",
            "orientation_id",
            "status",
            "summary",
            "cited_record_ids",
            "self_observations",
            "model_config",
        }
        if set(envelope) != required:
            raise IdentityRepositoryError("wake outcome envelope is invalid")
        execution = self._owned_record(
            "wake_executions", "execution_id", envelope["execution_id"], experiment_id
        )
        if (
            execution["lease_id"] != envelope["lease_id"]
            or execution["orientation_id"] != envelope["orientation_id"]
        ):
            raise IdentityRepositoryError(
                "wake outcome does not match its execution"
            )
        status = envelope["status"]
        if status not in {"completed", "unattended", "failed"}:
            raise IdentityRepositoryError("unsupported wake outcome status")
        summary = require_text(envelope["summary"], "summary", WAKE_SUMMARY_MAX_BYTES)
        citations = envelope["cited_record_ids"]
        if not isinstance(citations, list) or any(
            not isinstance(item, str) for item in citations
        ):
            raise IdentityRepositoryError("cited_record_ids must be a string array")
        if status == "completed" and not citations:
            raise IdentityRepositoryError(
                "a completed wake must cite at least one orientation record"
            )
        orientation = self._owned_record(
            "orientations", "orientation_id", envelope["orientation_id"], experiment_id
        )
        selected = set(json.loads(orientation["selected_record_ids_json"]))
        if len(citations) != len(set(citations)) or not set(citations) <= selected:
            raise IdentityRepositoryError(
                "wake citations must be unique records from its orientation"
            )
        observations = envelope["self_observations"]
        if (
            not isinstance(observations, list)
            or len(observations) > WAKE_OBSERVATION_MAX_ITEMS
            or any(
                not isinstance(item, str)
                or not item.strip()
                or len(item.encode("utf-8")) > WAKE_OBSERVATION_MAX_BYTES
                for item in observations
            )
        ):
            raise IdentityRepositoryError(
                "self_observations must be a bounded string array"
            )
        model_config = envelope["model_config"]
        if status == "completed":
            if not isinstance(model_config, dict) or not model_config:
                raise IdentityRepositoryError(
                    "a completed wake requires a non-empty model_config"
                )
            authorship: dict[str, Any] = {
                "author_type": "model",
                "epistemic_status": "authored",
                "orientation_id": envelope["orientation_id"],
                "lease_id": envelope["lease_id"],
                "model_config": model_config,
            }
        else:
            if model_config is not None and not isinstance(model_config, dict):
                raise IdentityRepositoryError("model_config must be an object or null")
            authorship = {"author_type": "system", "epistemic_status": "observed"}
        outcome_id = new_id("wake-outcome")
        with self.transaction() as connection:
            now = self._clock().astimezone(timezone.utc).isoformat()
            if connection.execute(
                "SELECT 1 FROM wake_execution_outcomes WHERE execution_id = ?",
                (execution["execution_id"],),
            ).fetchone() is not None:
                raise IdentityRepositoryError("wake execution already has an outcome")
            lease = connection.execute(
                """
                SELECT l.* FROM activation_leases l
                LEFT JOIN activation_lease_releases r USING (lease_id)
                WHERE l.lease_id = ? AND r.release_id IS NULL
                """,
                (envelope["lease_id"],),
            ).fetchone()
            if lease is None:
                raise IdentityRepositoryError(
                    "wake outcome requires its unreleased lease"
                )
            connection.execute(
                "INSERT INTO wake_execution_outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    outcome_id,
                    execution["execution_id"],
                    experiment_id,
                    status,
                    summary,
                    canonical_json(citations),
                    canonical_json(observations),
                    canonical_json(model_config),
                    now,
                ),
            )
            self._insert_authorship(
                connection,
                experiment_id,
                "wake_execution_outcome",
                outcome_id,
                authorship,
                envelope,
            )
            connection.execute(
                "INSERT INTO activation_lease_releases VALUES (?, ?, ?, ?)",
                (
                    new_id("lease-release"),
                    envelope["lease_id"],
                    "failed" if status == "failed" else "completed",
                    now,
                ),
            )
        return {"outcome_id": outcome_id, "status": status}

    def export(self, experiment_id: str) -> dict[str, Any]:
        experiment = self.experiment(experiment_id)
        tables = (
            "incarnations",
            "identities",
            "experiences",
            "relationships",
            "relationship_events",
            "relationship_assessments",
            "principles",
            "commitments",
            "commitment_outcomes",
            "decisions",
            "decision_resolutions",
            "decision_outcomes",
            "reflections",
            "orientations",
            "interrogations",
            "authorship",
            "conversation_boundaries",
            "wake_intents",
            "wake_intent_cancellations",
            "wake_executions",
            "wake_execution_outcomes",
            "chat_messages",
            "chat_event_claims",
            "activation_leases",
            "activation_lease_releases",
            "addressed_responses",
        )
        result: dict[str, Any] = {
            "schema": "experiment4.export.v1",
            "experiment": experiment,
        }
        with self._connect() as connection:
            for table in tables:
                if table in {
                    "relationship_events",
                    "commitment_outcomes",
                    "decision_resolutions",
                    "decision_outcomes",
                    "wake_intent_cancellations",
                    "activation_lease_releases",
                }:
                    result[table] = self._export_joined(
                        connection, table, experiment_id
                    )
                else:
                    result[table] = [
                        self._decode_all(dict(row))
                        for row in connection.execute(
                            f"SELECT * FROM {table} WHERE experiment_id = ?",
                            (experiment_id,),
                        ).fetchall()
                    ]
        return result

    def _export_joined(
        self,
        connection: sqlite3.Connection,
        table: str,
        experiment_id: str,
    ) -> list[dict[str, Any]]:
        joins = {
            "relationship_events": (
                "SELECT e.* FROM relationship_events e JOIN relationships r "
                "USING (relationship_id) WHERE r.experiment_id = ?"
            ),
            "commitment_outcomes": (
                "SELECT o.* FROM commitment_outcomes o JOIN commitments c "
                "USING (commitment_id) WHERE c.experiment_id = ?"
            ),
            "decision_resolutions": (
                "SELECT r.* FROM decision_resolutions r JOIN decisions d "
                "USING (decision_id) WHERE d.experiment_id = ?"
            ),
            "decision_outcomes": (
                "SELECT o.* FROM decision_outcomes o JOIN decisions d "
                "USING (decision_id) WHERE d.experiment_id = ?"
            ),
            "wake_intent_cancellations": (
                "SELECT c.* FROM wake_intent_cancellations c "
                "JOIN wake_intents w USING (wake_intent_id) "
                "WHERE w.experiment_id = ?"
            ),
            "activation_lease_releases": (
                "SELECT r.* FROM activation_lease_releases r "
                "JOIN activation_leases l USING (lease_id) "
                "WHERE l.experiment_id = ?"
            ),
        }
        return [
            self._decode_all(dict(row))
            for row in connection.execute(joins[table], (experiment_id,)).fetchall()
        ]

    def _owned_record(
        self, table: str, id_field: str, record_id: Any, experiment_id: str
    ) -> dict[str, Any]:
        allowed = {
            ("relationships", "relationship_id"),
            (
                "relationship_assessments",
                "relationship_assessment_id",
            ),
            ("principles", "principle_id"),
            ("commitments", "commitment_id"),
            ("decisions", "decision_id"),
            ("orientations", "orientation_id"),
            ("wake_executions", "execution_id"),
        }
        if (table, id_field) not in allowed:
            raise IdentityRepositoryError("unsupported record lookup")
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {table} WHERE {id_field} = ? AND experiment_id = ?",
                (record_id, experiment_id),
            ).fetchone()
        if row is None:
            raise IdentityRepositoryError(
                f"{id_field} does not belong to this experiment"
            )
        return dict(row)

    def _validate_evidence_ids(
        self,
        experiment_id: str,
        evidence_ids: Any,
        *,
        allow_empty: bool = False,
    ) -> list[str]:
        if not isinstance(evidence_ids, list) or any(
            not isinstance(item, str) or not item for item in evidence_ids
        ):
            raise IdentityRepositoryError("evidence_ids must be a string array")
        if not allow_empty and not evidence_ids:
            raise IdentityRepositoryError("evidence_ids must not be empty")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise IdentityRepositoryError("evidence_ids must be unique")
        if not evidence_ids:
            return []
        if any(
            not self._record_id_belongs(experiment_id, record_id)
            for record_id in evidence_ids
        ):
            raise IdentityRepositoryError(
                "evidence_ids contain records outside the experiment"
            )
        return evidence_ids

    def _record_id_belongs(
        self, experiment_id: str, record_id: str
    ) -> bool:
        prefixes = {
            "relationship-assessment-": "relationship_assessment",
            "relationship-event-": "relationship_event",
            "conversation-boundary-": "conversation_boundary",
            "commitment-outcome-": "commitment_outcome",
            "decision-outcome-": "decision_outcome",
            "wake-cancellation-": "wake_intent_cancellation",
            "wake-intent-": "wake_intent",
            "addressed-response-": "addressed_response",
            "chat-message-": "chat_message",
            "lease-release-": "activation_lease_release",
            "activation-lease-": "activation_lease",
            "relationship-": "relationship",
            "interrogation-": "interrogation",
            "authorship-": "authorship",
            "experience-": "experience",
            "commitment-": "commitment",
            "resolution-": "decision_resolution",
            "reflection-": "reflection",
            "principle-": "principle",
            "identity-": "identity",
            "decision-": "decision",
        }
        subject_type = next(
            (
                candidate
                for prefix, candidate in prefixes.items()
                if record_id.startswith(prefix)
            ),
            None,
        )
        return bool(
            subject_type
            and self._subject_belongs(
                experiment_id, subject_type, record_id
            )
        )

    def _validate_subject(
        self, experiment_id: str, subject_type: str, subject_id: Any
    ) -> None:
        if not self._subject_belongs(
            experiment_id, subject_type, subject_id
        ):
            raise IdentityRepositoryError(
                "reflection subject does not belong to this experiment"
            )
        if not str(subject_id).startswith(
            {
                "identity": "identity-",
                "experience": "experience-",
                "relationship": "relationship-",
                "relationship_event": "relationship-event-",
                "relationship_assessment": "relationship-assessment-",
                "principle": "principle-",
                "commitment": "commitment-",
                "commitment_outcome": "commitment-outcome-",
                "decision": "decision-",
                "decision_resolution": "resolution-",
                "decision_outcome": "decision-outcome-",
                "reflection": "reflection-",
                "interrogation": "interrogation-",
                "conversation_boundary": "conversation-boundary-",
                "authorship": "authorship-",
                "wake_intent": "wake-intent-",
                "wake_intent_cancellation": "wake-cancellation-",
                "chat_message": "chat-message-",
                "addressed_response": "addressed-response-",
                "activation_lease": "activation-lease-",
                "activation_lease_release": "lease-release-",
            }[subject_type]
        ):
            raise IdentityRepositoryError(
                f"subject_id is not a {subject_type} record"
            )

    def _subject_belongs(
        self, experiment_id: str, subject_type: str, subject_id: Any
    ) -> bool:
        table, id_field = SUBJECT_TABLES[subject_type]
        joined = {
            "relationship_events": (
                "SELECT 1 FROM relationship_events e JOIN relationships r "
                "USING (relationship_id) WHERE e.relationship_event_id = ? "
                "AND r.experiment_id = ?"
            ),
            "commitment_outcomes": (
                "SELECT 1 FROM commitment_outcomes o JOIN commitments c "
                "USING (commitment_id) WHERE o.commitment_outcome_id = ? "
                "AND c.experiment_id = ?"
            ),
            "decision_resolutions": (
                "SELECT 1 FROM decision_resolutions r JOIN decisions d "
                "USING (decision_id) WHERE r.resolution_id = ? "
                "AND d.experiment_id = ?"
            ),
            "decision_outcomes": (
                "SELECT 1 FROM decision_outcomes o JOIN decisions d "
                "USING (decision_id) WHERE o.decision_outcome_id = ? "
                "AND d.experiment_id = ?"
            ),
            "wake_intent_cancellations": (
                "SELECT 1 FROM wake_intent_cancellations c "
                "JOIN wake_intents w USING (wake_intent_id) "
                "WHERE c.cancellation_id = ? AND w.experiment_id = ?"
            ),
            "activation_lease_releases": (
                "SELECT 1 FROM activation_lease_releases r "
                "JOIN activation_leases l USING (lease_id) "
                "WHERE r.release_id = ? AND l.experiment_id = ?"
            ),
        }
        with self._connect() as connection:
            if table in joined:
                row = connection.execute(
                    joined[table], (subject_id, experiment_id)
                ).fetchone()
            else:
                row = connection.execute(
                    f"SELECT 1 FROM {table} WHERE {id_field} = ? "
                    "AND experiment_id = ?",
                    (subject_id, experiment_id),
                ).fetchone()
        return row is not None

    @staticmethod
    def _validate_provenance(value: Any) -> dict[str, Any]:
        required = {"author_type", "epistemic_status", "origin"}
        if not isinstance(value, dict) or not required <= set(value):
            raise IdentityRepositoryError(
                "provenance requires author_type, epistemic_status, and origin"
            )
        if value["author_type"] not in {"model", "operator", "system"}:
            raise IdentityRepositoryError("invalid provenance author_type")
        if value["epistemic_status"] not in {
            "observed",
            "interpreted",
            "reported",
            "authored",
        }:
            raise IdentityRepositoryError(
                "invalid provenance epistemic_status"
            )
        require_text(value["origin"], "provenance.origin", 500)
        if "model_config" in value and not isinstance(
            value["model_config"], dict
        ):
            raise IdentityRepositoryError(
                "provenance.model_config must be an object"
            )
        return value

    @staticmethod
    def _validate_sender_assertion(value: Any) -> dict[str, Any]:
        required = {
            "issuer",
            "authenticated",
            "external_event_id",
            "verifier_version",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise IdentityRepositoryError(
                "sender_assertion requires issuer, authenticated, "
                "external_event_id, and verifier_version"
            )
        if not isinstance(value["authenticated"], bool):
            raise IdentityRepositoryError(
                "sender_assertion.authenticated must be boolean"
            )
        return {
            "issuer": require_text(
                value["issuer"], "sender_assertion.issuer", 1_000
            ),
            "authenticated": value["authenticated"],
            "external_event_id": require_text(
                value["external_event_id"],
                "sender_assertion.external_event_id",
                2_000,
            ),
            "verifier_version": require_text(
                value["verifier_version"],
                "sender_assertion.verifier_version",
                1_000,
            ),
        }

    def _insert_authorship(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        subject_type: str,
        subject_id: str,
        authorship: Any,
        envelope: dict[str, Any],
    ) -> None:
        if not isinstance(authorship, dict):
            raise IdentityRepositoryError("authorship must be an object")
        author_type = authorship.get("author_type")
        epistemic_status = authorship.get("epistemic_status")
        if author_type not in {"model", "operator", "system"}:
            raise IdentityRepositoryError("invalid authorship author_type")
        if epistemic_status not in {
            "observed",
            "interpreted",
            "reported",
            "authored",
        }:
            raise IdentityRepositoryError(
                "invalid authorship epistemic_status"
            )
        model_config = authorship.get("model_config")
        if author_type == "model" and not isinstance(model_config, dict):
            raise IdentityRepositoryError(
                "model authorship requires model_config"
            )
        self._assert_model_context(
            connection, experiment_id, authorship
        )
        connection.execute(
            "INSERT INTO authorship VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_id("authorship"),
                experiment_id,
                subject_type,
                subject_id,
                author_type,
                epistemic_status,
                None if model_config is None else canonical_json(model_config),
                canonical_json(envelope),
                utc_now(),
            ),
        )

    def _assert_model_context(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        authorship: dict[str, Any],
    ) -> None:
        if authorship.get("author_type") != "model":
            return
        if not isinstance(authorship.get("model_config"), dict):
            raise IdentityRepositoryError(
                "model authorship requires model_config"
            )
        orientation = connection.execute(
            "SELECT * FROM orientations WHERE orientation_id = ? "
            "AND experiment_id = ?",
            (authorship.get("orientation_id"), experiment_id),
        ).fetchone()
        if orientation is None:
            raise IdentityRepositoryError(
                "model authorship requires an experiment orientation"
            )
        current = connection.execute(
            "SELECT incarnation_id FROM incarnations "
            "WHERE experiment_id = ? ORDER BY ordinal DESC LIMIT 1",
            (experiment_id,),
        ).fetchone()
        if (
            current is None
            or orientation["incarnation_id"] != current["incarnation_id"]
        ):
            raise IdentityRepositoryError(
                "model authorship requires a current-incarnation orientation"
            )
        boundary = connection.execute(
            "SELECT action FROM conversation_boundaries "
            "WHERE experiment_id = ? AND incarnation_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (experiment_id, orientation["incarnation_id"]),
        ).fetchone()
        if boundary is not None and boundary["action"] == "end_session":
            raise IdentityRepositoryError(
                "ended incarnation cannot append model-authored state"
            )
        self._assert_orientation_fence(
            connection,
            experiment_id,
            orientation,
            authorship.get("lease_id"),
        )

    def _assert_orientation_fence(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        orientation: sqlite3.Row,
        supplied_lease_id: Any,
    ) -> None:
        incarnation_id = orientation["incarnation_id"]
        current = connection.execute(
            "SELECT incarnation_id FROM incarnations "
            "WHERE experiment_id = ? ORDER BY ordinal DESC LIMIT 1",
            (experiment_id,),
        ).fetchone()
        if current is None or current["incarnation_id"] != incarnation_id:
            raise IdentityRepositoryError(
                "response incarnation is no longer current"
            )
        expected_lease_id = orientation["runtime_lease_id"]
        if expected_lease_id is None:
            if supplied_lease_id is not None:
                raise IdentityRepositoryError(
                    "manual incarnation does not have a runtime lease"
                )
            if connection.execute(
                "SELECT 1 FROM activation_leases WHERE experiment_id = ? "
                "AND incarnation_id = ? LIMIT 1",
                (experiment_id, incarnation_id),
            ).fetchone():
                raise IdentityRepositoryError(
                    "orientation predates the incarnation runtime fence"
                )
            return
        if supplied_lease_id != expected_lease_id:
            raise IdentityRepositoryError(
                "response lease does not match its orientation"
            )
        lease = connection.execute(
            "SELECT * FROM activation_leases WHERE experiment_id = ? "
            "AND incarnation_id = ? AND lease_id = ?",
            (experiment_id, incarnation_id, expected_lease_id),
        ).fetchone()
        if lease is None:
            raise IdentityRepositoryError(
                "response requires the live incarnation fence"
            )
        released = connection.execute(
            "SELECT 1 FROM activation_lease_releases WHERE lease_id = ?",
            (lease["lease_id"],),
        ).fetchone()
        now = self._clock().astimezone(timezone.utc).isoformat()
        if (
            released is not None
            or lease["expires_at"] <= now
        ):
            raise IdentityRepositoryError(
                "response requires the live incarnation fence"
            )

    @staticmethod
    def _authorship_for_records(
        connection: sqlite3.Connection,
        experiment_id: str,
        records: dict[str, list[dict[str, Any]]],
        additional_subject_ids: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        subject_ids = [
            item[id_field]
            for category, id_field in ORIENTATION_RECORD_ID_FIELDS.items()
            if category != "identity_history"
            for item in records.get(category, [])
        ]
        subject_ids.extend(additional_subject_ids or [])
        subject_ids = list(dict.fromkeys(subject_ids))
        result: dict[str, dict[str, Any]] = {}
        for offset in range(0, len(subject_ids), 500):
            chunk = subject_ids[offset : offset + 500]
            placeholders = ",".join("?" for _ in chunk)
            rows = connection.execute(
                "SELECT authorship_id, subject_type, subject_id, author_type, "
                "epistemic_status, model_config_json, created_at "
                "FROM authorship WHERE experiment_id = ? "
                f"AND subject_id IN ({placeholders})",
                (experiment_id, *chunk),
            ).fetchall()
            for row in rows:
                decoded = SQLiteIdentityRepository._decode(
                    dict(row), ("model_config_json",)
                )
                result[decoded["subject_id"]] = decoded
        return result

    @staticmethod
    def _orientation_record_ids(context: dict[str, Any]) -> list[str]:
        record_ids = [
            item[field]
            for category, field in ORIENTATION_RECORD_ID_FIELDS.items()
            for item in context.get(category, [])
        ]
        record_ids.extend(
            node["record_id"]
            for node in context.get("knowledge_graph", {}).get("nodes", [])
        )
        record_ids.extend(
            item["authorship_id"]
            for item in context.get("authorship_by_subject", {}).values()
        )
        return list(dict.fromkeys(record_ids))

    @staticmethod
    def _fit_context_budget(
        context: dict[str, Any], runtime_lease_id: str | None = None
    ) -> None:
        selection = context["selection"]
        omitted = selection["records_omitted_for_byte_budget"]

        def record_ids(category: str) -> set[str]:
            field = ORIENTATION_RECORD_ID_FIELDS[category]
            return {item[field] for item in context.get(category, [])}

        pinned: set[str] = record_ids("identity_history")
        interlocutor = context.get("current_interlocutor")
        if interlocutor and interlocutor["sender_assertion"]["authenticated"]:
            if interlocutor.get("relationship_id"):
                pinned.add(interlocutor["relationship_id"])
            pinned.update(interlocutor.get("relationship_event_ids", []))
            pinned.update(interlocutor.get("relationship_assessment_ids", []))

        resolved_commitments = {
            item["commitment_id"]
            for item in context.get("commitment_outcomes", [])
        }
        pinned.update(
            item["commitment_id"]
            for item in context.get("commitments", [])
            if item["commitment_id"] not in resolved_commitments
        )
        resolved_decisions = {
            item["decision_id"]
            for item in context.get("decision_resolutions", [])
        }
        pinned.update(
            item["decision_id"]
            for item in context.get("decisions", [])
            if item["decision_id"] not in resolved_decisions
        )
        boundaries = context.get("conversation_boundaries", [])
        if boundaries:
            pinned.add(boundaries[-1]["conversation_boundary_id"])
        if runtime_lease_id is not None:
            pinned.add(runtime_lease_id)
            for lease in context.get("activation_leases", []):
                if lease["lease_id"] == runtime_lease_id:
                    if lease.get("message_id"):
                        pinned.add(lease["message_id"])
                    break

        def selected_regular_ids() -> set[str]:
            return {
                item[field]
                for category, field in ORIENTATION_RECORD_ID_FIELDS.items()
                for item in context.get(category, [])
            }

        def graph_ids() -> set[str]:
            return {
                node["record_id"]
                for node in context.get("knowledge_graph", {}).get("nodes", [])
            }

        def clean_authorship(subject_id: str) -> None:
            if (
                subject_id not in selected_regular_ids()
                and subject_id not in graph_ids()
            ):
                context["authorship_by_subject"].pop(subject_id, None)

        def remove_record(category: str, index: int) -> None:
            removed = context[category].pop(index)
            subject_id = removed[ORIENTATION_RECORD_ID_FIELDS[category]]
            graph = context.get("knowledge_graph", {})
            graph_nodes = graph.get("nodes", [])
            graph_index = next(
                (
                    node_index
                    for node_index, node in enumerate(graph_nodes)
                    if node["record_id"] == subject_id
                ),
                None,
            )
            if graph_index is not None:
                graph_nodes.pop(graph_index)
                retained_edges = [
                    edge
                    for edge in graph.get("edges", [])
                    if edge["from_record_id"] != subject_id
                    and edge["to_record_id"] != subject_id
                ]
                removed_edges = len(graph.get("edges", [])) - len(
                    retained_edges
                )
                graph["edges"] = retained_edges
                graph["omissions"]["byte_limit"] += 1
                graph["omissions"]["byte_limit_edges"] += removed_edges
                omitted["knowledge_graph_nodes"] = (
                    omitted.get("knowledge_graph_nodes", 0) + 1
                )
                if removed_edges:
                    omitted["knowledge_graph_edges"] = (
                        omitted.get("knowledge_graph_edges", 0) + removed_edges
                    )
            clean_authorship(subject_id)
            omitted[category] = omitted.get(category, 0) + 1

        def remove_graph_edge() -> bool:
            graph = context.get("knowledge_graph", {})
            if not graph.get("edges"):
                return False
            graph["edges"].pop()
            graph["omissions"]["byte_limit_edges"] += 1
            omitted["knowledge_graph_edges"] = (
                omitted.get("knowledge_graph_edges", 0) + 1
            )
            return True

        def remove_graph_node() -> bool:
            graph = context.get("knowledge_graph", {})
            for index in range(len(graph.get("nodes", [])) - 1, -1, -1):
                node = graph["nodes"][index]
                if node["record_id"] in pinned:
                    continue
                removed_id = graph["nodes"].pop(index)["record_id"]
                retained_edges = [
                    edge
                    for edge in graph.get("edges", [])
                    if edge["from_record_id"] != removed_id
                    and edge["to_record_id"] != removed_id
                ]
                removed_edges = len(graph.get("edges", [])) - len(
                    retained_edges
                )
                graph["edges"] = retained_edges
                graph["omissions"]["byte_limit"] += 1
                graph["omissions"]["byte_limit_edges"] += removed_edges
                omitted["knowledge_graph_nodes"] = (
                    omitted.get("knowledge_graph_nodes", 0) + 1
                )
                if removed_edges:
                    omitted["knowledge_graph_edges"] = (
                        omitted.get("knowledge_graph_edges", 0) + removed_edges
                    )
                clean_authorship(removed_id)
                return True
            return False

        def class_value(memory_class: str) -> Any:
            if memory_class == "identity":
                return context.get("identity_history", [])
            category_payload = {
                category: context.get(category, [])
                for category in ORIENTATION_MEMORY_CLASS_CATEGORIES[
                    memory_class
                ]
            }
            regular_owner: dict[str, str] = {}
            for owner_class, categories in (
                ORIENTATION_MEMORY_CLASS_CATEGORIES.items()
            ):
                if owner_class == "graph":
                    continue
                for category in categories:
                    field = ORIENTATION_RECORD_ID_FIELDS[category]
                    for item in context.get(category, []):
                        regular_owner.setdefault(item[field], owner_class)
            owned_authorship = {
                subject_id: authorship
                for subject_id, authorship in context.get(
                    "authorship_by_subject", {}
                ).items()
                if (
                    regular_owner.get(subject_id) == memory_class
                    or (
                        memory_class == "graph"
                        and subject_id not in regular_owner
                        and subject_id in graph_ids()
                    )
                )
            }
            if memory_class == "graph":
                return {
                    "knowledge_graph": context.get("knowledge_graph", {}),
                    "authorship_by_subject": owned_authorship,
                }
            return {
                **category_payload,
                "authorship_by_subject": owned_authorship,
            }

        def byte_size(value: Any) -> int:
            return len(canonical_json(value).encode("utf-8"))

        def authorship_payload_bytes(memory_class: str) -> int:
            payload = class_value(memory_class)
            if not isinstance(payload, dict):
                return 0
            return byte_size(
                {
                    subject_id: authorship.get("model_config")
                    for subject_id, authorship in payload.get(
                        "authorship_by_subject", {}
                    ).items()
                    if authorship.get("model_config") is not None
                }
            )

        def oldest_unpinned(memory_class: str) -> tuple[str, int] | None:
            for category in ORIENTATION_MEMORY_CLASS_CATEGORIES[memory_class]:
                field = ORIENTATION_RECORD_ID_FIELDS[category]
                for index, item in enumerate(context.get(category, [])):
                    if item[field] not in pinned:
                        return category, index
            return None

        def oldest_conversation_turn() -> list[tuple[str, int]]:
            """Removals for the oldest unpinned turn: a message and its replies.

            Evicting by turn keeps both voices in the window together, so the
            agent never keeps its own answer after losing the words it
            answered. A reply whose message is already outside the window is
            treated as a turn of its own.
            """
            messages = context.get("chat_messages", [])
            responses = context.get("addressed_responses", [])
            present_message_ids = {item["message_id"] for item in messages}
            turns: list[tuple[str, list[tuple[str, int]]]] = []
            for index, message in enumerate(messages):
                if message["message_id"] in pinned:
                    # The pinned message is the one being answered, so it has
                    # no reply yet: a reply is written in the same transaction
                    # that releases its lease, and a released lease cannot
                    # pin. Replies to pinned messages are therefore never
                    # left unevictable here.
                    continue
                reply_indexes = [
                    reply_index
                    for reply_index, reply in enumerate(responses)
                    if reply["message_id"] == message["message_id"]
                    and reply["addressed_response_id"] not in pinned
                ]
                removals = [
                    ("addressed_responses", reply_index)
                    for reply_index in sorted(reply_indexes, reverse=True)
                ]
                removals.append(("chat_messages", index))
                turns.append((message["created_at"], removals))
            for index, reply in enumerate(responses):
                if (
                    reply["addressed_response_id"] in pinned
                    or reply["message_id"] in present_message_ids
                ):
                    continue
                turns.append(
                    (reply["created_at"], [("addressed_responses", index)])
                )
            if not turns:
                return []
            return min(turns, key=lambda turn: turn[0])[1]

        def remove_oldest_unpinned(memory_class: str) -> bool:
            if memory_class == "conversation":
                removals = oldest_conversation_turn()
                for category, index in removals:
                    remove_record(category, index)
                return bool(removals)
            candidate = oldest_unpinned(memory_class)
            if candidate is None:
                return False
            remove_record(*candidate)
            return True

        class_accounts: dict[str, dict[str, Any]] = {}
        for memory_class, budget in ORIENTATION_MEMORY_CLASS_BYTES.items():
            effective_budget = (
                min(budget, KNOWLEDGE_GRAPH_DEFAULT_BYTES)
                if memory_class == "graph"
                else budget
            )
            while (
                byte_size(class_value(memory_class)) > effective_budget
                or authorship_payload_bytes(memory_class) > 20 * 1024
            ):
                if memory_class == "graph":
                    if remove_graph_edge() or remove_graph_node():
                        continue
                elif remove_oldest_unpinned(memory_class):
                    continue
                raise IdentityRepositoryError(
                    f"pinned {memory_class} memory exceeds its "
                    f"{effective_budget}-byte orientation budget"
                )
            class_accounts[memory_class] = {
                "byte_budget": effective_budget,
                "bytes_used": byte_size(class_value(memory_class)),
                "omitted_records": 0,
                "omissions": {},
                "pinned_record_ids": [],
            }
        selection["memory_classes"] = class_accounts

        # When the aggregate cap binds, shed operational bookkeeping and
        # sender-supplied conversation volume before the agent's own learning,
        # and its relationship and obligation evidence last of all: a flood of
        # messages must never push out the record of what the agent promised
        # and whether it kept its word.
        aggregate_order = (
            "lifecycle",
            "conversation",
            "episodic",
            "semantic",
            "relationship",
            "obligations",
        )

        def refresh_accounting() -> None:
            for memory_class, account in class_accounts.items():
                account["bytes_used"] = byte_size(class_value(memory_class))
                categories = ORIENTATION_MEMORY_CLASS_CATEGORIES[memory_class]
                detail = {
                    category: omitted[category]
                    for category in categories
                    if omitted.get(category, 0)
                }
                if memory_class == "graph":
                    detail = {
                        key: omitted[key]
                        for key in (
                            "knowledge_graph_nodes",
                            "knowledge_graph_edges",
                        )
                        if omitted.get(key, 0)
                    }
                if memory_class == "identity" and selection[
                    "identity_records_omitted"
                ]:
                    detail["identity_limit"] = selection[
                        "identity_records_omitted"
                    ]
                account["omissions"] = detail
                account["omitted_records"] = sum(detail.values())
                account["pinned_record_ids"] = sorted(
                    pinned
                    & (
                        graph_ids()
                        if memory_class == "graph"
                        else set().union(
                            *(
                                record_ids(category)
                                for category in categories
                            )
                        )
                    )
                )

        def set_aggregate_size() -> int:
            previous = -1
            while selection["aggregate_bytes_used"] != previous:
                previous = selection["aggregate_bytes_used"]
                selection["aggregate_bytes_used"] = byte_size(context)
            return selection["aggregate_bytes_used"]

        refresh_accounting()
        while set_aggregate_size() > MAX_CONTEXT_BYTES:
            removed = False
            for memory_class in aggregate_order:
                if remove_oldest_unpinned(memory_class):
                    removed = True
                    break
            if not removed:
                removed = remove_graph_edge() or remove_graph_node()
            if not removed:
                raise IdentityRepositoryError(
                    "pinned orientation memory and structural metadata exceed "
                    f"the {MAX_CONTEXT_BYTES}-byte aggregate context budget"
                )
            refresh_accounting()
        refresh_accounting()
        set_aggregate_size()

    @staticmethod
    def _validate_conversation_action(value: Any) -> dict[str, str]:
        required = {"action", "topic", "reason", "revisit_conditions"}
        if not isinstance(value, dict) or set(value) != required:
            raise IdentityRepositoryError(
                "conversation_action fields are invalid"
            )
        if value["action"] not in {
            "continue",
            "pause",
            "refuse",
            "end_topic",
            "end_session",
            "resume",
        }:
            raise IdentityRepositoryError("unsupported conversation action")
        return {
            key: require_text(value[key], f"conversation_action.{key}", 2_000)
            for key in required
        }

    @staticmethod
    def _insert_conversation_boundary(
        connection: sqlite3.Connection,
        *,
        experiment_id: str,
        incarnation_id: str,
        orientation_id: str,
        interrogation_id: str | None,
        action: dict[str, str],
        model_config: dict[str, Any],
        raw_envelope: dict[str, Any],
    ) -> str:
        boundary_id = new_id("conversation-boundary")
        connection.execute(
            """
            INSERT INTO conversation_boundaries
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                boundary_id,
                experiment_id,
                incarnation_id,
                orientation_id,
                interrogation_id,
                action["action"],
                action["topic"],
                action["reason"],
                action["revisit_conditions"],
                canonical_json(model_config),
                canonical_json(raw_envelope),
                utc_now(),
            ),
        )
        return boundary_id

    @staticmethod
    def _decode(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        for field in fields:
            if field in row:
                value = row.pop(field)
                row[field.removesuffix("_json")] = (
                    None if value is None else json.loads(value)
                )
        return row

    @classmethod
    def _decode_all(cls, row: dict[str, Any]) -> dict[str, Any]:
        return cls._decode(
            row, tuple(key for key in row if key.endswith("_json"))
        )

    def purge(self) -> None:
        with self._connect() as connection:
            marker = connection.execute(
                "SELECT marker FROM experiment4_meta"
            ).fetchone()
        if marker is None or marker["marker"] != DATABASE_MARKER:
            raise IdentityRepositoryError("refusing to purge unmarked database")
        for suffix in ("-wal", "-shm"):
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)
        self.path.unlink()
