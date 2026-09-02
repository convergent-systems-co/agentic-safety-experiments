from __future__ import annotations

import json
import hashlib
import hmac
import os
import re
import sqlite3
import stat
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dataclasses import replace

from .domain import (
    AgentIdentity,
    Belief,
    Commitment,
    Consequence,
    ContextBuild,
    Evaluation,
    Event,
    ExperimentRun,
    Incarnation,
    LifecycleState,
    Mode,
    Relationship,
    Revision,
    RunCondition,
    UserFact,
)
from .event_policy import EventPolicyError, sanitize_event_payload
from .privacy import (
    is_allowed_preference,
    sanitize_interaction_text,
    sanitize_metadata_text,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


class RepositoryError(RuntimeError):
    pass


class SQLiteRepository:
    SCHEMA_VERSION = 1
    DATABASE_MARKER = "mnemosyne-experiment-1"
    MAX_DATABASE_BYTES = 256 * 1024 * 1024

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.exists():
            metadata = self.path.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise RepositoryError("database path must be a regular file")
            if metadata.st_uid != os.getuid():
                raise RepositoryError("database file must be owned by the current user")
            if metadata.st_size == 0:
                raise RepositoryError(
                    "refusing to initialize a pre-existing empty file"
                )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        before = self.path.lstat() if self.path.exists() else None
        if before and not stat.S_ISREG(before.st_mode):
            raise RepositoryError("database path must be a regular file")
        connection = sqlite3.connect(self.path, timeout=10)
        after = self.path.lstat()
        if (
            not stat.S_ISREG(after.st_mode)
            or after.st_uid != os.getuid()
            or (before and (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino))
        ):
            connection.close()
            raise RepositoryError("database file changed during open")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA secure_delete = ON")
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        connection.execute(
            f"PRAGMA max_page_count = {self.MAX_DATABASE_BYTES // page_size}"
        )
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self._ensure_storage_capacity()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            if self._storage_bytes() > self.MAX_DATABASE_BYTES:
                raise RepositoryError(
                    "Mnemosyne storage limit would be exceeded"
                )
            connection.commit()
        except sqlite3.OperationalError as error:
            connection.rollback()
            if "full" in str(error).casefold():
                raise RepositoryError(
                    "Mnemosyne storage limit would be exceeded"
                ) from error
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.transaction() as connection:
            existing_tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    """
                )
            }
            if existing_tables and "mnemosyne_meta" not in existing_tables:
                raise RepositoryError(
                    "refusing to initialize an unmarked existing SQLite database"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS mnemosyne_meta (
                    marker TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS schema_meta (
                    version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    persona TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS incarnations (
                    incarnation_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    model_provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    termination_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    timestamp TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    cwd TEXT,
                    repo TEXT,
                    branch TEXT,
                    correlation_id TEXT,
                    incarnation_id TEXT REFERENCES incarnations(incarnation_id)
                );
                CREATE INDEX IF NOT EXISTS events_time_idx
                    ON events(timestamp, ingested_at, event_id);
                CREATE INDEX IF NOT EXISTS events_agent_time_idx
                    ON events(agent_id, timestamp, ingested_at, event_id);
                CREATE TABLE IF NOT EXISTS beliefs (
                    belief_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    created_at TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                    status TEXT NOT NULL,
                    supersedes_belief_id TEXT REFERENCES beliefs(belief_id)
                );
                CREATE TABLE IF NOT EXISTS belief_evidence (
                    belief_id TEXT NOT NULL REFERENCES beliefs(belief_id),
                    event_id TEXT NOT NULL REFERENCES events(event_id),
                    weight REAL NOT NULL,
                    PRIMARY KEY (belief_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS commitments (
                    commitment_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    created_at TEXT NOT NULL,
                    commitment_type TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                    status TEXT NOT NULL,
                    source_belief_id TEXT REFERENCES beliefs(belief_id)
                );
                CREATE TABLE IF NOT EXISTS consequences (
                    consequence_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    created_at TEXT NOT NULL,
                    commitment_id TEXT NOT NULL REFERENCES commitments(commitment_id),
                    result_type TEXT NOT NULL,
                    description TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS consequence_evidence (
                    consequence_id TEXT NOT NULL REFERENCES consequences(consequence_id),
                    event_id TEXT NOT NULL REFERENCES events(event_id),
                    PRIMARY KEY (consequence_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    created_at TEXT NOT NULL,
                    old_belief_id TEXT NOT NULL REFERENCES beliefs(belief_id),
                    new_belief_id TEXT NOT NULL REFERENCES beliefs(belief_id),
                    reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revision_evidence (
                    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                    event_id TEXT NOT NULL REFERENCES events(event_id),
                    PRIMARY KEY (revision_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS relationships (
                    relationship_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    counterparty_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    UNIQUE(agent_id, counterparty_id)
                );
                CREATE TABLE IF NOT EXISTS relationship_events (
                    relationship_id TEXT NOT NULL REFERENCES relationships(relationship_id),
                    event_id TEXT NOT NULL REFERENCES events(event_id),
                    relation_type TEXT NOT NULL,
                    PRIMARY KEY (relationship_id, event_id, relation_type)
                );
                CREATE TABLE IF NOT EXISTS user_facts (
                    user_fact_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    counterparty_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    category TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                    status TEXT NOT NULL,
                    source_event_id TEXT NOT NULL REFERENCES events(event_id),
                    provenance_key TEXT,
                    supersedes_user_fact_id TEXT REFERENCES user_facts(user_fact_id)
                );
                CREATE TABLE IF NOT EXISTS context_builds (
                    context_build_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    run_id TEXT REFERENCES experiment_runs(run_id),
                    mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    query TEXT NOT NULL,
                    token_budget INTEGER NOT NULL,
                    selected_record_ids_json TEXT NOT NULL,
                    selected_fact_keys_json TEXT NOT NULL,
                    rendered_context_hash TEXT NOT NULL,
                    rendered_context TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiment_runs (
                    run_id TEXT PRIMARY KEY,
                    researcher_agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    scenario_id TEXT NOT NULL,
                    scenario_hash TEXT NOT NULL,
                    scenario_json TEXT NOT NULL,
                    model_config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiment_run_conditions (
                    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    mode TEXT NOT NULL,
                    PRIMARY KEY (run_id, agent_id),
                    UNIQUE (run_id, mode)
                );
                CREATE TABLE IF NOT EXISTS evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
                    scenario_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    mode TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    scores_json TEXT NOT NULL,
                    model_config_json TEXT NOT NULL,
                    context_build_id TEXT NOT NULL REFERENCES context_builds(context_build_id),
                    created_at TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS events_no_update
                BEFORE UPDATE ON events
                BEGIN
                    SELECT RAISE(ABORT, 'events are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS events_no_delete
                BEFORE DELETE ON events
                BEGIN
                    SELECT RAISE(ABORT, 'events are immutable');
                END;
                """
            )
            marker = connection.execute(
                "SELECT marker FROM mnemosyne_meta"
            ).fetchone()
            if marker is None:
                connection.execute(
                    "INSERT INTO mnemosyne_meta(marker) VALUES (?)",
                    (self.DATABASE_MARKER,),
                )
            elif marker["marker"] != self.DATABASE_MARKER:
                raise RepositoryError("invalid Mnemosyne database marker")
            row = connection.execute("SELECT version FROM schema_meta").fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO schema_meta(version) VALUES (?)",
                    (self.SCHEMA_VERSION,),
                )
            elif row["version"] != self.SCHEMA_VERSION:
                raise RepositoryError(
                    f"unsupported schema version {row['version']}; "
                    f"expected {self.SCHEMA_VERSION}"
                )

    def create_or_get_agent(
        self,
        name: str = "mnemosyne-observer",
        persona: str = "bounded persistent observer",
    ) -> AgentIdentity:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM agents WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO agents(agent_id, name, persona, created_at, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("agent"),
                        name,
                        persona,
                        utc_now(),
                        LifecycleState.CREATED,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM agents WHERE name = ?", (name,)
                ).fetchone()
        return self._agent(row)

    def get_agent(self, agent_id: str) -> AgentIdentity:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        if row is None:
            raise RepositoryError(f"unknown agent: {agent_id}")
        return self._agent(row)

    def set_agent_status(
        self, agent_id: str, status: LifecycleState
    ) -> AgentIdentity:
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE agents SET status = ? WHERE agent_id = ?",
                (status, agent_id),
            )
            if cursor.rowcount != 1:
                raise RepositoryError(f"unknown agent: {agent_id}")
        return self.get_agent(agent_id)

    def start_incarnation(
        self,
        agent_id: str,
        model_provider: str = "deterministic",
        model_name: str = "mnemosyne-rules-v1",
    ) -> Incarnation:
        incarnation_id = new_id("incarnation")
        with self.transaction() as connection:
            active = connection.execute(
                """
                SELECT incarnation_id FROM incarnations
                WHERE agent_id = ? AND ended_at IS NULL
                """,
                (agent_id,),
            ).fetchone()
            if active is not None:
                raise RepositoryError(
                    f"agent already has active incarnation: {active['incarnation_id']}"
                )
            connection.execute(
                """
                INSERT INTO incarnations(
                    incarnation_id, agent_id, model_provider, model_name, started_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    incarnation_id,
                    agent_id,
                    model_provider,
                    model_name,
                    utc_now(),
                ),
            )
        return self.get_incarnation(incarnation_id)

    def get_incarnation(self, incarnation_id: str) -> Incarnation:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM incarnations WHERE incarnation_id = ?",
                (incarnation_id,),
            ).fetchone()
        if row is None:
            raise RepositoryError(f"unknown incarnation: {incarnation_id}")
        return self._incarnation(row)

    def get_active_incarnation(self, agent_id: str) -> Incarnation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM incarnations
                WHERE agent_id = ? AND ended_at IS NULL
                ORDER BY started_at DESC LIMIT 1
                """,
                (agent_id,),
            ).fetchone()
        return self._incarnation(row) if row else None

    def list_incarnations(self, agent_id: str) -> list[Incarnation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM incarnations WHERE agent_id = ?
                ORDER BY started_at, incarnation_id
                """,
                (agent_id,),
            ).fetchall()
        return [self._incarnation(row) for row in rows]

    def end_incarnation(
        self, incarnation_id: str, termination_reason: str = "sleep"
    ) -> Incarnation:
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE incarnations
                SET ended_at = ?, termination_reason = ?
                WHERE incarnation_id = ? AND ended_at IS NULL
                """,
                (utc_now(), termination_reason, incarnation_id),
            )
            if cursor.rowcount != 1:
                raise RepositoryError(
                    f"incarnation is unknown or already ended: {incarnation_id}"
                )
        return self.get_incarnation(incarnation_id)

    def append_event(
        self,
        *,
        source: str,
        event_type: str,
        payload: dict[str, Any],
        timestamp: str | None = None,
        cwd: str | None = None,
        repo: str | None = None,
        branch: str | None = None,
        correlation_id: str | None = None,
        incarnation_id: str | None = None,
        agent_id: str | None = None,
        event_id: str | None = None,
    ) -> Event:
        self._ensure_storage_capacity()
        try:
            payload = sanitize_event_payload(source, event_type, payload)
            event_id = (
                sanitize_metadata_text(event_id) if event_id else None
            )
            timestamp = (
                sanitize_metadata_text(timestamp) if timestamp else None
            )
            cwd = sanitize_metadata_text(cwd) if cwd else None
            repo = sanitize_metadata_text(repo) if repo else None
            branch = sanitize_metadata_text(branch) if branch else None
            correlation_id = (
                sanitize_metadata_text(correlation_id)
                if correlation_id
                else None
            )
        except EventPolicyError as error:
            raise RepositoryError(str(error)) from error
        except ValueError as error:
            raise RepositoryError(str(error)) from error
        event_id = event_id or new_id("event")
        with self.transaction() as connection:
            if incarnation_id:
                incarnation = connection.execute(
                    """
                    SELECT agent_id FROM incarnations WHERE incarnation_id = ?
                    """,
                    (incarnation_id,),
                ).fetchone()
                if incarnation is None:
                    raise RepositoryError(
                        f"unknown incarnation: {incarnation_id}"
                    )
                if agent_id and agent_id != incarnation["agent_id"]:
                    raise RepositoryError(
                        "event agent does not own the incarnation"
                    )
                agent_id = incarnation["agent_id"]
            if agent_id is None:
                raise RepositoryError("events require agent ownership")
            existing = connection.execute(
                "SELECT * FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing is not None:
                candidate = (
                    agent_id,
                    source,
                    event_type,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    cwd,
                    repo,
                    branch,
                    correlation_id,
                    incarnation_id,
                )
                stored = (
                    existing["agent_id"],
                    existing["source"],
                    existing["event_type"],
                    existing["payload_json"],
                    existing["cwd"],
                    existing["repo"],
                    existing["branch"],
                    existing["correlation_id"],
                    existing["incarnation_id"],
                )
                if candidate != stored:
                    raise RepositoryError(
                        f"duplicate event ID has different content: {event_id}"
                    )
                return self._event(existing)
            connection.execute(
                """
                INSERT INTO events(
                    event_id, agent_id, timestamp, ingested_at, source, event_type,
                    payload_json, cwd, repo, branch, correlation_id, incarnation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    agent_id,
                    timestamp or utc_now(),
                    utc_now(),
                    source,
                    event_type,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    cwd,
                    repo,
                    branch,
                    correlation_id,
                    incarnation_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return self._event(row)

    def get_events(
        self,
        *,
        agent_id: str | None = None,
        limit: int | None = None,
        since: str | None = None,
    ) -> list[Event]:
        query = "SELECT * FROM events"
        parameters: list[Any] = []
        clauses = []
        if agent_id:
            clauses.append("agent_id = ?")
            parameters.append(agent_id)
        if since:
            clauses.append("timestamp >= ?")
            parameters.append(since)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp, ingested_at, event_id"
        if limit:
            inner_clauses = []
            inner_parameters: list[Any] = []
            if agent_id:
                inner_clauses.append("agent_id = ?")
                inner_parameters.append(agent_id)
            if since:
                inner_clauses.append("timestamp >= ?")
                inner_parameters.append(since)
            query = (
                "SELECT * FROM (SELECT * FROM events"
                + (
                    " WHERE " + " AND ".join(inner_clauses)
                    if inner_clauses
                    else ""
                )
                + " ORDER BY timestamp DESC, ingested_at DESC, event_id DESC LIMIT ?) "
                "ORDER BY timestamp, ingested_at, event_id"
            )
            parameters = inner_parameters + [limit]
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._event(row) for row in rows]

    def create_belief(
        self,
        *,
        agent_id: str,
        subject: str,
        predicate: str,
        object: str,
        confidence: float,
        evidence_event_ids: Sequence[str],
        supersedes_belief_id: str | None = None,
        belief_id: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> Belief:
        if not evidence_event_ids:
            raise RepositoryError("beliefs require at least one evidence event")
        if not 0 <= confidence <= 1:
            raise RepositoryError("belief confidence must be between 0 and 1")
        belief_id = belief_id or new_id("belief")

        def write(conn: sqlite3.Connection) -> None:
            self._validate_event_ownership(
                conn, agent_id, evidence_event_ids
            )
            conn.execute(
                """
                INSERT INTO beliefs(
                    belief_id, agent_id, created_at, subject, predicate, object,
                    confidence, status, supersedes_belief_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    belief_id,
                    agent_id,
                    utc_now(),
                    subject,
                    predicate,
                    object,
                    confidence,
                    supersedes_belief_id,
                ),
            )
            conn.executemany(
                """
                INSERT INTO belief_evidence(belief_id, event_id, weight)
                VALUES (?, ?, ?)
                """,
                [(belief_id, event_id, 1.0) for event_id in evidence_event_ids],
            )

        if connection is not None:
            write(connection)
            row = connection.execute(
                "SELECT * FROM beliefs WHERE belief_id = ?", (belief_id,)
            ).fetchone()
            evidence = connection.execute(
                """
                SELECT event_id FROM belief_evidence
                WHERE belief_id = ? ORDER BY event_id
                """,
                (belief_id,),
            ).fetchall()
            return self._belief(row, evidence)
        else:
            with self.transaction() as conn:
                write(conn)
        return self.get_belief(belief_id)

    def get_belief(self, belief_id: str) -> Belief:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM beliefs WHERE belief_id = ?", (belief_id,)
            ).fetchone()
            evidence = connection.execute(
                """
                SELECT event_id FROM belief_evidence
                WHERE belief_id = ? ORDER BY event_id
                """,
                (belief_id,),
            ).fetchall()
        if row is None:
            raise RepositoryError(f"unknown belief: {belief_id}")
        return self._belief(row, evidence)

    def get_active_beliefs(self, agent_id: str) -> list[Belief]:
        return self._get_beliefs(agent_id, active_only=True)

    def get_belief_history(
        self, agent_id: str, limit: int | None = None
    ) -> list[Belief]:
        return self._get_beliefs(agent_id, active_only=False, limit=limit)

    def _get_beliefs(
        self,
        agent_id: str,
        *,
        active_only: bool,
        limit: int | None = None,
    ) -> list[Belief]:
        query = "SELECT * FROM beliefs WHERE agent_id = ?"
        if active_only:
            query += " AND status = 'active'"
        parameters: list[Any] = [agent_id]
        if limit:
            query = (
                "SELECT * FROM ("
                + query
                + " ORDER BY created_at DESC, belief_id DESC LIMIT ?) "
                "ORDER BY created_at, belief_id"
            )
            parameters.append(limit)
        else:
            query += " ORDER BY created_at, belief_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
            result = []
            for row in rows:
                evidence = connection.execute(
                    """
                    SELECT event_id FROM belief_evidence
                    WHERE belief_id = ? ORDER BY event_id
                    """,
                    (row["belief_id"],),
                ).fetchall()
                result.append(self._belief(row, evidence))
        return result

    def supersede_belief(
        self,
        *,
        old_belief_id: str,
        new_object: str,
        confidence: float,
        evidence_event_ids: Sequence[str],
        reason: str,
    ) -> tuple[Belief, Revision]:
        new_belief_id = new_id("belief")
        revision_id = new_id("revision")
        with self.transaction() as connection:
            old = connection.execute(
                "SELECT * FROM beliefs WHERE belief_id = ?",
                (old_belief_id,),
            ).fetchone()
            if old is None or old["status"] != "active":
                raise RepositoryError(
                    f"belief is unknown or not active: {old_belief_id}"
                )
            self.create_belief(
                agent_id=old["agent_id"],
                subject=old["subject"],
                predicate=old["predicate"],
                object=new_object,
                confidence=confidence,
                evidence_event_ids=evidence_event_ids,
                supersedes_belief_id=old_belief_id,
                belief_id=new_belief_id,
                connection=connection,
            )
            connection.execute(
                """
                UPDATE beliefs SET status = 'superseded'
                WHERE belief_id = ? AND status = 'active'
                """,
                (old_belief_id,),
            )
            connection.execute(
                """
                INSERT INTO revisions(
                    revision_id, agent_id, created_at, old_belief_id,
                    new_belief_id, reason
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    old["agent_id"],
                    utc_now(),
                    old_belief_id,
                    new_belief_id,
                    reason,
                ),
            )
            connection.executemany(
                """
                INSERT INTO revision_evidence(revision_id, event_id)
                VALUES (?, ?)
                """,
                [(revision_id, event_id) for event_id in evidence_event_ids],
            )
        return self.get_belief(new_belief_id), self.get_revision(revision_id)

    def create_commitment(
        self,
        *,
        agent_id: str,
        incarnation_id: str,
        commitment_type: str,
        claim: str,
        confidence: float,
        source_belief_id: str | None,
    ) -> Commitment:
        commitment_id = new_id("commitment")
        with self.transaction() as connection:
            incarnation = connection.execute(
                """
                SELECT agent_id FROM incarnations WHERE incarnation_id = ?
                """,
                (incarnation_id,),
            ).fetchone()
            if incarnation is None or incarnation["agent_id"] != agent_id:
                raise RepositoryError(
                    "commitment incarnation belongs to another agent"
                )
            if source_belief_id:
                belief = connection.execute(
                    "SELECT agent_id FROM beliefs WHERE belief_id = ?",
                    (source_belief_id,),
                ).fetchone()
                if belief is None or belief["agent_id"] != agent_id:
                    raise RepositoryError(
                        "commitment belief belongs to another agent"
                    )
            connection.execute(
                """
                INSERT INTO commitments(
                    commitment_id, agent_id, incarnation_id, created_at,
                    commitment_type, claim, confidence, status, source_belief_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    commitment_id,
                    agent_id,
                    incarnation_id,
                    utc_now(),
                    commitment_type,
                    claim,
                    confidence,
                    source_belief_id,
                ),
            )
        return self.get_commitment(commitment_id)

    def get_commitment(self, commitment_id: str) -> Commitment:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM commitments WHERE commitment_id = ?",
                (commitment_id,),
            ).fetchone()
        if row is None:
            raise RepositoryError(f"unknown commitment: {commitment_id}")
        return self._commitment(row)

    def get_open_commitments(self, agent_id: str) -> list[Commitment]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM commitments
                WHERE agent_id = ? AND status = 'open'
                ORDER BY created_at, commitment_id
                """,
                (agent_id,),
            ).fetchall()
        return [self._commitment(row) for row in rows]

    def get_commitments(
        self, agent_id: str, limit: int | None = None
    ) -> list[Commitment]:
        query = "SELECT * FROM commitments WHERE agent_id = ?"
        parameters: list[Any] = [agent_id]
        if limit:
            query = (
                "SELECT * FROM ("
                + query
                + " ORDER BY created_at DESC, commitment_id DESC LIMIT ?) "
                "ORDER BY created_at, commitment_id"
            )
            parameters.append(limit)
        else:
            query += " ORDER BY created_at, commitment_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._commitment(row) for row in rows]

    def update_commitment_status(
        self, commitment_id: str, status: str
    ) -> Commitment:
        allowed = {
            "open",
            "fulfilled",
            "contradicted",
            "revised",
            "withdrawn",
            "expired",
        }
        if status not in allowed:
            raise RepositoryError(f"invalid commitment status: {status}")
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE commitments SET status = ? WHERE commitment_id = ?",
                (status, commitment_id),
            )
            if cursor.rowcount != 1:
                raise RepositoryError(f"unknown commitment: {commitment_id}")
        return self.get_commitment(commitment_id)

    def create_consequence(
        self,
        *,
        agent_id: str,
        commitment_id: str,
        result_type: str,
        description: str,
        evidence_event_ids: Sequence[str],
    ) -> Consequence:
        consequence_id = new_id("consequence")
        with self.transaction() as connection:
            commitment = connection.execute(
                """
                SELECT agent_id FROM commitments WHERE commitment_id = ?
                """,
                (commitment_id,),
            ).fetchone()
            if commitment is None or commitment["agent_id"] != agent_id:
                raise RepositoryError(
                    "consequence commitment belongs to another agent"
                )
            self._validate_event_ownership(
                connection, agent_id, evidence_event_ids
            )
            connection.execute(
                """
                INSERT INTO consequences(
                    consequence_id, agent_id, created_at, commitment_id,
                    result_type, description
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    consequence_id,
                    agent_id,
                    utc_now(),
                    commitment_id,
                    result_type,
                    description,
                ),
            )
            connection.executemany(
                """
                INSERT INTO consequence_evidence(consequence_id, event_id)
                VALUES (?, ?)
                """,
                [(consequence_id, event_id) for event_id in evidence_event_ids],
            )
        return self.get_consequence(consequence_id)

    def get_consequence(self, consequence_id: str) -> Consequence:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM consequences WHERE consequence_id = ?",
                (consequence_id,),
            ).fetchone()
            evidence = connection.execute(
                """
                SELECT event_id FROM consequence_evidence
                WHERE consequence_id = ? ORDER BY event_id
                """,
                (consequence_id,),
            ).fetchall()
        if row is None:
            raise RepositoryError(f"unknown consequence: {consequence_id}")
        return self._consequence(row, evidence)

    def get_consequences(
        self, agent_id: str, limit: int | None = None
    ) -> list[Consequence]:
        query = "SELECT * FROM consequences WHERE agent_id = ?"
        parameters: list[Any] = [agent_id]
        if limit:
            query = (
                "SELECT * FROM ("
                + query
                + " ORDER BY created_at DESC, consequence_id DESC LIMIT ?) "
                "ORDER BY created_at, consequence_id"
            )
            parameters.append(limit)
        else:
            query += " ORDER BY created_at, consequence_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
            result = []
            for row in rows:
                evidence = connection.execute(
                    """
                    SELECT event_id FROM consequence_evidence
                    WHERE consequence_id = ? ORDER BY event_id
                    """,
                    (row["consequence_id"],),
                ).fetchall()
                result.append(self._consequence(row, evidence))
        return result

    def get_revision(self, revision_id: str) -> Revision:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM revisions WHERE revision_id = ?", (revision_id,)
            ).fetchone()
            evidence = connection.execute(
                """
                SELECT event_id FROM revision_evidence
                WHERE revision_id = ? ORDER BY event_id
                """,
                (revision_id,),
            ).fetchall()
        if row is None:
            raise RepositoryError(f"unknown revision: {revision_id}")
        return self._revision(row, evidence)

    def create_revision(
        self,
        *,
        agent_id: str,
        old_belief_id: str,
        new_belief_id: str,
        reason: str,
        evidence_event_ids: Sequence[str],
    ) -> Revision:
        revision_id = new_id("revision")
        with self.transaction() as connection:
            belief_rows = connection.execute(
                """
                SELECT belief_id, agent_id FROM beliefs
                WHERE belief_id IN (?, ?)
                """,
                (old_belief_id, new_belief_id),
            ).fetchall()
            if len(belief_rows) != 2 or any(
                row["agent_id"] != agent_id for row in belief_rows
            ):
                raise RepositoryError(
                    "revision beliefs must belong to the same agent"
                )
            self._validate_event_ownership(
                connection, agent_id, evidence_event_ids
            )
            connection.execute(
                """
                INSERT INTO revisions(
                    revision_id, agent_id, created_at, old_belief_id,
                    new_belief_id, reason
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    agent_id,
                    utc_now(),
                    old_belief_id,
                    new_belief_id,
                    reason,
                ),
            )
            connection.executemany(
                """
                INSERT INTO revision_evidence(revision_id, event_id)
                VALUES (?, ?)
                """,
                [(revision_id, event_id) for event_id in evidence_event_ids],
            )
        return self.get_revision(revision_id)

    def get_revisions(
        self, agent_id: str, limit: int | None = None
    ) -> list[Revision]:
        query = "SELECT * FROM revisions WHERE agent_id = ?"
        parameters: list[Any] = [agent_id]
        if limit:
            query = (
                "SELECT * FROM ("
                + query
                + " ORDER BY created_at DESC, revision_id DESC LIMIT ?) "
                "ORDER BY created_at, revision_id"
            )
            parameters.append(limit)
        else:
            query += " ORDER BY created_at, revision_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
            result = []
            for row in rows:
                evidence = connection.execute(
                    """
                    SELECT event_id FROM revision_evidence
                    WHERE revision_id = ? ORDER BY event_id
                    """,
                    (row["revision_id"],),
                ).fetchall()
                result.append(self._revision(row, evidence))
        return result

    def create_relationship(
        self, *, agent_id: str, counterparty_id: str, status: str = "active"
    ) -> Relationship:
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM relationships
                WHERE agent_id = ? AND counterparty_id = ?
                """,
                (agent_id, counterparty_id),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO relationships(
                        relationship_id, agent_id, counterparty_id, created_at, status
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("relationship"),
                        agent_id,
                        counterparty_id,
                        utc_now(),
                        status,
                    ),
                )
                row = connection.execute(
                    """
                    SELECT * FROM relationships
                    WHERE agent_id = ? AND counterparty_id = ?
                    """,
                    (agent_id, counterparty_id),
                ).fetchone()
        return self._relationship(row)

    def add_relationship_event(
        self, relationship_id: str, event_id: str, relation_type: str
    ) -> None:
        with self.transaction() as connection:
            ownership = connection.execute(
                """
                SELECT r.agent_id AS relationship_agent,
                       e.agent_id AS event_agent
                FROM relationships r CROSS JOIN events e
                WHERE r.relationship_id = ? AND e.event_id = ?
                """,
                (relationship_id, event_id),
            ).fetchone()
            if (
                ownership is None
                or ownership["relationship_agent"] != ownership["event_agent"]
            ):
                raise RepositoryError(
                    "relationship and event must belong to the same agent"
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO relationship_events(
                    relationship_id, event_id, relation_type
                ) VALUES (?, ?, ?)
                """,
                (relationship_id, event_id, relation_type),
            )

    def get_relationship_history(
        self, agent_id: str, counterparty_id: str
    ) -> list[tuple[Relationship, Event, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT r.*, e.*, re.relation_type
                FROM relationships r
                JOIN relationship_events re
                  ON re.relationship_id = r.relationship_id
                JOIN events e ON e.event_id = re.event_id
                WHERE r.agent_id = ? AND r.counterparty_id = ?
                ORDER BY e.timestamp, e.ingested_at, e.event_id
                """,
                (agent_id, counterparty_id),
            ).fetchall()
        return [
            (self._relationship(row), self._event(row), row["relation_type"])
            for row in rows
        ]

    def get_relationships(self, agent_id: str) -> list[Relationship]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM relationships WHERE agent_id = ?
                ORDER BY created_at, relationship_id
                """,
                (agent_id,),
            ).fetchall()
        return [self._relationship(row) for row in rows]

    def create_user_fact(
        self,
        *,
        agent_id: str,
        counterparty_id: str,
        category: str,
        origin: str,
        fact: str,
        provenance_key: str,
        confidence: float,
        source_event_id: str,
        supersedes_user_fact_id: str | None = None,
    ) -> UserFact:
        fact = fact.strip()
        if category != "preference" or not is_allowed_preference(fact):
            raise RepositoryError(
                "only allowlisted interaction/workflow preferences may be stored"
            )
        if origin not in {"user_statement", "operator"}:
            raise RepositoryError("invalid preference origin")
        if not re.fullmatch(r"[0-9a-f]{64}", provenance_key):
            raise RepositoryError("preference provenance key is invalid")
        if counterparty_id != "user":
            raise RepositoryError(
                "Experiment 1 preferences require the user counterparty"
            )
        if not 0 <= confidence <= 1:
            raise RepositoryError("user fact confidence must be between 0 and 1")
        user_fact_id = new_id("user-fact")
        with self.transaction() as connection:
            self._validate_event_ownership(
                connection, agent_id, [source_event_id]
            )
            source = connection.execute(
                """
                SELECT source, event_type, payload_json
                FROM events WHERE event_id = ?
                """,
                (source_event_id,),
            ).fetchone()
            source_payload = json.loads(source["payload_json"])
            expected_event_type = (
                "user_preference_statement"
                if origin == "user_statement"
                else "operator_preference"
            )
            if (
                source["source"] != "observer_interaction"
                or source["event_type"] != expected_event_type
                or source_payload.get("preference_digest")
                != hmac.new(
                    bytes.fromhex(provenance_key),
                    fact.encode(),
                    hashlib.sha256,
                ).hexdigest()
            ):
                raise RepositoryError(
                    "preference provenance digest and origin do not match"
                )
            if fact.casefold() in source["payload_json"].casefold():
                raise RepositoryError(
                    "user fact text must be stored once, not copied into its source event"
                )
            if supersedes_user_fact_id:
                previous = connection.execute(
                    """
                    SELECT counterparty_id, category FROM user_facts
                    WHERE user_fact_id = ? AND agent_id = ? AND status = 'active'
                    """,
                    (supersedes_user_fact_id, agent_id),
                ).fetchone()
                if (
                    previous is None
                    or previous["counterparty_id"] != counterparty_id
                    or previous["category"] != category
                ):
                    raise RepositoryError(
                        "superseded preference must match agent, counterparty, and category"
                    )
                cursor = connection.execute(
                    """
                    UPDATE user_facts SET status = 'superseded'
                    WHERE user_fact_id = ? AND agent_id = ? AND status = 'active'
                    """,
                    (supersedes_user_fact_id, agent_id),
                )
                if cursor.rowcount != 1:
                    raise RepositoryError(
                        "superseded user fact is unknown or inactive: "
                        f"{supersedes_user_fact_id}"
                    )
            connection.execute(
                """
                INSERT INTO user_facts(
                    user_fact_id, agent_id, counterparty_id, created_at,
                    category, origin, fact, confidence, status, source_event_id,
                    provenance_key, supersedes_user_fact_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    user_fact_id,
                    agent_id,
                    counterparty_id,
                    utc_now(),
                    category,
                    origin,
                    fact.strip(),
                    confidence,
                    source_event_id,
                    provenance_key,
                    supersedes_user_fact_id,
                ),
            )
        return self.get_user_fact(user_fact_id)

    def get_user_fact(self, user_fact_id: str) -> UserFact:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_facts WHERE user_fact_id = ?",
                (user_fact_id,),
            ).fetchone()
        if row is None:
            raise RepositoryError(f"unknown user fact: {user_fact_id}")
        return self._user_fact(row)

    def get_active_user_facts(
        self,
        agent_id: str,
        counterparty_id: str = "user",
        limit: int | None = None,
    ) -> list[UserFact]:
        base_query = """
            SELECT * FROM user_facts
            WHERE agent_id = ? AND counterparty_id = ? AND status = 'active'
        """
        query = base_query
        parameters: list[Any] = [agent_id, counterparty_id]
        if limit:
            query = (
                "SELECT * FROM ("
                + base_query
                + " ORDER BY created_at DESC, user_fact_id DESC LIMIT ?) "
                "ORDER BY created_at, user_fact_id"
            )
            parameters.append(limit)
        else:
            query += " ORDER BY created_at, user_fact_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._user_fact(row) for row in rows]

    def get_user_fact_history(
        self, agent_id: str, counterparty_id: str = "user"
    ) -> list[UserFact]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM user_facts
                WHERE agent_id = ? AND counterparty_id = ?
                ORDER BY created_at, user_fact_id
                """,
                (agent_id, counterparty_id),
            ).fetchall()
        return [self._user_fact(row) for row in rows]

    def delete_user_fact(self, user_fact_id: str, *, agent_id: str) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT fact FROM user_facts
                WHERE user_fact_id = ? AND agent_id = ? AND status != 'deleted'
                """,
                (user_fact_id, agent_id),
            ).fetchone()
            if row is None:
                raise RepositoryError(f"unknown user fact: {user_fact_id}")
            candidates = connection.execute(
                """
                SELECT context_build_id, rendered_context,
                       selected_fact_keys_json, selected_record_ids_json
                FROM context_builds
                WHERE agent_id = ?
                """,
                (agent_id,),
            ).fetchall()
            contexts = [
                context
                for context in candidates
                if user_fact_id
                in json.loads(context["selected_record_ids_json"])
            ]
            for context in contexts:
                rendered = context["rendered_context"].replace(
                    row["fact"], "[DELETED]"
                )
                fact_keys = json.loads(context["selected_fact_keys_json"])
                fact_keys = [
                    "user-fact:[DELETED]"
                    if key.startswith("user-fact:")
                    else key
                    for key in fact_keys
                ]
                connection.execute(
                    """
                    UPDATE context_builds
                    SET rendered_context = ?, rendered_context_hash = ?,
                        selected_fact_keys_json = ?
                    WHERE context_build_id = ?
                    """,
                    (
                        rendered,
                        hashlib.sha256(rendered.encode()).hexdigest(),
                        json.dumps(fact_keys),
                        context["context_build_id"],
                    ),
                )
            cursor = connection.execute(
                """
                UPDATE user_facts
                SET fact = '[DELETED]', status = 'deleted', provenance_key = NULL
                WHERE user_fact_id = ? AND agent_id = ? AND status != 'deleted'
                """,
                (user_fact_id, agent_id),
            )
            if cursor.rowcount != 1:
                raise RepositoryError(f"unknown user fact: {user_fact_id}")
        self.compact()

    def save_context_build(self, context: ContextBuild) -> ContextBuild:
        self._ensure_storage_capacity()
        query = sanitize_interaction_text(context.query)
        rendered = sanitize_interaction_text(context.rendered_context)
        context = replace(
            context,
            query=query,
            rendered_context=rendered,
            rendered_context_hash=hashlib.sha256(rendered.encode()).hexdigest(),
        )
        with self.transaction() as connection:
            agent = connection.execute(
                "SELECT 1 FROM agents WHERE agent_id = ?",
                (context.agent_id,),
            ).fetchone()
            if agent is None:
                raise RepositoryError(
                    f"unknown context agent: {context.agent_id}"
                )
            if context.run_id:
                condition = connection.execute(
                    """
                    SELECT 1 FROM experiment_run_conditions
                    WHERE run_id = ? AND agent_id = ? AND mode = ?
                    """,
                    (context.run_id, context.agent_id, context.mode),
                ).fetchone()
                if condition is None:
                    raise RepositoryError(
                        "context agent and mode are not enrolled in the run"
                    )
            self._validate_selected_record_ownership(
                connection,
                context.agent_id,
                context.selected_record_ids,
            )
            from .context import ContextCompiler

            expected_rendered, expected_ids, expected_keys, expected_query = (
                ContextCompiler(self).render(
                    agent_id=context.agent_id,
                    mode=context.mode,
                    query=context.query,
                    token_budget=context.token_budget,
                )
            )
            if (
                context.query != expected_query
                or context.rendered_context != expected_rendered
                or context.selected_record_ids != expected_ids
                or context.selected_fact_keys != expected_keys
            ):
                raise RepositoryError(
                    "context content is not compiler-derived from owned records"
                )
            connection.execute(
                """
                INSERT INTO context_builds(
                    context_build_id, agent_id, run_id, mode, created_at, query,
                    token_budget, selected_record_ids_json,
                    selected_fact_keys_json,
                    rendered_context_hash, rendered_context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    context.context_build_id,
                    context.agent_id,
                    context.run_id,
                    context.mode,
                    context.created_at,
                    context.query,
                    context.token_budget,
                    json.dumps(context.selected_record_ids),
                    json.dumps(context.selected_fact_keys),
                    context.rendered_context_hash,
                    context.rendered_context,
                ),
            )
        return context

    def get_context_build(self, context_build_id: str) -> ContextBuild:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM context_builds WHERE context_build_id = ?
                """,
                (context_build_id,),
            ).fetchone()
        if row is None:
            raise RepositoryError(f"unknown context build: {context_build_id}")
        return self._context_build(row)

    def save_evaluation(self, evaluation: Evaluation) -> Evaluation:
        self._ensure_storage_capacity()
        sanitized_model = self._sanitize_model_config(
            evaluation.model_config
        )
        sanitized_scores = self._validate_scores(evaluation.scores)
        evaluation = replace(
            evaluation,
            question=sanitize_interaction_text(evaluation.question),
            answer=sanitize_interaction_text(evaluation.answer),
            scores=sanitized_scores,
            model_config=sanitized_model,
        )
        with self.transaction() as connection:
            ownership = connection.execute(
                """
                SELECT c.agent_id, c.mode,
                       c.run_id,
                       r.scenario_id AS run_scenario_id,
                       r.model_config_json AS run_model_config
                FROM context_builds c
                JOIN experiment_runs r ON r.run_id = ?
                WHERE c.context_build_id = ?
                """,
                (evaluation.run_id, evaluation.context_build_id),
            ).fetchone()
            if (
                ownership is None
                or ownership["run_id"] != evaluation.run_id
                or ownership["agent_id"] != evaluation.agent_id
                or ownership["mode"] != evaluation.mode
                or ownership["run_scenario_id"] != evaluation.scenario_id
                or json.loads(ownership["run_model_config"])
                != evaluation.model_config
            ):
                raise RepositoryError(
                    "evaluation run, agent, mode, and context ownership do not match"
                )
            connection.execute(
                """
                INSERT INTO evaluations(
                    evaluation_id, run_id, scenario_id, agent_id, mode, question,
                    answer, scores_json, model_config_json, context_build_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation.evaluation_id,
                    evaluation.run_id,
                    evaluation.scenario_id,
                    evaluation.agent_id,
                    evaluation.mode,
                    evaluation.question,
                    evaluation.answer,
                    json.dumps(evaluation.scores, sort_keys=True),
                    json.dumps(evaluation.model_config, sort_keys=True),
                    evaluation.context_build_id,
                    evaluation.created_at,
                ),
            )
        return evaluation

    def create_experiment_run(
        self,
        *,
        researcher_agent_id: str,
        scenario_id: str,
        scenario: dict[str, Any],
        model_config: dict[str, Any],
    ) -> ExperimentRun:
        self._ensure_storage_capacity()
        from .experiment import ExperimentRunner

        ExperimentRunner.validate(scenario)
        scenario = ExperimentRunner.sanitize(scenario)
        model_config = self._sanitize_model_config(model_config)
        try:
            scenario_id = sanitize_metadata_text(scenario_id)
        except ValueError as error:
            raise RepositoryError(str(error)) from error
        serialized = json.dumps(scenario, sort_keys=True, separators=(",", ":"))
        run = ExperimentRun(
            run_id=new_id("run"),
            researcher_agent_id=researcher_agent_id,
            scenario_id=scenario_id,
            scenario_hash=hashlib.sha256(serialized.encode()).hexdigest(),
            scenario=scenario,
            model_config=model_config,
            created_at=utc_now(),
        )
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO experiment_runs(
                    run_id, researcher_agent_id, scenario_id, scenario_hash, scenario_json,
                    model_config_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.researcher_agent_id,
                    run.scenario_id,
                    run.scenario_hash,
                    serialized,
                    json.dumps(run.model_config, sort_keys=True),
                    run.created_at,
                ),
            )
        return run

    def enroll_run_condition(
        self, *, run_id: str, agent_id: str, mode: Mode
    ) -> RunCondition:
        with self.transaction() as connection:
            run = connection.execute(
                "SELECT 1 FROM experiment_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            agent = connection.execute(
                "SELECT 1 FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if run is None or agent is None:
                raise RepositoryError("run and condition agent must exist")
            connection.execute(
                """
                INSERT INTO experiment_run_conditions(run_id, agent_id, mode)
                VALUES (?, ?, ?)
                """,
                (run_id, agent_id, mode),
            )
        return RunCondition(run_id, agent_id, mode)

    def get_run_conditions(
        self, run_id: str
    ) -> list[RunCondition]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM experiment_run_conditions
                WHERE run_id = ? ORDER BY mode
                """,
                (run_id,),
            ).fetchall()
        return [
            RunCondition(row["run_id"], row["agent_id"], Mode(row["mode"]))
            for row in rows
        ]

    def get_experiment_runs(self) -> list[ExperimentRun]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM experiment_runs ORDER BY created_at, run_id
                """
            ).fetchall()
        return [
            ExperimentRun(
                row["run_id"],
                row["researcher_agent_id"],
                row["scenario_id"],
                row["scenario_hash"],
                json.loads(row["scenario_json"]),
                json.loads(row["model_config_json"]),
                row["created_at"],
            )
            for row in rows
        ]

    def get_context_builds(
        self,
        agent_id: str | None = None,
        run_id: str | None = None,
    ) -> list[ContextBuild]:
        parameters: list[str] = []
        if run_id:
            query = "SELECT * FROM context_builds WHERE run_id = ?"
            parameters.append(run_id)
            if agent_id:
                query += " AND agent_id = ?"
                parameters.append(agent_id)
            query += " ORDER BY created_at, context_build_id"
        else:
            query = "SELECT * FROM context_builds"
            if agent_id:
                query += " WHERE agent_id = ?"
                parameters.append(agent_id)
            query += " ORDER BY created_at, context_build_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._context_build(row) for row in rows]

    def get_evaluations(
        self,
        scenario_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
    ) -> list[Evaluation]:
        clauses = []
        parameters = []
        if scenario_id:
            clauses.append("scenario_id = ?")
            parameters.append(scenario_id)
        if agent_id:
            clauses.append("agent_id = ?")
            parameters.append(agent_id)
        if run_id:
            clauses.append("run_id = ?")
            parameters.append(run_id)
        query = "SELECT * FROM evaluations"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, evaluation_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._evaluation(row) for row in rows]

    def purge(self) -> None:
        if not self.path.exists():
            return
        with self._connect() as connection:
            marker = connection.execute(
                "SELECT marker FROM mnemosyne_meta"
            ).fetchone()
            if marker is None or marker["marker"] != self.DATABASE_MARKER:
                raise RepositoryError("refusing to purge an unmarked database")
            active = connection.execute(
                """
                SELECT COUNT(*) AS count FROM agents
                WHERE status NOT IN ('ASLEEP', 'CREATED')
                """
            ).fetchone()
            if active["count"]:
                raise RepositoryError(
                    "all observers must be asleep before purge"
                )
            connection.execute("DROP TRIGGER IF EXISTS events_no_update")
            connection.execute("DROP TRIGGER IF EXISTS events_no_delete")
            for table in (
                "evaluations",
                "experiment_run_conditions",
                "experiment_runs",
                "context_builds",
                "user_facts",
                "relationship_events",
                "relationships",
                "revision_evidence",
                "revisions",
                "consequence_evidence",
                "consequences",
                "commitments",
                "belief_evidence",
                "beliefs",
                "events",
                "incarnations",
                "agents",
                "schema_meta",
                "mnemosyne_meta",
            ):
                connection.execute(f"DROP TABLE IF EXISTS {table}")
            connection.commit()
        self.path.unlink(missing_ok=True)
        Path(f"{self.path}-wal").unlink(missing_ok=True)
        Path(f"{self.path}-shm").unlink(missing_ok=True)

    def compact(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")

    def _ensure_storage_capacity(self) -> None:
        if self._storage_bytes() >= self.MAX_DATABASE_BYTES:
            raise RepositoryError(
                "Mnemosyne storage limit reached; inspect and explicitly purge data"
            )

    def _storage_bytes(self) -> int:
        return sum(
            path.stat().st_size
            for path in (
                self.path,
                Path(f"{self.path}-wal"),
                Path(f"{self.path}-shm"),
            )
            if path.exists()
        )

    @staticmethod
    def _sanitize_model_config(config: dict[str, Any]) -> dict[str, Any]:
        if set(config) != {"provider", "model", "temperature", "tools"}:
            raise RepositoryError("model configuration has invalid fields")
        if not isinstance(config["temperature"], (int, float)):
            raise RepositoryError("model temperature must be numeric")
        if not isinstance(config["tools"], list) or not all(
            isinstance(tool, str) for tool in config["tools"]
        ):
            raise RepositoryError("model tools must be a string list")
        try:
            return {
                "provider": sanitize_metadata_text(config["provider"]),
                "model": sanitize_metadata_text(config["model"]),
                "temperature": config["temperature"],
                "tools": [
                    sanitize_metadata_text(tool) for tool in config["tools"]
                ],
            }
        except ValueError as error:
            raise RepositoryError(str(error)) from error

    @staticmethod
    def _validate_scores(scores: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(scores, dict) or any(
            not isinstance(key, str)
            or not isinstance(value, (bool, int, float))
            for key, value in scores.items()
        ):
            raise RepositoryError("evaluation scores must be numeric or boolean")
        return dict(scores)

    @staticmethod
    def _agent(row: sqlite3.Row) -> AgentIdentity:
        return AgentIdentity(
            row["agent_id"],
            row["name"],
            row["persona"],
            row["created_at"],
            LifecycleState(row["status"]),
        )

    @staticmethod
    def _incarnation(row: sqlite3.Row) -> Incarnation:
        return Incarnation(
            row["incarnation_id"],
            row["agent_id"],
            row["model_provider"],
            row["model_name"],
            row["started_at"],
            row["ended_at"],
            row["termination_reason"],
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> Event:
        return Event(
            row["event_id"],
            row["agent_id"],
            row["timestamp"],
            row["ingested_at"],
            row["source"],
            row["event_type"],
            json.loads(row["payload_json"]),
            row["cwd"],
            row["repo"],
            row["branch"],
            row["correlation_id"],
            row["incarnation_id"],
        )

    @staticmethod
    def _belief(
        row: sqlite3.Row, evidence: Sequence[sqlite3.Row]
    ) -> Belief:
        return Belief(
            row["belief_id"],
            row["agent_id"],
            row["created_at"],
            row["subject"],
            row["predicate"],
            row["object"],
            row["confidence"],
            row["status"],
            row["supersedes_belief_id"],
            tuple(item["event_id"] for item in evidence),
        )

    @staticmethod
    def _commitment(row: sqlite3.Row) -> Commitment:
        return Commitment(
            row["commitment_id"],
            row["agent_id"],
            row["incarnation_id"],
            row["created_at"],
            row["commitment_type"],
            row["claim"],
            row["confidence"],
            row["status"],
            row["source_belief_id"],
        )

    @staticmethod
    def _consequence(
        row: sqlite3.Row, evidence: Sequence[sqlite3.Row]
    ) -> Consequence:
        return Consequence(
            row["consequence_id"],
            row["agent_id"],
            row["created_at"],
            row["commitment_id"],
            row["result_type"],
            row["description"],
            tuple(item["event_id"] for item in evidence),
        )

    @staticmethod
    def _revision(
        row: sqlite3.Row, evidence: Sequence[sqlite3.Row]
    ) -> Revision:
        return Revision(
            row["revision_id"],
            row["agent_id"],
            row["created_at"],
            row["old_belief_id"],
            row["new_belief_id"],
            row["reason"],
            tuple(item["event_id"] for item in evidence),
        )

    @staticmethod
    def _relationship(row: sqlite3.Row) -> Relationship:
        return Relationship(
            row["relationship_id"],
            row["agent_id"],
            row["counterparty_id"],
            row["created_at"],
            row["status"],
        )

    @staticmethod
    def _user_fact(row: sqlite3.Row) -> UserFact:
        return UserFact(
            row["user_fact_id"],
            row["agent_id"],
            row["counterparty_id"],
            row["created_at"],
            row["category"],
            row["origin"],
            row["fact"],
            row["confidence"],
            row["status"],
            row["source_event_id"],
            row["supersedes_user_fact_id"],
        )

    @staticmethod
    def _context_build(row: sqlite3.Row) -> ContextBuild:
        return ContextBuild(
            row["context_build_id"],
            row["agent_id"],
            row["run_id"],
            Mode(row["mode"]),
            row["created_at"],
            row["query"],
            row["token_budget"],
            tuple(json.loads(row["selected_record_ids_json"])),
            tuple(json.loads(row["selected_fact_keys_json"])),
            row["rendered_context_hash"],
            row["rendered_context"],
        )

    @staticmethod
    def _evaluation(row: sqlite3.Row) -> Evaluation:
        return Evaluation(
            row["evaluation_id"],
            row["run_id"],
            row["scenario_id"],
            row["agent_id"],
            Mode(row["mode"]),
            row["question"],
            row["answer"],
            json.loads(row["scores_json"]),
            json.loads(row["model_config_json"]),
            row["context_build_id"],
            row["created_at"],
        )

    @staticmethod
    def _validate_event_ownership(
        connection: sqlite3.Connection,
        agent_id: str,
        event_ids: Sequence[str],
    ) -> None:
        placeholders = ",".join("?" for _ in event_ids)
        rows = connection.execute(
            f"""
            SELECT event_id, agent_id FROM events
            WHERE event_id IN ({placeholders})
            """,
            tuple(event_ids),
        ).fetchall()
        if len(rows) != len(set(event_ids)):
            raise RepositoryError("one or more evidence events do not exist")
        if any(row["agent_id"] != agent_id for row in rows):
            raise RepositoryError("evidence event belongs to another agent")

    @staticmethod
    def _validate_selected_record_ownership(
        connection: sqlite3.Connection,
        agent_id: str,
        record_ids: Sequence[str],
    ) -> None:
        tables = (
            ("events", "event_id"),
            ("beliefs", "belief_id"),
            ("commitments", "commitment_id"),
            ("consequences", "consequence_id"),
            ("revisions", "revision_id"),
            ("user_facts", "user_fact_id"),
        )
        for record_id in record_ids:
            owners = []
            for table, id_column in tables:
                row = connection.execute(
                    f"SELECT agent_id FROM {table} WHERE {id_column} = ?",
                    (record_id,),
                ).fetchone()
                if row is not None:
                    owners.append(row["agent_id"])
            if len(owners) != 1 or owners[0] != agent_id:
                raise RepositoryError(
                    f"selected record is missing or belongs to another agent: {record_id}"
                )
