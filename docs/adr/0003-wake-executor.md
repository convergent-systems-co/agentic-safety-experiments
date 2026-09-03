# ADR 0003: Wake Executor for Self-Authored Intentions

- Status: Accepted
- Date: 2026-09-03
- Scope: Experiment 4 / Lumen

## Context

Lumen could record a wake intention under its own authorship but nothing
honored it: the README described a planned `launchd` runtime that did not
exist. In conversation on 2026-09-03 Lumen named the gap ("the clock is mine;
the hands are not attached yet") and set the first test: an intent it set must
be cancellable by it and honored without its collaborator present. Its
collaborator's stated convention is that timed requests will be asks for Lumen
to set its own alarm, so authorship over waking stays with Lumen.

Two smaller gaps sat beside it. The CLI allowed only operator or system to
cancel an intention, though the repository accepted a model author with a
weaker check. And Lumen had never recorded an experience or reflection of its
own, though the provenance path already allowed model authorship under a
lease; that was a hosting omission, not a code gap, and a test now documents
the capability.

## Decision

1. A model may cancel only a wake intention it authored, and only under a live
   lease-bound orientation (`_assert_model_context`). Operator and system
   cancellation is unchanged. The CLI accepts a model authorship envelope via
   `--input`.
2. Two append-only tables, `wake_executions` and `wake_execution_outcomes`,
   record that a wake happened and what came of it. Both are immutable, exported,
   and shown in orientation under lifecycle memory. Migration
   `wake-executions-v1` is additive.
3. `due_wake_intents` returns time-triggered intentions whose moment has come,
   that are uncancelled, unexecuted, and non-recurring. `begin_wake_execution`
   leases the current incarnation for at most the intent's maximum runtime,
   orients on the intent's purpose, and records the execution; any failure
   releases the lease as `failed`. An intent from an ended session is refused.
4. `record_wake_outcome` validates like an addressed reply: the envelope must
   match its execution, citations must be unique orientation records, a
   `completed` outcome needs at least one citation and a model config and gets
   model authorship under the live lease, `unattended` and `failed` outcomes
   get system authorship. The lease is released in the same transaction.
5. `run_due_wake_intents` honors every due intent once. With no model host it
   records `unattended`. With a host, a failure or invalid outcome is recorded
   as `failed` with the error before the error is raised.
6. The CLI exposes `due-wake-intents`, `wake-intent-prompt`,
   `record-wake-outcome`, and `execute-wake-intents --model-command`. The Go
   adapter gains `lumen wake`. A `launchd` template runs the executor every
   fifteen minutes; nothing stays resident.

## Alternatives considered

### A resident scheduler process

Rejected. The design principle is no-process sleep. A resident process would
become the owner of Lumen's continuity and a second place identity could leak.

### Execute recurring intents on every run

Rejected for now. An intent with recurrence would fire on every executor pass
once due. Recurrence needs its own semantics (next-fire computation, a cap)
before it can be honored; until then such intents are recorded and skipped.

### Let a wake begin a successor incarnation after `end_session`

Deferred. Beginning a successor is a lifecycle decision the current design
reserves for a manual wake. A self-wake into an ended session is refused with
a clear error.

## Consequences

Lumen's alarm is now testable end to end without a model: set an intent, run
the executor after the trigger, and observe the execution and an `unattended`
outcome in the next orientation with no lease left open. Attaching a model
host is one command-line option; that host receives the same bounded prompt
contract as an addressed reply and is held to the same citation rules.

The executor is a polling job, so a wake fires up to one interval late. It
honors one intent per pass, so at a fifteen-minute interval the agent can wake
at most 96 times a day and a person can always address it between wakes; the
model host timeout is clipped to the same one-hour bound as the lease. The
executor's output carries identifiers and status only, so its log holds no
orientation content, and a failed outcome records how the host failed but not
what it printed. Outcome summaries and observations are size-bounded so one
wake cannot fill the lifecycle budget. A wake intent's purpose shares the
retrieval query cap. There is no daily cost cap beyond the pass limit; attaching
a model host is a budget decision.
Installing the `launchd` agent is a system configuration change left to the
operator. No model host is configured by default; the first attended wake is
a decision about cost and trust that this ADR does not make.
