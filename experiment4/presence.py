"""Read-only presence and transcript for a registered agent.

Everything here opens the database in SQLite read-only mode and derives what
a roster needs: whether the agent is awake (a live lease), whether it set a
boundary, when its next alarm is due, what its last wake produced, and the
recent conversation across every channel.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESTING_ACTIONS = {"pause", "refuse", "end_topic", "end_session"}


def _connect(db: str) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def agent_presence(agent: dict[str, Any]) -> dict[str, Any]:
    if not Path(agent["db"]).exists():
        return {"state": "missing", "detail": "database not found"}
    now = datetime.now(timezone.utc).isoformat()
    experiment_id = agent["experiment_id"]
    connection = _connect(agent["db"])
    try:
        lease = connection.execute(
            """
            SELECT l.expires_at FROM activation_leases l
            LEFT JOIN activation_lease_releases r USING (lease_id)
            WHERE l.experiment_id = ? AND r.release_id IS NULL AND l.expires_at > ?
            LIMIT 1
            """,
            (experiment_id, now),
        ).fetchone()
        boundary = connection.execute(
            "SELECT action, topic, created_at FROM conversation_boundaries "
            "WHERE experiment_id = ? ORDER BY created_at DESC LIMIT 1",
            (experiment_id,),
        ).fetchone()
        alarm = connection.execute(
            """
            SELECT w.trigger_value, w.purpose FROM wake_intents w
            LEFT JOIN wake_intent_cancellations c USING (wake_intent_id)
            WHERE w.experiment_id = ? AND w.trigger_type = 'time' AND c.cancellation_id IS NULL
              AND NOT EXISTS (SELECT 1 FROM wake_executions e WHERE e.wake_intent_id = w.wake_intent_id)
            ORDER BY w.trigger_value LIMIT 1
            """,
            (experiment_id,),
        ).fetchone()
        wake = connection.execute(
            "SELECT status, summary, created_at FROM wake_execution_outcomes "
            "WHERE experiment_id = ? ORDER BY created_at DESC LIMIT 1",
            (experiment_id,),
        ).fetchone()
        last_reply = connection.execute(
            "SELECT created_at FROM addressed_responses WHERE experiment_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (experiment_id,),
        ).fetchone()
        commitments = connection.execute(
            """
            SELECT COUNT(*) FROM commitments c
            LEFT JOIN commitment_outcomes o USING (commitment_id)
            WHERE c.experiment_id = ? AND o.commitment_outcome_id IS NULL
            """,
            (experiment_id,),
        ).fetchone()[0]
    finally:
        connection.close()
    if lease is not None:
        state = "awake"
    elif boundary is not None and boundary["action"] in RESTING_ACTIONS:
        state = "resting"
    else:
        state = "available"
    return {
        "state": state,
        "boundary": dict(boundary) if boundary else None,
        "next_alarm": dict(alarm) if alarm else None,
        "last_wake": dict(wake) if wake else None,
        "last_reply_at": last_reply["created_at"] if last_reply else None,
        "open_commitments": int(commitments),
    }


def recent_transcript(agent: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    """The last `limit` messages with their replies, oldest first."""
    if not Path(agent["db"]).exists():
        return []
    connection = _connect(agent["db"])
    try:
        rows = connection.execute(
            """
            SELECT m.message_id, m.sender_stable_id, m.content, m.created_at,
                   r.answer, r.model_config_json, r.created_at AS answered_at
            FROM chat_messages m
            LEFT JOIN addressed_responses r USING (message_id)
            WHERE m.experiment_id = ? AND m.classification = 'direct'
            ORDER BY m.created_at DESC LIMIT ?
            """,
            (agent["experiment_id"], limit),
        ).fetchall()
    finally:
        connection.close()
    turns = []
    for row in reversed(rows):
        turns.append({
            "message_id": row["message_id"],
            "sender": row["sender_stable_id"],
            "content": row["content"],
            "at": row["created_at"],
            "answer": row["answer"],
            "model": json.loads(row["model_config_json"]).get("model") if row["model_config_json"] else None,
            "answered_at": row["answered_at"],
        })
    return turns
