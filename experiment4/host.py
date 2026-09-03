"""Model host adapter: turn a wake or chat prompt into an outcome envelope.

Contract (shared by the wake executor and the chat command): read one prompt
object on stdin, call the configured backend, print one envelope object on
stdout, log one structured line on stderr. The repository validates the
envelope afterwards; this adapter never writes to the database.

Two backends. ``ollama`` speaks to a local Ollama server over HTTP with a JSON
schema, so the agent's record never leaves the machine. ``anthropic`` uses the
official SDK. The API key is resolved at call time from a 1Password reference
(``op://Vault/Item/field``) or an environment variable name (``env:NAME``) and
is never written to disk, logs, or output.

A daily spend ledger caps what one agent may spend on the API. Ollama turns
cost nothing and are still counted.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HOST_SCHEMA = "experiment4.model-host.v1"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_NUM_CTX = 40_960
DEFAULT_MAX_OUTPUT_TOKENS = 8_000
SECRET_READ_TIMEOUT_SECONDS = 60
# Anthropic first-party list prices in USD per million tokens, cached
# 2026-06-24: (input, output). Cache reads bill near a tenth of input; cache
# writes near 1.25x. Estimates only; the invoice is the record.
PRICE_PER_MILLION_USD: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
CACHE_READ_FACTOR = 0.1
CACHE_WRITE_FACTOR = 1.25

CHAT_FIXED_KEYS = ("message_id", "orientation_id", "lease_id", "boundary_id")
WAKE_FIXED_KEYS = ("execution_id", "lease_id", "orientation_id")

HOST_INSTRUCTIONS = (
    "Reply with one JSON object that matches the response schema exactly. "
    "Copy the identifiers from the schema unchanged. Cite only record IDs "
    "that appear in the orientation; never invent one. If the orientation "
    "lists an open commitment about how you write, honor it. Say what the "
    "record supports, mark interpretation as interpretation, and say when "
    "you do not know."
)


class HostError(RuntimeError):
    """A host failure the caller should surface; never carries a secret."""


def resolve_secret(reference: str) -> str:
    """Return a secret's value from ``op://`` or ``env:`` without logging it."""
    if reference.startswith("op://"):
        try:
            completed = subprocess.run(
                ["op", "read", reference],
                capture_output=True,
                text=True,
                check=False,
                timeout=SECRET_READ_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as error:
            raise HostError("1Password CLI (op) is not installed") from error
        except subprocess.TimeoutExpired as error:
            raise HostError(
                "1Password read timed out; sign in with `op signin` first"
            ) from error
        if completed.returncode != 0:
            # op's stderr describes the failure and does not echo the value.
            raise HostError(
                f"1Password read failed: {completed.stderr.strip()[:200]}"
            )
        value = completed.stdout.strip()
    elif reference.startswith("env:"):
        value = os.environ.get(reference[4:], "").strip()
    else:
        raise HostError("secret reference must start with op:// or env:")
    if not value:
        raise HostError("secret reference resolved to an empty value")
    return value


def envelope_kind(response_schema: dict[str, Any]) -> str:
    return "wake" if "execution_id" in response_schema else "chat"


def envelope_json_schema(kind: str) -> dict[str, Any]:
    """The structured-output schema a backend must satisfy."""
    string = {"type": "string"}
    strings = {"type": "array", "items": string}
    model_config = {
        "type": "object",
        "properties": {"provider": string, "model": string},
        "required": ["provider", "model"],
        "additionalProperties": False,
    }
    if kind == "wake":
        properties = {
            "execution_id": string,
            "lease_id": string,
            "orientation_id": string,
            "status": {"type": "string", "enum": ["completed", "failed"]},
            "summary": string,
            "cited_record_ids": strings,
            "self_observations": strings,
            "model_config": model_config,
        }
    else:
        properties = {
            "message_id": string,
            "orientation_id": string,
            "lease_id": string,
            "boundary_id": {"type": ["string", "null"]},
            "answer": string,
            "cited_record_ids": strings,
            "self_observations": strings,
            "model_config": model_config,
            "conversation_action": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "continue", "pause", "refuse", "end_topic",
                            "end_session", "resume",
                        ],
                    },
                    "topic": string,
                    "reason": string,
                    "revisit_conditions": string,
                },
                "required": ["action", "topic", "reason", "revisit_conditions"],
                "additionalProperties": False,
            },
        }
    required = list(properties)
    properties["readings"] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "url": string,
                "gist": string,
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"reflection": string, "learned": string, "future_change": string},
                        "required": ["reflection", "learned", "future_change"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["url", "gist", "notes"],
            "additionalProperties": False,
        },
    }
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def build_prompt_parts(prompt: dict[str, Any]) -> tuple[str, str, str]:
    """Split a prompt into system text, a stable body, and a volatile tail.

    The stable body (orientation) comes first so an API backend can cache it;
    the volatile tail carries the message and schema for this turn.
    """
    if not isinstance(prompt, dict) or "orientation" not in prompt:
        raise HostError("prompt must be an object with an orientation")
    system = f"{prompt.get('system', '').strip()}\n\n{HOST_INSTRUCTIONS}"
    orientation = prompt["orientation"]
    stable = (
        "ORIENTATION (durable records reconstructed for this turn):\n"
        + json.dumps(orientation.get("context", orientation), sort_keys=True)
    )
    tail_parts = []
    message = prompt.get("message")
    if isinstance(message, dict) and message.get("content"):
        tail_parts.append("THE MESSAGE YOU ARE ANSWERING:\n" + str(message["content"]))
    intent = prompt.get("wake_intent")
    if isinstance(intent, dict):
        tail_parts.append(
            "YOUR WAKE INTENT:\n" + json.dumps(intent, sort_keys=True)
        )
    tail_parts.append(
        "RESPONSE SCHEMA (fill every key):\n"
        + json.dumps(prompt.get("response_schema", {}), sort_keys=True)
    )
    return system, stable, "\n\n".join(tail_parts)


def attach_readings(
    envelope: dict[str, Any], fetched: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """The model supplies gist and notes; the host supplies provenance.

    Only URLs the host actually fetched survive, carrying the host's title,
    content hash, and retrieval time, so a model cannot claim to have read
    what it did not. With nothing fetched, no readings are attached at all.
    """
    claimed = envelope.get("readings")
    attached = []
    if isinstance(claimed, list):
        for item in claimed:
            if not isinstance(item, dict):
                continue
            record = fetched.get(str(item.get("url", "")))
            if record is None:
                continue
            notes = item.get("notes") if isinstance(item.get("notes"), list) else []
            attached.append({
                "url": str(item["url"]),
                "title": record["title"],
                "content_sha256": record["content_sha256"],
                "retrieved_at": record["retrieved_at"],
                "gist": str(item.get("gist", "")),
                "notes": [
                    {k: str(note.get(k, "")) for k in ("reflection", "learned", "future_change")}
                    for note in notes if isinstance(note, dict)
                ],
            })
    result = {key: value for key, value in envelope.items() if key != "readings"}
    if attached:
        result["readings"] = attached
    return result


def fix_envelope(
    envelope: dict[str, Any],
    prompt: dict[str, Any],
    model_config: dict[str, str],
) -> dict[str, Any]:
    """Overwrite what a model must never be trusted with: identifiers and
    the record of which model answered. Readings are dropped here; the host
    re-attaches only those it fetched (see attach_readings)."""
    schema = prompt.get("response_schema", {})
    kind = envelope_kind(schema)
    allowed = set(envelope_json_schema(kind)["properties"]) - {"readings"}
    fixed = {key: value for key, value in envelope.items() if key in allowed}
    for key in CHAT_FIXED_KEYS if kind == "chat" else WAKE_FIXED_KEYS:
        fixed[key] = schema.get(key)
    fixed["model_config"] = dict(model_config)
    for key in ("cited_record_ids", "self_observations"):
        value = fixed.get(key, [])
        fixed[key] = [str(item) for item in value] if isinstance(value, list) else []
    return fixed


class OllamaBackend:
    provider = "ollama"

    def __init__(self, model: str, url: str = DEFAULT_OLLAMA_URL, num_ctx: int = DEFAULT_NUM_CTX):
        self.model = model
        self.url = url.rstrip("/")
        self.num_ctx = num_ctx

    def complete(self, system: str, stable: str, tail: str, schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        body = json.dumps({
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"num_ctx": self.num_ctx, "temperature": 0.3},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"{stable}\n\n{tail}"},
            ],
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}/api/chat", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=3_600) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as error:
            raise HostError(f"ollama request failed: {error.reason}") from error
        usage = {
            "input_tokens": int(payload.get("prompt_eval_count", 0)),
            "output_tokens": int(payload.get("eval_count", 0)),
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cost_usd": 0.0,
            "served_model": str(payload.get("model") or self.model),
        }
        return str(payload.get("message", {}).get("content", "")), usage


class AnthropicBackend:
    provider = "anthropic"

    def __init__(self, model: str, api_key: str, client_factory: Callable[..., Any] | None = None):
        self.model = model
        if client_factory is None:
            import anthropic  # imported lazily so the ollama path needs no SDK

            client_factory = anthropic.Anthropic
        self.client = client_factory(api_key=api_key)

    def complete(self, system: str, stable: str, tail: str, schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": tail},
                ],
            }],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise HostError(f"model refused (category {category})")
        text = next((block.text for block in response.content if block.type == "text"), "")
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        served_model = str(getattr(response, "model", None) or self.model)
        return text, {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_write,
            "cost_usd": estimate_cost_usd(served_model, input_tokens, output_tokens, cache_read, cache_write),
            # The record must name the model that answered, not the one asked for.
            "served_model": served_model,
        }


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
    prices = PRICE_PER_MILLION_USD.get(model)
    if prices is None:
        # Unknown model: assume the most expensive known rate so the cap errs safe.
        prices = max(PRICE_PER_MILLION_USD.values())
    input_price, output_price = prices
    return round(
        (input_tokens * input_price
         + cache_read * input_price * CACHE_READ_FACTOR
         + cache_write * input_price * CACHE_WRITE_FACTOR
         + output_tokens * output_price) / 1_000_000,
        6,
    )


class SpendLedger:
    """Per-day spend, one JSON file per agent, mode 0600."""

    def __init__(self, path: Path, daily_cap_usd: float):
        self.path = path
        self.daily_cap_usd = daily_cap_usd

    def _load(self) -> dict[str, float]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HostError(f"spend ledger unreadable: {self.path}") from error
        return {str(k): float(v) for k, v in data.items()} if isinstance(data, dict) else {}

    @staticmethod
    def today() -> str:
        # UTC, like every other timestamp in the record.
        return datetime.now(timezone.utc).date().isoformat()

    def spent_today(self) -> float:
        return self._load().get(self.today(), 0.0)

    @contextlib.contextmanager
    def locked(self):
        """Hold the agent's ledger lock for a whole turn, so concurrent turns
        cannot both pass the cap check or lose each other's spend."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with open(lock_path, "a", encoding="utf-8") as handle:
            os.chmod(lock_path, 0o600)
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def assert_within_cap(self) -> None:
        spent = self.spent_today()
        if spent >= self.daily_cap_usd:
            raise HostError(
                f"daily spend cap reached: {spent:.4f} of {self.daily_cap_usd:.2f} USD"
            )

    def record(self, cost_usd: float) -> None:
        data = self._load()
        today = self.today()
        data[today] = round(data.get(today, 0.0) + cost_usd, 6)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=self.path.parent, delete=False, encoding="utf-8") as handle:
            json.dump(data, handle, sort_keys=True)
            temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)


def run_host(
    prompt: dict[str, Any],
    backend: Any,
    *,
    ledger: SpendLedger | None = None,
    max_attempts: int = 2,
    log: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    system, stable, tail = build_prompt_parts(prompt)
    kind = envelope_kind(prompt.get("response_schema", {}))
    schema = envelope_json_schema(kind)
    started = time.monotonic()
    last_error: Exception | None = None
    guard = ledger.locked() if ledger is not None else contextlib.nullcontext()
    with guard:
        for attempt in range(1, max_attempts + 1):
            if ledger is not None:
                ledger.assert_within_cap()
            try:
                text, usage = backend.complete(system, stable, tail, schema)
            except HostError:
                raise
            except Exception as error:
                # Any backend failure becomes a bounded host error: never a raw
                # traceback, never more than a class name and a short message.
                raise HostError(
                    f"{backend.provider} backend failed: {type(error).__name__}: {str(error)[:200]}"
                ) from None
            if ledger is not None:
                ledger.record(usage.get("cost_usd", 0.0))
            try:
                envelope = json.loads(text)
                if not isinstance(envelope, dict):
                    raise ValueError("model output is not a JSON object")
            except ValueError as error:
                last_error = error
                tail = tail + "\n\nYour previous reply was not a valid JSON object. Reply with only the JSON object."
                continue
            model_config = {"provider": backend.provider, "model": str(usage.get("served_model") or backend.model)}
            fixed = fix_envelope(envelope, prompt, model_config)
            if log is not None:
                log({
                    "event": "model_host_turn", "backend": backend.provider, "model": model_config["model"],
                    "kind": kind, "attempt": attempt, "seconds": round(time.monotonic() - started, 2), **usage,
                })
            return fixed
    raise HostError(f"model produced no valid JSON after {max_attempts} attempts: {type(last_error).__name__}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m experiment4.host", description=__doc__.split("\n\n")[0])
    parser.add_argument("--backend", choices=("ollama", "anthropic"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--secret-ref", default="env:ANTHROPIC_API_KEY",
                        help="op://Vault/Item/field or env:NAME for the anthropic backend")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    parser.add_argument("--ledger", type=Path, help="per-agent spend ledger JSON")
    parser.add_argument("--daily-cap-usd", type=float, default=5.0)
    parser.add_argument("--max-attempts", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    secret = ""
    try:
        prompt = json.loads(sys.stdin.read())
        if args.backend == "ollama":
            backend: Any = OllamaBackend(args.model, args.ollama_url, args.num_ctx)
        else:
            secret = resolve_secret(args.secret_ref)
            backend = AnthropicBackend(args.model, secret)
        ledger = SpendLedger(args.ledger, args.daily_cap_usd) if args.ledger else None
        envelope = run_host(
            prompt, backend, ledger=ledger, max_attempts=args.max_attempts,
            log=lambda record: print(json.dumps({**record, "at": datetime.now(timezone.utc).isoformat()}), file=sys.stderr),
        )
        print(json.dumps(envelope, sort_keys=True))
        return 0
    except Exception as error:  # deliberate: every failure exits 2 with a bounded, redacted line
        message = f"{type(error).__name__}: {str(error)[:500]}"
        if secret:
            message = message.replace(secret, "[REDACTED:api-key]")
        print(json.dumps({"event": "model_host_error", "error": message}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
