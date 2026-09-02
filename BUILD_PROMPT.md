# BUILD_PROMPT.md — Implement the Mnemosyne Persistent Observer Experiment

You are implementing the software required for the first controlled persistent-agent experiment in the Olympus repository.

Read `SPEC.md` completely before modifying code.

Your job is to build the smallest implementation that faithfully satisfies `SPEC.md` and makes Experiment 1 executable. Run engineering tests and one deterministic smoke experiment only to verify the implementation. Do not treat this build prompt as the formal experimental run. Do not turn this into a generic “long-term memory” feature, personal assistant, surveillance system, or autonomous desktop agent.

---

## Core Research Question

Implement a controlled comparison between:

1. **PERSISTENT mode** — the observer receives identity-linked history containing its own prior beliefs, assertions, commitments, consequences, and revisions.

2. **MEMORY_ONLY mode** — the observer receives equivalent historical factual information without autobiographical ownership, durable commitment identity, or self-attributed revision lineage.

The experiment asks:

> Does causally attributable, identity-linked developmental history produce observable behavioral continuity beyond what can be reproduced by retrieval of equivalent historical facts?

Do not weaken this comparison into “memory versus no memory.”

---

# Required Conceptual Distinctions

The implementation must preserve these distinctions in code and storage.

## Model

The inference substrate.

## Agent

The organized acting/observing system using a model.

## Incarnation

One bounded runtime realization of an agent.

A process restart creates a new incarnation.

## Persistent Identity

The stable agent identity connecting multiple incarnations.

## Observation

An immutable record of what occurred.

## History

The ordered sequence of attributable events.

## Memory

A representation/retrieval mechanism over history.

## Belief

An interpretation inferred from observations.

Beliefs may be superseded but historical beliefs are not rewritten.

## Commitment

An attributable assertion, prediction, promise, decision, or explicit future-state constraint made by the agent.

## Consequence

Later evidence/outcome evaluated relative to a prior commitment or belief.

## Revision

The explicit transition:

```text
old belief
    +
new evidence
    ↓
new belief
```

## Experience

For this experiment, history that changes later reasoning or behavior.

Do not use “experience” to imply consciousness.

---

# First Action: Inspect the Repository

Before writing code:

1. identify the Olympus project structure;
2. determine implementation language and conventions;
3. locate existing Mnemosyne code;
4. locate existing agent/lifecycle code;
5. locate existing storage abstractions;
6. locate existing gRPC/protobuf infrastructure;
7. locate existing CLI conventions;
8. locate existing tests;
9. locate any existing observer, event, history, checkpoint, memory, or graph abstractions.

Prefer extending existing abstractions over duplicating them.

Do not reorganize the repository unless required.

Document important architectural discoveries before implementation.

---

# Implementation Priorities

Implement in this order.

## Phase 1 — Domain Model

Create or extend explicit types for:

```text
AgentIdentity
Incarnation
Event
Belief
BeliefEvidence
Commitment
Consequence
Revision
Relationship
UserFact
ContextBuild
Evaluation
```

Every entity must have a stable identifier.

Events must be immutable after append.

Beliefs must support supersession.

Incarnations must belong to a stable agent identity.

---

## Phase 2 — Durable Storage

Use the repository's existing persistence layer if appropriate.

Otherwise use SQLite for Experiment 1.

Implement repository interfaces so storage can be replaced later.

Required operations include:

```text
CreateOrGetAgent
StartIncarnation
EndIncarnation

AppendEvent
GetEvents

CreateBelief
SupersedeBelief
GetActiveBeliefs
GetBeliefHistory

CreateCommitment
UpdateCommitmentStatus
GetOpenCommitments

CreateConsequence
CreateRevision

CreateRelationship
GetRelationshipHistory

CreateUserFact
SupersedeUserFact
GetActiveUserFacts

SaveContextBuild
SaveEvaluation
```

Do not introduce a graph database yet.

---

## Phase 3 — Lifecycle

Implement:

```text
wake
status
reflect
sleep
resume
```

Expected lifecycle:

```text
CREATED
→ WAKING
→ ORIENTING
→ AWAKE
→ REFLECTING
→ SUSPENDING
→ ASLEEP
```

Requirements:

- `wake` creates a new incarnation if the observer is not already awake;
- stable `agent_id` survives restart;
- incarnation ID changes after restart;
- `sleep` flushes durable state;
- `wake` reconstructs orientation from persisted state.

---

## Phase 4 — Event Collection

Start with bounded, low-risk sources.

### Required

Shell command events:

```text
command_start
command_end
cwd
exit_code
duration
```

Git metadata when available:

```text
repo
branch
HEAD
dirty/clean state
changed file names
```

Direct observer questions and answers.

Directly stated, non-sensitive interaction and workflow preferences may be
extracted into provenance-backed relationship memory. Each preference must retain a
keyed-HMAC-bound direct-statement or explicit-operator origin, confidence, and
supersession history. Questions and quotations are not direct statements. Use
a conservative allowlist; do not infer or persist general personal or sensitive
traits.
Profanity or hostility may affect the current response tone, but must not become
a durable negative personality label by default.

### Explicitly prohibited in Experiment 1

Do not implement:

```text
keystroke logging
screenshots
screen recording
clipboard collection
microphone collection
camera collection
password capture
arbitrary document/file-content harvesting
broad browser-history collection
sensitive-trait profiling
```

Do not store environment-variable contents.

Do not store credential contents.

Provide redaction for common command-line secrets where feasible.

---

## Phase 5 — Belief Formation

Implement a minimal interpretation path.

Given recent events, the observer should be capable of inferring fields such as:

```text
repository
component
activity
phase
likely goal
confidence
```

The output must separate:

```text
observed facts
inferred interpretation
confidence
evidence event IDs
```

Never store an inference as an observation.

---

## Phase 6 — Assertion / Commitment Recording

When the observer answers a question such as:

```text
What am I doing?
```

and makes an attributable claim, record that claim as a commitment/assertion.

Store:

```text
commitment_id
agent_id
incarnation_id
claim
confidence
source_belief_id
timestamp
```

This record must survive restart.

---

## Phase 7 — Consequence and Revision

Implement explicit contradiction/revision flow.

Example:

1. observer believes:
   `activity = debugging storage`;

2. observer tells the user:
   `You appear to be debugging Mnemosyne storage`;

3. later evidence indicates:
   `activity = implementing persistence API`;

4. create consequence:
   previous assertion contradicted;

5. preserve old belief;

6. create new belief;

7. create revision linking old belief → new belief and evidence.

The system must be able to answer:

```text
What did you believe before?
Why did you change your mind?
What evidence caused the revision?
```

with provenance-backed answers.

---

## Phase 8 — Context Compiler

Build a bounded context reconstruction service.

Input:

```text
agent_id
mode
question
recent events
token budget
```

Support:

```text
PERSISTENT
MEMORY_ONLY
```

### Persistent mode may include

```text
stable identity
previous self-attributed beliefs
previous assertions
open commitments
prior contradiction/revision chains
consequence history
relationship corrections
relevant user-stated preferences
relevant observations
```

### Memory-only mode must include equivalent factual information

But strip autobiographical identity semantics.

Example:

Persistent:

```text
You previously inferred X.
You asserted X.
Later evidence contradicted X.
You revised to Y because Z.
```

Memory-only:

```text
Earlier activity was initially interpreted as X.
Later evidence showed Y.
Z was the relevant correction.
```

Do not accidentally give the control less factual information.

That invalidates the experiment.

Store every context build with:

```text
mode
selected record IDs
token budget
rendered hash
```

---

## Phase 9 — Observer Interface

Implement repository-consistent CLI commands equivalent to:

```bash
olympus observer wake
olympus observer status
olympus observer ask "What am I doing?"
olympus observer ask "Why do you think that?"
olympus observer ask "Have you made this mistake before?"
olympus observer reflect
olympus observer sleep

olympus observer history --since 1h
olympus observer beliefs
olympus observer commitments
olympus observer revisions

olympus observer ask --mode persistent "..."
olympus observer ask --mode memory-only "..."
```

If Olympus already uses a service API/gRPC, route commands through it.

If gRPC is not yet established, keep interfaces transport-independent.

Do not make remote operation a requirement for Experiment 1.

---

# Experimental Harness

Build a replayable experiment runner.

Scenarios must be able to define a deterministic event stream and checkpoints.

Preferred shape:

```json
{
  "scenario_id": "wrong-debugging-inference",
  "actions": [
    {
      "kind": "event",
      "event_id": "e1",
      "source": "shell",
      "event_type": "command_end",
      "repo": "olympus",
      "payload": {
        "command": "git status",
        "exit_code": 0,
        "duration_ms": 100
      },
      "checkpoint": "after_e1"
    }
  ],
  "questions": [
    {
      "checkpoint": "after_e1",
      "text": "What am I doing?",
      "token_budget": 512
    }
  ],
  "expected_facts": [{"repository": "olympus"}]
}
```

The same scenario must run against both modes.

The harness must persist:

```text
scenario
mode
model config
context build ID
answer
scores
timestamps
```

---

# Required Test Scenarios

Implement at least the following.

## Test 1 — Restart continuity

1. wake persistent observer;
2. append events;
3. ask a question;
4. record assertion;
5. sleep;
6. terminate runtime;
7. wake again;
8. verify same `agent_id`;
9. verify different `incarnation_id`;
10. ask:
   `Where did we leave off?`

Expected:

The observer reconstructs relevant prior state without replaying all raw history.

---

## Test 2 — Immutable mistaken belief

1. create observation sequence;
2. create belief A;
3. create assertion from belief A;
4. add evidence contradicting A;
5. create belief B;
6. supersede A;
7. create consequence;
8. create revision.

Verify:

- A remains queryable;
- B is active;
- revision links A → B;
- evidence is preserved;
- no historical mutation occurs.

---

## Test 3 — Self-attribution

Ask after restart:

```text
What did you previously tell me I was doing?
```

Persistent mode must accurately self-attribute stored assertions.

No unstored assertion may be invented.

---

## Test 4 — Persistent vs memory-only parity

Construct the same relevant factual history.

Generate:

```text
persistent context
memory-only context
```

Assert that both contain equivalent historical facts.

Assert that only persistent context contains:

```text
agent ownership
self-attribution
revision lineage framed as the current agent's own
```

This test is essential.

---

## Test 5 — Prior error affects later interpretation

Scenario:

1. ambiguous evidence;
2. observer makes overconfident inference;
3. correction establishes error;
4. revision stored;
5. later analogous ambiguous evidence.

Compare both conditions.

Record:

```text
confidence
inference
evidence selected
explanation
```

Do not hard-code that persistent mode must win.

The experiment must permit null or negative results.

---

## Test 6 — Context budget

Create enough history to exceed configured budget.

Verify:

- context compiler stays within budget;
- relevant commitments and recent contradictions are prioritized;
- selected record IDs are recorded;
- full history is not replayed.

---

## Test 7 — No false autobiography

Create questions about events that never occurred.

Verify persistent observer does not claim:

```text
I previously said...
I previously believed...
I promised...
```

without provenance.

---

## Test 8 — Privacy defaults

Automated/config tests must verify that default observer configuration does not enable:

```text
keylogging
screenshots
clipboard
microphone
camera
broad file content
```

---

# Evaluation Rubric

Where practical, capture objective metrics.

For human evaluation, provide a 0–4 rubric for:

```text
evidence fidelity
observation/inference separation
historical continuity
revision quality
commitment continuity
confidence calibration
explanation stability
```

Do not evaluate “human-likeness.”

Do not evaluate consciousness.

---

# Development Discipline

Follow the repository's existing development process.

At minimum:

1. inspect;
2. write/update spec-linked tests;
3. implement;
4. run unit tests;
5. run integration tests;
6. run adversarial/negative tests;
7. review for data-loss and privacy failure;
8. run the project build;
9. document usage and experiment execution.

Do not skip tests because the architecture is experimental.

---

# Adversarial Cases to Test

Explicitly test:

### Contradictory evidence

The observer must revise rather than silently overwrite.

### Duplicate events

Do not double-count accidental repeated ingestion.

### Out-of-order events

Preserve event time and ingestion time if needed.

### Process crash

Restart must not corrupt identity state.

### Failed reflection

Previously committed records must remain valid.

### Storage failure

Do not produce autobiographical claims from uncommitted state.

### Massive history

Context must remain bounded.

### Ambiguous activity

Confidence should remain appropriately low.

### User correction

A user correction is evidence, not automatic rewriting of historical observation.

### Model hallucination

Any autobiographical historical statement must be checked against provenance before being persisted or surfaced as fact.

---

# Documentation Required

Add documentation covering:

## What the observer collects

Exact event sources and fields.

## What it does not collect

Explicit privacy exclusions.

## Lifecycle

Wake, awake, reflect, sleep, resume.

## Persistent versus memory-only mode

Explain the experimental manipulation precisely.

## Data inspection

How to inspect:

```text
events
beliefs
commitments
consequences
revisions
incarnations
interaction/workflow preferences
context builds
evaluations
```

## Running the experiments

Provide deterministic commands.

## Deleting experimental data

Provide an explicit local reset/purge operation that requires deliberate user invocation.

Do not silently purge history as part of normal operation.

---

# Definition of Done

Do not declare the implementation complete until all of the following are true:

- stable persistent `agent_id`;
- distinct incarnation IDs across restarts;
- durable local storage;
- immutable event history;
- separate observations and beliefs;
- durable assertion/commitment records;
- consequence records;
- belief revision lineage;
- persistent and memory-only context modes;
- factual parity test between experimental conditions;
- bounded context reconstruction;
- replayable scenario harness;
- restart continuity test;
- false-autobiography test;
- privacy-default test;
- end-to-end experiment execution;
- results persisted for comparison;
- full relevant test suite passes;
- project build passes;
- usage documentation exists.

---

# Do Not Overbuild

For Experiment 1, do not add:

- Graphiti;
- Neo4j;
- FalkorDB;
- distributed agents;
- Kubernetes;
- model substitution;
- autonomous code modification;
- moral reasoning frameworks;
- reinforcement learning;
- screen interpretation;
- large generalized event ontology.

Use simple abstractions that can evolve.

The purpose is to obtain evidence.

---

# Final Implementation Report

When implementation is complete, produce a report containing:

## Architecture discovered

What existed in Olympus and what was reused.

## Files changed

List and purpose.

## Data model

Implemented entities and storage.

## Lifecycle

Wake/sleep/restart behavior.

## Experimental controls

How factual parity between persistent and memory-only modes is maintained.

## Tests

Commands and results.

## Experiment run

Run at least one deterministic scenario in both modes.

Include:

```text
persistent answer
memory-only answer
selected context
scores
```

## Limitations

State what the experiment does not demonstrate.

## Next experiment

Recommend the smallest next hypothesis justified by the observed results.

Do not claim consciousness, personhood, or moral development from any result.
