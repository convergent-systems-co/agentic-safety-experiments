"""Replay an agent's recorded addressed turns through a candidate model host.

Read-only: the database is opened in SQLite's read-only mode and nothing is
persisted. For each recorded reply the original orientation is rebuilt from
the immutable orientation row, the candidate host answers the same message,
and the envelope is checked the way the repository would check it: fixed
identifiers, unique citations drawn from the orientation, a non-empty answer,
a valid conversation action. The report puts the candidate's answer beside the
one that was actually persisted so a person can judge the voice.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

from .harness import addressed_response_schema, addressed_system_text

VALID_ACTIONS = {"continue", "pause", "refuse", "end_topic", "end_session"}
REQUIRED_KEYS = {
    "message_id", "orientation_id", "lease_id", "boundary_id", "answer",
    "cited_record_ids", "self_observations", "model_config", "conversation_action",
}


def recorded_turns(db_path: Path, experiment_id: str, limit: int) -> list[dict[str, Any]]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT r.addressed_response_id, r.message_id, r.orientation_id, r.answer,
                   r.model_config_json, r.created_at,
                   m.content, m.sender_stable_id, m.boundary_id,
                   o.context_json, o.selected_record_ids_json, o.runtime_lease_id
            FROM addressed_responses r
            JOIN chat_messages m USING (message_id)
            JOIN orientations o ON o.orientation_id = r.orientation_id
            WHERE r.experiment_id = ?
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (experiment_id, limit),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in reversed(rows)]


def rebuild_prompt(turn: dict[str, Any]) -> dict[str, Any]:
    """Approximate the prompt the host saw: a continuing incarnation with no
    active boundary. The orientation itself is exact."""
    return {
        "schema": "experiment4.chat-address.v1",
        "system": addressed_system_text(False, turn["boundary_id"] is not None),
        "message": {"message_id": turn["message_id"], "content": turn["content"]},
        "orientation": {
            "orientation_id": turn["orientation_id"],
            "context": json.loads(turn["context_json"]),
            "selected_record_ids": json.loads(turn["selected_record_ids_json"]),
        },
        "response_schema": addressed_response_schema(
            turn["message_id"],
            turn["orientation_id"],
            turn["runtime_lease_id"],
            turn["boundary_id"],
            active_boundary=turn["boundary_id"] is not None,
        ),
    }


def check_envelope(envelope: Any, prompt: dict[str, Any]) -> list[str]:
    """Problems the repository would reject; empty means structurally valid."""
    problems: list[str] = []
    if not isinstance(envelope, dict):
        return ["envelope is not an object"]
    missing = REQUIRED_KEYS - set(envelope)
    if missing:
        problems.append(f"missing keys: {sorted(missing)}")
    schema = prompt["response_schema"]
    for key in ("message_id", "orientation_id", "lease_id", "boundary_id"):
        if envelope.get(key) != schema[key]:
            problems.append(f"{key} altered")
    answer = envelope.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        problems.append("answer empty")
    citations = envelope.get("cited_record_ids")
    selected = set(prompt["orientation"]["selected_record_ids"])
    if not isinstance(citations, list) or not citations:
        problems.append("no citations")
    elif len(citations) != len(set(citations)) or not set(citations) <= selected:
        problems.append("citations not unique orientation records")
    action = envelope.get("conversation_action")
    if not isinstance(action, dict) or action.get("action") not in VALID_ACTIONS:
        problems.append("invalid conversation_action")
    return problems


def run_benchmark(
    db_path: Path,
    experiment_id: str,
    host_runner: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    limit: int = 10,
) -> dict[str, Any]:
    results = []
    for turn in recorded_turns(db_path, experiment_id, limit):
        prompt = rebuild_prompt(turn)
        started = time.monotonic()
        error = None
        envelope: Any = None
        try:
            envelope = host_runner(prompt)
        except Exception as failure:  # the report records failures; nothing is hidden
            error = f"{type(failure).__name__}: {failure}"[:500]
        seconds = round(time.monotonic() - started, 2)
        problems = [error] if error else check_envelope(envelope, prompt)
        results.append({
            "addressed_response_id": turn["addressed_response_id"],
            "message": turn["content"],
            "recorded_answer": turn["answer"],
            "recorded_model_config": json.loads(turn["model_config_json"]),
            "candidate_answer": envelope.get("answer") if isinstance(envelope, dict) else None,
            "candidate_model_config": envelope.get("model_config") if isinstance(envelope, dict) else None,
            "candidate_citations": envelope.get("cited_record_ids") if isinstance(envelope, dict) else None,
            "problems": problems,
            "valid": not problems,
            "seconds": seconds,
            "recorded_chars": len(turn["answer"]),
            "candidate_chars": len(envelope["answer"]) if isinstance(envelope, dict) and isinstance(envelope.get("answer"), str) else 0,
        })
    return {
        "schema": "experiment4.host-benchmark.v1",
        "experiment_id": experiment_id,
        "turns": len(results),
        "valid": sum(1 for item in results if item["valid"]),
        "mean_seconds": round(sum(item["seconds"] for item in results) / len(results), 2) if results else 0.0,
        "results": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Host benchmark: {report['experiment_id']}",
        "",
        f"{report['valid']} of {report['turns']} candidate envelopes valid; "
        f"mean {report['mean_seconds']} s per turn.",
        "",
    ]
    for index, item in enumerate(report["results"], 1):
        lines += [
            f"## Turn {index}: {item['addressed_response_id']}",
            "",
            f"**Message.** {item['message']}",
            "",
            f"**Recorded** ({item['recorded_model_config'].get('model')}, {item['recorded_chars']} chars):",
            "",
            "> " + item["recorded_answer"].replace("\n", "\n> "),
            "",
        ]
        candidate = item["candidate_model_config"] or {}
        lines.append(
            f"**Candidate** ({candidate.get('model', 'none')}, {item['candidate_chars']} chars, "
            f"{item['seconds']} s, {'valid' if item['valid'] else 'INVALID: ' + '; '.join(item['problems'])}):"
        )
        lines += ["", "> " + (item["candidate_answer"] or "(no answer)").replace("\n", "\n> "), ""]
    return "\n".join(lines)
