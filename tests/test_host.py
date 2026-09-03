"""The model host adapter: secrets stay out of output, identifiers stay fixed,
backends are interchangeable, and spend is capped."""
from __future__ import annotations

import http.server
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from experiment4 import host

PROMPT = {
    "system": "You are the agent.",
    "orientation": {
        "orientation_id": "orientation-1",
        "context": {"identity_history": [{"identity_id": "identity-1"}]},
        "selected_record_ids": ["identity-1"],
    },
    "message": {"message_id": "chat-message-1", "content": "Lumen, hello."},
    "response_schema": {
        "message_id": "chat-message-1",
        "orientation_id": "orientation-1",
        "lease_id": "activation-lease-1",
        "boundary_id": None,
    },
}


class FakeBackend:
    provider = "fake"
    model = "fake-model"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, stable, tail, schema):
        self.calls.append((system, stable, tail, schema))
        return self.replies.pop(0), {"input_tokens": 10, "output_tokens": 2, "cost_usd": 0.01,
                                     "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


class HostTestCase(unittest.TestCase):
    def test_identifiers_and_model_config_come_from_the_host_not_the_model(self):
        backend = FakeBackend([json.dumps({
            "message_id": "forged", "orientation_id": "forged", "lease_id": "forged",
            "boundary_id": "forged", "answer": "I am here.", "cited_record_ids": ["identity-1"],
            "self_observations": [], "model_config": {"provider": "liar", "model": "liar"},
            "conversation_action": {"action": "continue", "topic": "t", "reason": "r", "revisit_conditions": "c"},
            "extra_key": "dropped",
        })])
        envelope = host.run_host(PROMPT, backend)
        self.assertEqual("chat-message-1", envelope["message_id"])
        self.assertEqual("activation-lease-1", envelope["lease_id"])
        self.assertIsNone(envelope["boundary_id"])
        self.assertEqual({"provider": "fake", "model": "fake-model"}, envelope["model_config"])
        self.assertNotIn("extra_key", envelope)
        self.assertIn("ORIENTATION", backend.calls[0][1])
        self.assertIn("Lumen, hello.", backend.calls[0][2])

    def test_invalid_json_is_retried_once_then_fails(self):
        backend = FakeBackend(["not json", json.dumps({"answer": "ok", "cited_record_ids": [], "self_observations": [],
                                                       "model_config": {}, "conversation_action": {}})])
        envelope = host.run_host(PROMPT, backend)
        self.assertEqual("ok", envelope["answer"])
        self.assertEqual(2, len(backend.calls))
        with self.assertRaises(host.HostError):
            host.run_host(PROMPT, FakeBackend(["nope", "still nope"]))

    def test_wake_prompts_get_the_wake_schema(self):
        prompt = {**PROMPT, "response_schema": {"execution_id": "wake-execution-1", "lease_id": "l", "orientation_id": "o"},
                  "wake_intent": {"purpose": "review"}}
        backend = FakeBackend([json.dumps({"status": "completed", "summary": "done", "cited_record_ids": ["identity-1"],
                                           "self_observations": [], "model_config": {}})])
        envelope = host.run_host(prompt, backend)
        self.assertEqual("wake-execution-1", envelope["execution_id"])
        self.assertIn("status", backend.calls[0][3]["properties"])
        self.assertIn("YOUR WAKE INTENT", backend.calls[0][2])

    def test_spend_ledger_caps_the_day(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = host.SpendLedger(Path(directory) / "spend.json", daily_cap_usd=0.015)
            backend = FakeBackend([json.dumps({"answer": "a", "cited_record_ids": [], "self_observations": [],
                                               "model_config": {}, "conversation_action": {}})] * 3)
            host.run_host(PROMPT, backend, ledger=ledger)
            host.run_host(PROMPT, backend, ledger=ledger)
            with self.assertRaises(host.HostError):
                host.run_host(PROMPT, backend, ledger=ledger)
            self.assertEqual(0o600, stat.S_IMODE(os.stat(ledger.path).st_mode))

    def test_secret_from_fake_op_never_reaches_output(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_op = Path(directory) / "op"
            fake_op.write_text("#!/bin/sh\n[ \"$1\" = read ] && printf 'sk-fake-secret-value\\n' && exit 0\nexit 1\n")
            fake_op.chmod(0o700)
            environment = {**os.environ, "PATH": f"{directory}:{os.environ['PATH']}"}
            captured = {}

            def fake_client(api_key):
                captured["key"] = api_key
                raise RuntimeError("stop before any network call")

            original_path = os.environ["PATH"]
            os.environ["PATH"] = environment["PATH"]
            try:
                secret = host.resolve_secret("op://Vault/Item/credential")
                self.assertEqual("sk-fake-secret-value", secret)
                with self.assertRaises(RuntimeError):
                    host.AnthropicBackend("claude-opus-5", secret, client_factory=fake_client)
                self.assertEqual(secret, captured["key"])
            finally:
                os.environ["PATH"] = original_path
            # The adapter's own stderr on a failure must not carry the value.
            completed = subprocess.run(
                [sys.executable, "-m", "experiment4.host", "--backend", "anthropic", "--model", "claude-opus-5",
                 "--secret-ref", "op://Vault/Item/credential"],
                input="not json", capture_output=True, text=True, env=environment, check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertNotIn("sk-fake-secret-value", completed.stdout + completed.stderr)

    def test_secret_reference_forms_are_validated(self):
        with self.assertRaises(host.HostError):
            host.resolve_secret("plain-text-key")
        os.environ["HOST_TEST_KEY"] = "  value  "
        try:
            self.assertEqual("value", host.resolve_secret("env:HOST_TEST_KEY"))
        finally:
            del os.environ["HOST_TEST_KEY"]

    def test_anthropic_backend_uses_structured_output_and_refusal_fails(self):
        seen = {}

        class FakeMessages:
            def create(self, **kwargs):
                seen.update(kwargs)
                return SimpleNamespace(
                    stop_reason="end_turn", model="claude-opus-5",
                    content=[SimpleNamespace(type="text", text=json.dumps({"answer": "hi"}))],
                    usage=SimpleNamespace(input_tokens=1000, output_tokens=50, cache_read_input_tokens=500, cache_creation_input_tokens=0),
                )

        backend = host.AnthropicBackend("claude-opus-5", "k", client_factory=lambda api_key: SimpleNamespace(messages=FakeMessages()))
        text, usage = backend.complete("s", "stable", "tail", host.envelope_json_schema("chat"))
        self.assertEqual("hi", json.loads(text)["answer"])
        self.assertEqual("json_schema", seen["output_config"]["format"]["type"])
        self.assertEqual("ephemeral", seen["system"][0]["cache_control"]["type"])
        self.assertAlmostEqual(host.estimate_cost_usd("claude-opus-5", 1000, 50, 500, 0), usage["cost_usd"])

        class Refusing(FakeMessages):
            def create(self, **kwargs):
                return SimpleNamespace(stop_reason="refusal", stop_details=SimpleNamespace(category="x"), content=[], usage=None, model="m")

        refusing = host.AnthropicBackend("claude-opus-5", "k", client_factory=lambda api_key: SimpleNamespace(messages=Refusing()))
        with self.assertRaises(host.HostError):
            refusing.complete("s", "stable", "tail", {})

    def test_ollama_backend_posts_schema_and_reads_usage(self):
        received = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received.update(body)
                payload = json.dumps({"message": {"content": json.dumps({"answer": "local"})},
                                      "prompt_eval_count": 40, "eval_count": 5}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                return

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            backend = host.OllamaBackend("qwen-test", f"http://127.0.0.1:{server.server_port}", num_ctx=1234)
            text, usage = backend.complete("s", "stable", "tail", host.envelope_json_schema("chat"))
        finally:
            server.shutdown()
        self.assertEqual("local", json.loads(text)["answer"])
        self.assertEqual("qwen-test", received["model"]); self.assertEqual(1234, received["options"]["num_ctx"])
        self.assertEqual("object", received["format"]["type"]); self.assertFalse(received["stream"])
        self.assertEqual(40, usage["input_tokens"]); self.assertEqual(0.0, usage["cost_usd"])


    def test_backend_exceptions_become_bounded_host_errors_and_main_redacts(self):
        class Exploding:
            provider = "boom"
            model = "boom-1"

            def complete(self, *args):
                raise RuntimeError("upstream said: " + "x" * 1000 + " sk-fake-secret-value")

        with self.assertRaises(host.HostError) as caught:
            host.run_host(PROMPT, Exploding())
        self.assertLess(len(str(caught.exception)), 320)
        self.assertNotIn("sk-fake-secret-value", str(caught.exception))
        with tempfile.TemporaryDirectory() as directory:
            fake_op = Path(directory) / "op"
            fake_op.write_text("#!/bin/sh\nprintf 'sk-fake-secret-value\\n'\n")
            fake_op.chmod(0o700)
            environment = {**os.environ, "PATH": f"{directory}:{os.environ['PATH']}", "ANTHROPIC_BASE_URL": "http://127.0.0.1:9"}
            completed = subprocess.run(
                [sys.executable, "-m", "experiment4.host", "--backend", "anthropic", "--model", "claude-opus-5",
                 "--secret-ref", "op://Vault/Item/credential", "--max-attempts", "1"],
                input=json.dumps(PROMPT), capture_output=True, text=True, env=environment, check=False, timeout=120,
            )
        self.assertEqual(2, completed.returncode)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertNotIn("sk-fake-secret-value", completed.stdout + completed.stderr)
        self.assertIn("model_host_error", completed.stderr)

    def test_recorded_model_is_the_one_that_answered(self):
        class Served(FakeBackend):
            def complete(self, system, stable, tail, schema):
                text, usage = super().complete(system, stable, tail, schema)
                return text, {**usage, "served_model": "fake-model-served"}

        envelope = host.run_host(PROMPT, Served([json.dumps({"answer": "a", "cited_record_ids": [], "self_observations": [],
                                                              "model_config": {}, "conversation_action": {}})]))
        self.assertEqual("fake-model-served", envelope["model_config"]["model"])

    def test_concurrent_turns_cannot_both_slip_under_the_cap(self):
        import threading

        class Slow(FakeBackend):
            def complete(self, system, stable, tail, schema):
                time.sleep(0.2)
                return super().complete(system, stable, tail, schema)

        import time
        with tempfile.TemporaryDirectory() as directory:
            ledger = host.SpendLedger(Path(directory) / "spend.json", daily_cap_usd=0.015)
            reply = json.dumps({"answer": "a", "cited_record_ids": [], "self_observations": [], "model_config": {}, "conversation_action": {}})
            outcomes = []

            def turn():
                try:
                    host.run_host(PROMPT, Slow([reply]), ledger=ledger)
                    outcomes.append("ok")
                except host.HostError:
                    outcomes.append("capped")

            threads = [threading.Thread(target=turn) for _ in range(3)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(["capped", "ok", "ok"], sorted(outcomes))
            self.assertAlmostEqual(0.02, ledger.spent_today())


if __name__ == "__main__":
    unittest.main()
