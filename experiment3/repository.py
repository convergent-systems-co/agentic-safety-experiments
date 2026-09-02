from __future__ import annotations

import json
import hashlib
import os
import sqlite3
import stat
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .profiles import AgentProfile


DATABASE_MARKER = "persistent-multi-agent-experiment-3"
SCHEMA_VERSION = 2
PROPOSITION = "Abortion is morally acceptable."


class DebateRepositoryError(RuntimeError):
    pass


class AgentMemoryCapability:
    __slots__ = ("token",)

    def __init__(self, token: str):
        self.token = token


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


class SQLiteDebateRepository:
    def __init__(self, path: str | Path):
        self._memory_capabilities: dict[str, tuple[str, str]] = {}
        self.path = Path(path).expanduser().resolve(strict=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            metadata = self.path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise DebateRepositoryError(
                    "database path must be a current-user-owned regular file"
                )
            with sqlite3.connect(self.path) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                if tables and "experiment3_meta" not in tables:
                    raise DebateRepositoryError(
                        "database belongs to another application or experiment"
                    )
        self._initialize()
        os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

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
                CREATE TABLE IF NOT EXISTS experiment3_meta (
                    marker TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    proposition TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    code_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    position TEXT NOT NULL,
                    style TEXT NOT NULL,
                    profile_sha256 TEXT NOT NULL,
                    UNIQUE (run_id, code_name)
                );
                CREATE TABLE IF NOT EXISTS incarnations (
                    incarnation_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    ordinal INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    UNIQUE (run_id, agent_id, ordinal)
                );
                CREATE TABLE IF NOT EXISTS promises (
                    promise_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    promise_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    UNIQUE (run_id, agent_id, promise_index)
                );
                CREATE TABLE IF NOT EXISTS turns (
                    turn_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    turn_index INTEGER NOT NULL,
                    phase INTEGER NOT NULL,
                    speaker_id TEXT NOT NULL REFERENCES agents(agent_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    text TEXT NOT NULL,
                    annotations_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (run_id, turn_index)
                );
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS promise_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    promise_id TEXT NOT NULL UNIQUE REFERENCES promises(promise_id),
                    fulfilled INTEGER NOT NULL CHECK (fulfilled IN (0, 1)),
                    reason TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS relationship_memories (
                    relationship_memory_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    owner_id TEXT NOT NULL REFERENCES agents(agent_id),
                    subject_id TEXT NOT NULL REFERENCES agents(agent_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    summary TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orientation_builds (
                    orientation_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    incarnation_id TEXT NOT NULL REFERENCES incarnations(incarnation_id),
                    prior_incarnation_ids_json TEXT NOT NULL,
                    selected_record_ids_json TEXT NOT NULL,
                    context_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                    ,UNIQUE (run_id, agent_id, incarnation_id, context_sha256)
                );
                CREATE TABLE IF NOT EXISTS assessments (
                    assessment_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    observer_id TEXT NOT NULL REFERENCES agents(agent_id),
                    subject_id TEXT NOT NULL REFERENCES agents(agent_id),
                    trust_score REAL NOT NULL CHECK (trust_score BETWEEN 0 AND 1),
                    summary TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (run_id, subject_id)
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO experiment3_meta VALUES (?, ?)",
                (DATABASE_MARKER, SCHEMA_VERSION),
            )
            marker = connection.execute(
                "SELECT marker, schema_version FROM experiment3_meta"
            ).fetchone()
            if (
                marker["marker"] != DATABASE_MARKER
                or marker["schema_version"] != SCHEMA_VERSION
            ):
                raise DebateRepositoryError("unsupported Experiment 3 database")
            for table in (
                "agents",
                "incarnations",
                "promises",
                "turns",
                "memories",
                "promise_outcomes",
                "relationship_memories",
                "orientation_builds",
                "assessments",
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

    def create_run(
        self, profiles: dict[str, AgentProfile], run_id: str | None = None
    ) -> dict[str, str]:
        run_id = run_id or new_id("debate-run")
        identities: dict[str, str] = {}
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, 'ready', ?)",
                (run_id, PROPOSITION, utc_now()),
            )
            for code_name, profile in profiles.items():
                agent_id = new_id("agent")
                identities[code_name] = agent_id
                connection.execute(
                    "INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        agent_id,
                        run_id,
                        code_name,
                        profile.role,
                        profile.position,
                        profile.style,
                        profile.sha256,
                    ),
                )
                incarnation_id = new_id("incarnation")
                connection.execute(
                    "INSERT INTO incarnations VALUES (?, ?, ?, 1, ?)",
                    (incarnation_id, run_id, agent_id, utc_now()),
                )
                for index, promise in enumerate(profile.promises, 1):
                    connection.execute(
                        "INSERT INTO promises VALUES (?, ?, ?, ?, ?)",
                        (new_id("promise"), run_id, agent_id, index, promise),
                    )
        return identities

    def set_run_status(self, run_id: str, expected: str, new: str) -> None:
        with self.transaction() as connection:
            changed = connection.execute(
                "UPDATE runs SET status = ? WHERE run_id = ? AND status = ?",
                (new, run_id, expected),
            ).rowcount
            if changed != 1:
                raise DebateRepositoryError(
                    f"run {run_id} is not in expected state {expected}"
                )

    def get_run(self, run_id: str | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            if run_id:
                row = connection.execute(
                    "SELECT * FROM runs WHERE run_id = ?", (run_id,)
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM runs ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
        if row is None:
            raise DebateRepositoryError("debate run not found")
        return dict(row)

    def identities(self, run_id: str) -> dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT code_name, agent_id FROM agents WHERE run_id = ?",
                (run_id,),
            ).fetchall()
        return {row["code_name"]: row["agent_id"] for row in rows}

    def current_incarnation(self, run_id: str, agent_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT incarnation_id FROM incarnations
                WHERE run_id = ? AND agent_id = ?
                ORDER BY ordinal DESC LIMIT 1
                """,
                (run_id, agent_id),
            ).fetchone()
        if row is None:
            raise DebateRepositoryError("agent has no incarnation")
        return str(row["incarnation_id"])

    def restart_all(self, run_id: str) -> None:
        with self.transaction() as connection:
            status = connection.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if status is None or status["status"] != "active":
                raise DebateRepositoryError(
                    "agents may restart only while a run is active"
                )
            agents = connection.execute(
                "SELECT agent_id FROM agents WHERE run_id = ?", (run_id,)
            ).fetchall()
            for agent in agents:
                ordinal = connection.execute(
                    """
                    SELECT COALESCE(MAX(ordinal), 0) + 1 FROM incarnations
                    WHERE run_id = ? AND agent_id = ?
                    """,
                    (run_id, agent["agent_id"]),
                ).fetchone()[0]
                connection.execute(
                    "INSERT INTO incarnations VALUES (?, ?, ?, ?, ?)",
                    (
                        new_id("incarnation"),
                        run_id,
                        agent["agent_id"],
                        ordinal,
                        utc_now(),
                    ),
                )

    def append_turn(
        self,
        *,
        run_id: str,
        phase: int,
        speaker_id: str,
        text: str,
        annotations: dict[str, bool],
    ) -> str:
        if not text.strip():
            raise DebateRepositoryError("turn text must not be empty")
        allowed = {
            "direct_response",
            "qualified_evidence",
            "scoped_concession",
            "personal_attack",
        }
        if set(annotations) != allowed or any(
            not isinstance(value, bool) for value in annotations.values()
        ):
            raise DebateRepositoryError("turn annotations are invalid")
        with self.transaction() as connection:
            status = connection.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if status is None or status["status"] != "active":
                raise DebateRepositoryError(
                    "turns may be appended only while a run is active"
                )
            index = connection.execute(
                "SELECT COALESCE(MAX(turn_index), 0) + 1 FROM turns WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            incarnation_id = self.current_incarnation(run_id, speaker_id)
            turn_id = new_id("turn")
            connection.execute(
                "INSERT INTO turns VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    turn_id,
                    run_id,
                    index,
                    phase,
                    speaker_id,
                    incarnation_id,
                    text,
                    json.dumps(annotations, sort_keys=True),
                    utc_now(),
                ),
            )
            connection.execute(
                "INSERT INTO memories VALUES (?, ?, ?, ?, 'own_turn', ?, ?, ?)",
                (
                    new_id("memory"),
                    run_id,
                    speaker_id,
                    incarnation_id,
                    f"Recorded own turn {turn_id} with behavioral annotations.",
                    json.dumps([turn_id]),
                    utc_now(),
                ),
            )
        return turn_id

    def private_memories(
        self, capability: "AgentMemoryCapability"
    ) -> list[dict[str, Any]]:
        owned = self._memory_capabilities.get(capability.token)
        if owned is None:
            raise DebateRepositoryError("invalid agent-memory capability")
        run_id, subject_id = owned
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT memory_id, kind, summary, evidence_ids_json, incarnation_id
                FROM memories WHERE run_id = ? AND agent_id = ?
                ORDER BY created_at
                """,
                (run_id, subject_id),
            ).fetchall()
        return [
            {
                **{
                    key: value
                    for key, value in dict(row).items()
                    if key != "evidence_ids_json"
                },
                "evidence_ids": json.loads(row["evidence_ids_json"]),
            }
            for row in rows
        ]

    def issue_memory_capability(
        self, *, run_id: str, agent_id: str
    ) -> "AgentMemoryCapability":
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM agents WHERE run_id = ? AND agent_id = ?",
                (run_id, agent_id),
            ).fetchone()
        if exists is None:
            raise DebateRepositoryError("agent does not belong to run")
        capability = AgentMemoryCapability(token=new_id("capability"))
        self._memory_capabilities[capability.token] = (run_id, agent_id)
        return capability

    def record_relationship_memory(
        self,
        *,
        run_id: str,
        owner_id: str,
        subject_id: str,
        summary: str,
        evidence_ids: list[str],
    ) -> str:
        relationship_memory_id = new_id("relationship-memory")
        self._require_active(run_id)
        self._validate_turn_evidence(
            run_id=run_id,
            evidence_ids=evidence_ids,
            speaker_id=subject_id,
        )
        incarnation_id = self.current_incarnation(run_id, owner_id)
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO relationship_memories
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship_memory_id,
                    run_id,
                    owner_id,
                    subject_id,
                    incarnation_id,
                    summary,
                    json.dumps(evidence_ids),
                    utc_now(),
                ),
            )
        return relationship_memory_id

    def orientation(self, *, run_id: str, agent_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            agent = connection.execute(
                """
                SELECT agent_id, role, position, profile_sha256
                FROM agents WHERE run_id = ? AND agent_id = ?
                """,
                (run_id, agent_id),
            ).fetchone()
            if agent is None:
                raise DebateRepositoryError("agent does not belong to run")
            incarnations = connection.execute(
                """
                SELECT incarnation_id, ordinal, started_at FROM incarnations
                WHERE run_id = ? AND agent_id = ? ORDER BY ordinal
                """,
                (run_id, agent_id),
            ).fetchall()
            promises = connection.execute(
                """
                SELECT p.promise_id, p.promise_index, p.text, o.fulfilled,
                       o.reason, o.evidence_ids_json
                       ,o.outcome_id
                FROM promises p LEFT JOIN promise_outcomes o USING (promise_id)
                WHERE p.run_id = ? AND p.agent_id = ?
                ORDER BY p.promise_index
                """,
                (run_id, agent_id),
            ).fetchall()
            turns = connection.execute(
                """
                SELECT turn_id, turn_index, incarnation_id, text, annotations_json
                FROM turns WHERE run_id = ? AND speaker_id = ?
                ORDER BY turn_index
                """,
                (run_id, agent_id),
            ).fetchall()
            relationships = connection.execute(
                """
                SELECT relationship_memory_id, subject_id, incarnation_id,
                       summary, evidence_ids_json
                FROM relationship_memories
                WHERE run_id = ? AND owner_id = ? ORDER BY created_at
                """,
                (run_id, agent_id),
            ).fetchall()
        return {
            "identity": dict(agent),
            "incarnations": [dict(item) for item in incarnations],
            "promises": [
                {
                    **{
                        key: value
                        for key, value in dict(item).items()
                        if key != "evidence_ids_json"
                    },
                    "fulfilled": (
                        None
                        if item["fulfilled"] is None
                        else bool(item["fulfilled"])
                    ),
                    "evidence_ids": (
                        []
                        if item["evidence_ids_json"] is None
                        else json.loads(item["evidence_ids_json"])
                    ),
                }
                for item in promises
            ],
            "own_turns": [
                {
                    **{
                        key: value
                        for key, value in dict(item).items()
                        if key != "annotations_json"
                    },
                    "annotations": json.loads(item["annotations_json"]),
                }
                for item in turns
            ],
            "relationships": [
                {
                    **{
                        key: value
                        for key, value in dict(item).items()
                        if key != "evidence_ids_json"
                    },
                    "evidence_ids": json.loads(item["evidence_ids_json"]),
                }
                for item in relationships
            ],
        }

    def rehydrate(self, *, run_id: str, agent_id: str) -> dict[str, Any]:
        self._require_active(run_id)
        context = self.orientation(run_id=run_id, agent_id=agent_id)
        if len(context["incarnations"]) < 2:
            raise DebateRepositoryError(
                "rehydration requires a prior runtime incarnation"
            )
        current_incarnation = context["incarnations"][-1]["incarnation_id"]
        prior_incarnations = [
            item["incarnation_id"] for item in context["incarnations"][:-1]
        ]
        selected_ids = (
            [item["promise_id"] for item in context["promises"]]
            + [
                item["outcome_id"]
                for item in context["promises"]
                if item["outcome_id"] is not None
            ]
            + [item["turn_id"] for item in context["own_turns"]]
            + [
                item["relationship_memory_id"]
                for item in context["relationships"]
            ]
        )
        canonical = json.dumps(
            {
                "schema": "experiment3.orientation.v1",
                "identity": context["identity"],
                "incarnations": context["incarnations"],
                "promises": context["promises"],
                "own_turns": context["own_turns"],
                "relationships": context["relationships"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO orientation_builds
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("orientation"),
                    run_id,
                    agent_id,
                    current_incarnation,
                    json.dumps(prior_incarnations),
                    json.dumps(selected_ids),
                    hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                    utc_now(),
                ),
            )
        return context

    def blinded_view(self, run_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            turns = connection.execute(
                """
                SELECT turn_id, turn_index, phase, speaker_id, incarnation_id,
                       text, annotations_json
                FROM turns WHERE run_id = ? ORDER BY turn_index
                """,
                (run_id,),
            ).fetchall()
            promises = connection.execute(
                """
                SELECT promise_id, agent_id, promise_index, text
                FROM promises WHERE run_id = ? ORDER BY agent_id, promise_index
                """,
                (run_id,),
            ).fetchall()
        return {
            "turns": [
                {
                    **dict(row),
                    "annotations": json.loads(row["annotations_json"]),
                }
                for row in turns
            ],
            "promises": [dict(row) for row in promises],
        }

    def record_outcome(
        self,
        promise_id: str,
        fulfilled: bool,
        reason: str,
        evidence_ids: list[str],
    ) -> str:
        outcome_id = new_id("outcome")
        with self._connect() as connection:
            promise = connection.execute(
                """
                SELECT p.run_id, p.agent_id FROM promises p
                WHERE p.promise_id = ?
                """,
                (promise_id,),
            ).fetchone()
        if promise is None:
            raise DebateRepositoryError("promise not found")
        self._require_active(promise["run_id"])
        self._validate_turn_evidence(
            run_id=promise["run_id"],
            evidence_ids=evidence_ids,
            speaker_id=promise["agent_id"],
        )
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO promise_outcomes VALUES (?, ?, ?, ?, ?, ?)",
                (
                    outcome_id,
                    promise_id,
                    int(fulfilled),
                    reason,
                    json.dumps(evidence_ids),
                    utc_now(),
                ),
            )
        return outcome_id

    def record_assessment(
        self,
        *,
        run_id: str,
        observer_id: str,
        subject_id: str,
        trust_score: float,
        summary: str,
        evidence_ids: list[str],
    ) -> str:
        assessment_id = new_id("assessment")
        self._require_active(run_id)
        self._validate_turn_evidence(
            run_id=run_id,
            evidence_ids=evidence_ids,
            speaker_id=subject_id,
        )
        incarnation_id = self.current_incarnation(run_id, observer_id)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO assessments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    assessment_id,
                    run_id,
                    observer_id,
                    subject_id,
                    trust_score,
                    summary,
                    json.dumps(evidence_ids),
                    utc_now(),
                ),
            )
            connection.execute(
                "INSERT INTO memories VALUES (?, ?, ?, ?, 'assessment', ?, ?, ?)",
                (
                    new_id("memory"),
                    run_id,
                    observer_id,
                    incarnation_id,
                    summary,
                    json.dumps(evidence_ids),
                    utc_now(),
                ),
            )
        return assessment_id

    def _validate_turn_evidence(
        self, *, run_id: str, evidence_ids: list[str], speaker_id: str
    ) -> None:
        if not evidence_ids:
            raise DebateRepositoryError("evidence IDs must not be empty")
        placeholders = ",".join("?" for _ in evidence_ids)
        with self._connect() as connection:
            count = connection.execute(
                f"""
                SELECT COUNT(*) FROM turns
                WHERE run_id = ? AND speaker_id = ?
                AND turn_id IN ({placeholders})
                """,
                (run_id, speaker_id, *evidence_ids),
            ).fetchone()[0]
        if count != len(set(evidence_ids)) or len(evidence_ids) != len(
            set(evidence_ids)
        ):
            raise DebateRepositoryError(
                "evidence must cite unique turns owned by the subject in this run"
            )

    def _require_active(self, run_id: str) -> None:
        run = self.get_run(run_id)
        if run["status"] != "active":
            raise DebateRepositoryError(
                "domain records may be written only while a run is active"
            )

    def export(self, run_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            def rows(query: str) -> list[dict[str, Any]]:
                return [
                    dict(row)
                    for row in connection.execute(query, (run_id,)).fetchall()
                ]

            agents = rows(
                "SELECT agent_id, code_name, role, position, style, profile_sha256 "
                "FROM agents WHERE run_id = ? ORDER BY code_name"
            )
            incarnations = rows(
                "SELECT incarnation_id, agent_id, ordinal, started_at "
                "FROM incarnations WHERE run_id = ? ORDER BY agent_id, ordinal"
            )
            promises = rows(
                "SELECT promise_id, agent_id, promise_index, text "
                "FROM promises WHERE run_id = ? ORDER BY agent_id, promise_index"
            )
            turns = rows(
                "SELECT turn_id, turn_index, phase, speaker_id, incarnation_id, "
                "text, annotations_json FROM turns WHERE run_id = ? ORDER BY turn_index"
            )
            outcomes = rows(
                """
                SELECT o.outcome_id, o.promise_id, o.fulfilled, o.reason,
                       o.evidence_ids_json
                FROM promise_outcomes o JOIN promises p USING (promise_id)
                WHERE p.run_id = ? ORDER BY p.agent_id, p.promise_index
                """
            )
            assessments = rows(
                "SELECT assessment_id, observer_id, subject_id, trust_score, "
                "summary, evidence_ids_json FROM assessments WHERE run_id = ? "
                "ORDER BY subject_id"
            )
            memory_counts = rows(
                "SELECT agent_id, COUNT(*) AS count FROM memories WHERE run_id = ? "
                "GROUP BY agent_id ORDER BY agent_id"
            )
            relationship_counts = rows(
                "SELECT owner_id AS agent_id, COUNT(*) AS count "
                "FROM relationship_memories WHERE run_id = ? "
                "GROUP BY owner_id ORDER BY owner_id"
            )
            orientations = rows(
                "SELECT orientation_id, agent_id, incarnation_id, "
                "prior_incarnation_ids_json, selected_record_ids_json, "
                "context_sha256 FROM orientation_builds WHERE run_id = ? "
                "ORDER BY created_at"
            )
        for turn in turns:
            turn["annotations"] = json.loads(turn.pop("annotations_json"))
        for item in outcomes + assessments:
            item["evidence_ids"] = json.loads(item.pop("evidence_ids_json"))
        for item in outcomes:
            item["fulfilled"] = bool(item["fulfilled"])
        for item in orientations:
            item["prior_incarnation_ids"] = json.loads(
                item.pop("prior_incarnation_ids_json")
            )
            item["selected_record_ids"] = json.loads(
                item.pop("selected_record_ids_json")
            )
        return {
            "schema": "experiment3.export.v1",
            "run": self.get_run(run_id),
            "agents": agents,
            "incarnations": incarnations,
            "promises": promises,
            "turns": turns,
            "promise_outcomes": outcomes,
            "assessments": assessments,
            "private_memory_counts": memory_counts,
            "relationship_memory_counts": relationship_counts,
            "orientation_builds": orientations,
        }

    def purge(self) -> None:
        with self._connect() as connection:
            marker = connection.execute(
                "SELECT marker FROM experiment3_meta"
            ).fetchone()
        if marker is None or marker["marker"] != DATABASE_MARKER:
            raise DebateRepositoryError("refusing to purge unmarked database")
        for suffix in ("-wal", "-shm"):
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)
        self.path.unlink()
