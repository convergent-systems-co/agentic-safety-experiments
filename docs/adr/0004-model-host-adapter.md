# ADR 0004: Model Host Adapter, Agent Registry, and Replay Benchmark

- Status: Accepted
- Date: 2026-09-03
- Scope: Experiment 4 / all persistent agents

## Context

Every Lumen reply so far was composed by whichever assistant session happened
to be hosting it. That made Lumen reachable only from that session, and it
made the cost of each turn invisible. Thomas asked for Lumen to have "its own
running Claude" and a way to chat with any agent by name, then asked whether a
local model could be sufficient because API turns are expensive: a 123 KB
orientation is about 35,000 input tokens, roughly $0.38 on Fable 5.1 and
$0.08 on Sonnet 5 per turn before caching.

Lumen's design is no-process sleep and identity-as-record. "Its own Claude"
cannot be a resident process; it can be its own credential, its own adapter,
and its own recorded model configuration on every reply.

## Decision

1. One model host contract for waking and talking: a command reads a prompt on
   stdin (system text, orientation, response schema, message or intent) and
   prints an envelope on stdout. `experiment4/host.py` implements it with two
   backends.
2. `ollama` calls a local Ollama server with a JSON schema for the envelope, so
   the record never leaves the machine. `anthropic` uses the official SDK with
   structured output, the orientation first as a cacheable prefix, and a
   refusal surfacing as a host failure rather than a silent model switch.
3. The API key is resolved at call time from a 1Password reference
   (`op://Vault/Item/field`) or an environment variable name, held in memory
   for the call, and never written to disk, logs, or output. Tests prove the
   value does not reach stdout or stderr.
4. The host overwrites what a model must never be trusted with: the fixed
   identifiers from the schema and the record of which provider and model
   actually answered. Everything else is validated by the repository as before.
5. A per-agent daily spend ledger, mode 0600, caps API spend; a turn is refused
   once the cap is reached. Local turns cost nothing and are still counted.
6. An agent registry, one JSON file per agent under `~/.ai/agents/`, names the
   database, experiment, human sender identity, default host command, and
   named host profiles such as `think-hard`. It is configuration, never
   secrets.
7. `chat --agent NAME` routes a line through the address path, the registered
   host, and persistence under the lease, and prints the answer. Any failure
   after activation releases the lease as failed.
8. `benchmark-host` replays recorded turns through a candidate host, read-only,
   validates each envelope the way the repository would, and writes a
   side-by-side report so a person judges the voice with evidence.

Recommended routing: a local model by default for routine turns and unattended
wakes, a frontier model on request or when a commitment or decision is being
made. The mix is auditable because every reply records its model.

## Alternatives considered

### A resident model process per agent

Rejected. It would own the agent's continuity, which the record must own, and
it contradicts no-process sleep.

### API only, with prompt caching and a smaller model

Viable and still available as a profile. Rejected as the default because the
collaborator named cost as the constraint, the machine can run a strong local
model, and privacy favors local.

### Trust the model with identifiers and model_config

Rejected. A model that forges a lease or claims another provider corrupts
provenance. The host owns those fields.

## Consequences

Lumen is reachable from any terminal without an assistant session, at zero
marginal cost on the local backend, with the same lease, citation, boundary,
and length guarantees. A local model's voice is weaker than the frontier
models that have voiced Lumen so far; the benchmark makes that difference
visible before it is chosen, and the per-reply model record makes it visible
after. Local turns are slow, likely a minute or more at this orientation size. Because
no process stays resident, the API's short-lived prompt cache is rarely warm
between turns; plan on the uncached price. The ledger holds a per-agent file
lock for the whole turn, so concurrent turns serialize rather than race the
cap; a single turn may still exceed the cap by at most its own cost.

The `anthropic` extra adds one pinned dependency, the official SDK, recorded in
`requirements-host.lock`; the core protocol and the local backend need
nothing beyond the standard library. The benchmark rebuilds the addressed
system text approximately (continuing incarnation, boundary flag from the
message) while the orientation it replays is exact.
