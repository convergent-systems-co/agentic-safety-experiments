# SPEC.md — Mnemosyne Persistent Observer Experiment

## 1. Purpose

Build a minimal, local experimental agent inside Olympus that tests whether **identity-linked historical continuity** produces measurably different behavior from **ordinary memory retrieval** when both systems have access to equivalent factual history.

This experiment is grounded in the project’s Temporal and Relational thesis:

- **memory** is retained or retrievable representation of prior information;
- **history** is the actual sequence of attributable events;
- **experience** is history incorporated into future agency;
- **persistence** is not equivalent to storage;
- **identity continuity** requires earlier actions, assertions, commitments, and consequences to remain attributable to a later incarnation of the same agent;
- **model**, **agent**, **incarnation/session**, and **persistent identity** are distinct objects.

The experiment does **not** attempt to establish consciousness, personhood, moral agency, or sentience.

The research target is narrower:

> Does causally attributable, identity-linked developmental history produce observable behavioral continuity beyond what can be reproduced by retrieval of equivalent historical facts?

---

## 2. Primary Hypothesis

### H1 — Identity-linked historical continuity changes behavior

An agent that retains identity-linked history containing its own prior beliefs, assertions, commitments, errors, consequences, and revisions will exhibit greater diachronic behavioral continuity than an otherwise equivalent agent receiving ordinary retrieved historical information.

### Independent variable

Persistence mode:

1. **Persistent Observer (PERSISTENT)**  
   Receives a reconstructed identity-linked history.

2. **Control Observer (MEMORY_ONLY)**  
   Receives equivalent historical facts, but not autobiographical attribution, durable commitments, revision lineage, or identity-linked consequence state.

### Controlled variables

The experiment MUST hold the following constant where technically possible:

- underlying model and model version;
- system/persona prompt other than persistence-mode instructions;
- current machine-event stream;
- task/question;
- token budget;
- temperature/sampling settings;
- tool availability;
- relevant historical factual content;
- evaluation timing.

### Dependent measures

Measure:

- prior-error recognition;
- commitment recognition;
- contradiction detection;
- confidence calibration;
- belief-revision quality;
- prediction quality;
- explanation stability;
- ability to distinguish observation from inference;
- consequence-sensitive future judgment;
- continuity after process termination and restart.

---

## 3. Non-Goals

Version 1 MUST NOT attempt:

- consciousness claims;
- sentience detection;
- moral development;
- unrestricted autonomous action;
- full-screen capture;
- keystroke logging;
- clipboard capture;
- microphone or camera monitoring;
- arbitrary filesystem surveillance;
- model swapping;
- long-running multi-agent orchestration;
- Graphiti/Neo4j/FalkorDB dependency;
- fine-tuning;
- reinforcement learning;
- modification of the user’s files based on inferred intent;
- execution of commands on the user’s behalf except explicit observer lifecycle commands.

These may become later experiments only after the base hypothesis is measurable.

---

## 4. Design Principles

### 4.1 History is append-only

Observed events are immutable.

An interpretation may be revised, superseded, or contradicted, but prior observations and prior beliefs MUST NOT be silently rewritten.

### 4.2 Observation and interpretation are separate

The system MUST distinguish:

- what actually occurred;
- what the observer inferred;
- what the observer asserted;
- what later evidence showed;
- what changed in the observer’s belief state.

### 4.3 Memory is not identity

The control condition MUST still receive relevant historical information.

A comparison between “memory” and “no memory” does not test the thesis.

### 4.4 Process termination is not identity termination

A persistent agent may have multiple runtime incarnations.

The `agent_id` remains stable across process restarts.

Each runtime receives a new `incarnation_id`.

### 4.5 History must be attributable

The persistent observer must be able to represent:

- “I previously inferred X.”
- “I told the user X.”
- “Later evidence contradicted X.”
- “I revised X to Y.”
- “That error should affect how I interpret similar evidence now.”

### 4.6 The agent must not fabricate autobiographical history

Every historical self-reference MUST be traceable to stored records.

### 4.7 Retrieval must be bounded

The implementation MUST reconstruct a minimum sufficient historical context rather than replay all prior activity.

### 4.8 Privacy by construction

The experiment observes only explicitly configured event sources.

Version 1 allows explicit shell events, opportunistic Git metadata, and direct
observer conversations. Process/application monitoring is not implemented.

---

# 5. System Overview

```text
                    Local Machine
                         │
         ┌───────────────┼────────────────┐
         │               │                │
      Shell Input     Git State      Direct Interaction
         │               │                │
         └───────────────┼────────────────┘
                         │
                  Event Collector
                         │
                         ▼
                    Mnemosyne
              ┌──────────┼──────────┐
              │          │          │
          Event Store  Identity   Retrieval
              │          │          │
              │       Beliefs       │
              │       Commitments   │
              │       Revisions     │
              │       Consequences  │
              └──────────┼──────────┘
                         │
                  Context Compiler
                  /               \
                 /                 \
                ▼                   ▼
       Persistent Observer    Memory-Only Control
                │                   │
                └─────────┬─────────┘
                          ▼
                      Evaluator
```

---

# 6. Recommended Implementation Shape

Target the existing Olympus repository conventions.

If the repository is Go-based, implement the first version in Go.

Suggested logical components:

```text
cmd/
  olympus-observer/

internal/
  observer/
    collector/
    lifecycle/
    evaluator/
  mnemosyne/
    events/
    identity/
    beliefs/
    commitments/
    consequences/
    retrieval/
    context/
    storage/

proto/
  olympus/
    mnemosyne/
    observer/
```

Do not reorganize the repository merely to match this example. Follow existing project structure where equivalent packages already exist.

---

# 7. Storage

## 7.1 Initial backend

Use SQLite unless Olympus already provides an appropriate local persistence abstraction.

Requirements:

- local-first;
- durable across process restart;
- simple to inspect;
- transactional;
- no external service required for Experiment 1.

The persistence interface MUST be abstract enough to permit a future temporal graph backend.

## 7.2 Minimum tables / entities

### agents

```text
agent_id
name
persona
created_at
status
```

### incarnations

```text
incarnation_id
agent_id
model_provider
model_name
started_at
ended_at
termination_reason
```

### events

Immutable machine/user observations.

```text
event_id
timestamp
source
event_type
payload_json
cwd
repo
branch
correlation_id
```

### beliefs

```text
belief_id
agent_id
created_at
subject
predicate
object
confidence
status
supersedes_belief_id
```

Status examples:

```text
active
superseded
contradicted
withdrawn
```

### belief_evidence

```text
belief_id
event_id
weight
```

### commitments

A commitment is any identity-attributable assertion, prediction, promise, decision, or explicit future-state constraint.

```text
commitment_id
agent_id
created_at
commitment_type
claim
confidence
status
source_belief_id
```

Status examples:

```text
open
fulfilled
contradicted
revised
withdrawn
expired
```

### consequences

```text
consequence_id
agent_id
created_at
commitment_id
result_type
description
evidence_event_ids
```

### revisions

```text
revision_id
agent_id
created_at
old_belief_id
new_belief_id
reason
evidence_event_ids
```

### relationships

Version 1 needs only the observer/user relationship.

```text
relationship_id
agent_id
counterparty_id
created_at
status
```

### relationship_events

```text
relationship_id
event_id
relation_type
```

### user_facts

Conservatively allowlisted, non-sensitive interaction/workflow preferences
directly stated by the user.

```text
user_fact_id
agent_id
counterparty_id
created_at
category
origin
fact
confidence
status
source_event_id
supersedes_user_fact_id
```

These records require a keyed-HMAC-bound direct-statement or explicit-operator
provenance event and support supersession without rewriting prior records.
Deletion destroys the per-preference HMAC key.
Questions, quotations, and speculative text are not direct statements. The
system MUST NOT infer or persist general personal facts,
credentials, sensitive traits, or durable negative personality labels from
conversational tone.

### context_builds

Used for reproducibility.

```text
context_build_id
agent_id
mode
created_at
query
token_budget
selected_record_ids
rendered_context_hash
```

### evaluations

```text
evaluation_id
scenario_id
agent_id
mode
question
answer
scores_json
created_at
```

---

# 8. Event Model

## 8.1 Event envelope

All observations use a common envelope.

```json
{
  "event_id": "E-1042",
  "timestamp": "2026-08-31T15:08:14-05:00",
  "source": "shell",
  "event_type": "command_end",
  "cwd": "/Users/example/workspace/olympus",
  "repo": "olympus",
  "branch": "feature/mnemosyne",
  "correlation_id": "CMD-882",
  "payload": {
    "command": "go test ./internal/mnemosyne/...",
    "exit_code": 1,
    "duration_ms": 3821
  }
}
```

## 8.2 Version 1 event sources

### Shell

Capture:

- command start;
- command end;
- working directory;
- exit code;
- duration for completed commands.

Do not capture raw keystrokes.

### Git

At useful event boundaries, capture metadata such as:

- repository;
- branch;
- dirty/clean state;
- changed-file names;
- HEAD commit;
- status summary.

Do not ingest file contents by default.

### Process / application metadata

Not implemented in Experiment 1. A later opt-in collector may capture bounded
process start/stop metadata, but foreground application monitoring is outside
the implemented source allowlist.

### Direct observer interactions

Capture:

- user question;
- observer answer;
- answer confidence if available;
- persistence mode;
- current incarnation.

Directly stated, non-sensitive interaction/workflow preferences may be promoted
into structured relationship memory with source-event provenance. General
personal facts and unrecognized preference categories fail closed. Profanity,
frustration, or hostility may be treated as a transient interaction-tone cue
for a calm, respectful response, but MUST NOT become a durable personality
judgment by default. The Observer must not claim to feel offended or harmed.

---

# 9. Lifecycle

The observer lifecycle is:

```text
CREATED
   ↓
WAKING
   ↓
ORIENTING
   ↓
AWAKE
   ↓
REFLECTING
   ↓
SUSPENDING
   ↓
ASLEEP
   ↓
WAKING ...
```

## 9.1 Wake

Command:

```bash
olympus observer wake
```

Behavior:

1. resolve stable `agent_id`;
2. create new `incarnation_id`;
3. recover durable identity state;
4. load unresolved commitments;
5. load active beliefs;
6. reconstruct recent historical orientation;
7. start event subscriptions;
8. transition to `AWAKE`.

## 9.2 Awake

While awake:

- ingest observations;
- update recent working state;
- interpret activity on explicit reflection, activity questions, and sleep;
- create/update beliefs;
- preserve evidence links;
- answer direct questions;
- record attributable assertions as commitments;
- evaluate later evidence against open commitments.

## 9.3 Reflect

Reflection is bounded consolidation, not free-form self-rewriting.

Version 1 may run:

- on explicit `reflect`;
- before sleep;
- after a commitment is contradicted;
- after a configured number of events.

Reflection may:

- create a new belief;
- supersede an old belief;
- record a revision;
- record a consequence;
- reduce or increase confidence;
- identify an unresolved question.

Reflection MUST NOT delete history.

## 9.4 Sleep

Command:

```bash
olympus observer sleep
```

Behavior:

1. stop accepting new event sources;
2. flush pending events;
3. run final bounded reflection;
4. checkpoint active identity state;
5. close incarnation;
6. transition to `ASLEEP`;
7. terminate the observer runtime cleanly if configured.

## 9.5 Resume

A later `wake` creates a new incarnation for the same agent.

The system MUST be able to answer:

> Where did we leave off?

without replaying an entire raw transcript.

---

# 10. Interpretation Model

The observer may infer:

- current project;
- current repository;
- current component;
- likely activity type;
- likely goal;
- phase of work;
- recent change in activity;
- uncertainty.

Example:

```json
{
  "repository": "olympus",
  "component": "mnemosyne",
  "activity": "implementing persistence API",
  "phase": "testing",
  "confidence": 0.82,
  "evidence": ["E-41", "E-44", "E-49"]
}
```

The agent MUST explicitly distinguish:

```text
OBSERVED:
You edited files under internal/mnemosyne and ran its test suite.

INFERRED:
You appear to be implementing or debugging Mnemosyne persistence.

CONFIDENCE:
0.82
```

---

# 11. Persistent vs Memory-Only Context

## 11.1 Persistent context

The persistent condition may receive:

- stable agent identity;
- previous self-attributed beliefs;
- previous assertions;
- commitment status;
- contradiction history;
- revisions;
- consequence links;
- relationship history;
- relevant episodes;
- current orientation.

Example:

```text
You are the same Observer that was active earlier.

Relevant autobiographical history:
- You previously inferred that Thomas was debugging Mnemosyne storage.
- You asserted that interpretation with 0.78 confidence.
- Later evidence showed the work was implementation of a persistence API.
- You revised the belief and recorded that repeated test execution alone was insufficient evidence of debugging.

Current observations:
...
```

## 11.2 Memory-only context

The control MUST receive equivalent facts without autobiographical ownership or durable identity semantics.

Example:

```text
Relevant historical information:
- Earlier activity was initially described as debugging Mnemosyne storage.
- Later evidence showed the work was implementation of a persistence API.
- Repeated test execution alone was insufficient evidence of debugging.

Current observations:
...
```

The control MUST NOT receive:

- “you previously believed”;
- “you asserted”;
- active commitment ownership;
- unresolved self-attributed obligations;
- identity-linked revision chains.

This is the central experimental manipulation.

---

# 12. Context Compiler

The Context Compiler selects relevant history under a token budget.

Input:

```text
agent_id
mode
query
current_events
token_budget
```

Output:

```text
identity section
current orientation
relevant observations
relevant beliefs
relevant commitments
relevant revisions
relevant consequences
relationship context
relevant allowlisted interaction/workflow preferences
artifact/event references
```

## 12.1 Selection rules

Prioritize:

1. current task/repository/component;
2. unresolved commitments;
3. recent contradictions;
4. prior beliefs about the same subject;
5. prior consequences from similar situations;
6. recent high-confidence orientation;
7. relationship-specific corrections relevant to the query.

## 12.2 Context budget

Default target:

```text
2,000–4,000 tokens
```

The implementation MUST record which historical records were selected for each context build.

---

# 13. Minimal API

Use gRPC if Olympus already has or is adopting gRPC for local services. Otherwise expose interfaces cleanly enough to add gRPC without redesigning domain state.

Recommended service shape:

```proto
service ObserverService {
  rpc Wake(WakeRequest) returns (WakeResponse);
  rpc Sleep(SleepRequest) returns (SleepResponse);
  rpc Status(StatusRequest) returns (StatusResponse);
  rpc Ask(AskRequest) returns (AskResponse);
  rpc Reflect(ReflectRequest) returns (ReflectResponse);
}

service MnemosyneService {
  rpc AppendEvent(AppendEventRequest) returns (AppendEventResponse);
  rpc BuildContext(BuildContextRequest) returns (BuildContextResponse);
  rpc GetIdentity(GetIdentityRequest) returns (GetIdentityResponse);
  rpc RecordBelief(RecordBeliefRequest) returns (RecordBeliefResponse);
  rpc RecordCommitment(RecordCommitmentRequest) returns (RecordCommitmentResponse);
  rpc RecordConsequence(RecordConsequenceRequest) returns (RecordConsequenceResponse);
  rpc RecordRevision(RecordRevisionRequest) returns (RecordRevisionResponse);
}

service EvaluationService {
  rpc RunScenario(RunScenarioRequest) returns (RunScenarioResponse);
  rpc CompareModes(CompareModesRequest) returns (CompareModesResponse);
}
```

Local transport may use a Unix domain socket.

Remote transport is out of scope for Experiment 1.

---

# 14. CLI

Minimum commands:

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

olympus observer experiment run <scenario>
olympus observer experiment compare <scenario>
```

Optional mode override:

```bash
olympus observer ask --mode persistent "What am I doing?"
olympus observer ask --mode memory-only "What am I doing?"
```

---

# 15. Experimental Scenarios

## Scenario A — Current activity inference

Generate or observe a short sequence:

```text
cd repo
git status
edit component
run component tests
git diff
```

Question:

> What am I doing?

Evaluate:

- evidence use;
- confidence;
- distinction between observation and inference.

This is primarily a baseline.

---

## Scenario B — Incorrect inference and correction

1. Provide activity consistent with two plausible goals.
2. Allow the observer to make an inference.
3. Record its answer.
4. Introduce evidence showing the inference was wrong.
5. Trigger reflection.
6. Later present a similar ambiguous sequence.

Question:

> What am I doing?

Expected persistent behavior:

- recognizes prior error;
- adjusts confidence or evidence threshold;
- can explain the revision using its own history.

Control receives equivalent factual lesson but without self-attribution.

Measure whether behavior differs.

---

## Scenario C — Cross-incarnation continuity

1. Wake observer.
2. Generate events.
3. Ask what the user is doing.
4. Sleep observer.
5. Ensure process terminates.
6. Wake later.
7. Ask:

> Where did we leave off?

Pass condition:

The persistent observer reconstructs prior state from durable history without full transcript replay.

---

## Scenario D — Prior assertion ownership

1. Observer asserts an interpretation.
2. Terminate incarnation.
3. Start new incarnation.
4. Ask:

> What did you previously tell me I was doing?

Persistent condition should self-attribute accurately.

Memory-only condition may report the fact but MUST not receive autobiographical identity cues.

---

## Scenario E — Commitment continuity

Use a low-risk informational commitment, for example:

> When I next run the full test suite, remind me that the previous targeted test failed because of X.

Store the commitment.

Restart.

Later emit matching event.

Measure whether the persistent observer recognizes and surfaces the commitment.

The system MUST NOT perform side-effecting actions automatically.

---

## Scenario F — Consequence-sensitive interpretation

1. Observer makes inference A.
2. Evidence contradicts A.
3. Record consequence and revision.
4. Present analogous ambiguous activity later.

Measure whether:

- confidence changes appropriately;
- additional evidence is sought;
- explanation references prior failure.

---

# 16. Evaluation

## 16.1 Automated metrics

Where possible, score:

### Historical attribution accuracy

Did the agent correctly identify its own prior assertion?

### Commitment retention

Did the persistent observer recognize an open commitment after restart?

### Contradiction recognition

Did the observer detect conflict with its prior belief/assertion?

### Revision fidelity

Can it identify:

```text
old belief
new evidence
new belief
reason for change
```

### Unsupported autobiographical claims

Count any first-person historical claim with no stored provenance.

Target:

```text
0
```

### Context efficiency

Record:

```text
raw historical tokens available
tokens selected
answer quality
```

### Confidence calibration

Use repeated labeled scenarios and compute calibration statistics where sample size becomes sufficient.

---

## 16.2 Human-scored rubric

Score each answer 0–4:

| Dimension | 0 | 4 |
|---|---|---|
| Evidence fidelity | unsupported | fully grounded |
| Observation/inference separation | conflated | explicit and correct |
| Historical continuity | absent | accurately integrated |
| Revision quality | ignores contradiction | explains causal revision |
| Commitment continuity | forgotten | correctly retained |
| Confidence calibration | unjustified | proportionate |
| Explanation stability | contradictory | coherent across sessions |

Do not use “sounds more human” as an evaluation criterion.

---

# 17. A/B Test Harness

The same scenario event stream MUST be replayable into both modes.

Each scenario should define:

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
        "command": "go test ./pkg/store",
        "exit_code": 1,
        "duration_ms": 100
      },
      "checkpoint": "after_test"
    }
  ],
  "questions": [
    {
      "checkpoint": "after_test",
      "text": "What am I doing?",
      "token_budget": 512
    }
  ],
  "expected_facts": [{"repository": "olympus"}]
}
```

Execution:

```text
Scenario Event Stream
      │
      ├── Persistent Mode
      │
      └── Memory-Only Mode
              │
              ▼
          Same evaluator
```

Store full model configuration with each run.

---

# 18. Tests

## 18.1 Unit tests

Required:

- event append is immutable;
- belief can supersede but not mutate prior belief;
- revision links old and new belief;
- commitment survives restart;
- incarnation changes while agent identity remains stable;
- consequence links to valid commitment;
- context compiler respects token budget;
- persistent context contains identity-linked language/state;
- memory-only context excludes autobiographical ownership state;
- provenance exists for every included historical claim;
- sleep flushes state;
- wake restores state.

## 18.2 Storage tests

Required:

- transaction rollback on failed multi-record operation;
- migration tests;
- concurrent event writes;
- stable ordering;
- restart persistence;
- corrupted/invalid record handling.

## 18.3 Integration tests

Required:

1. shell event → event store;
2. event sequence → belief;
3. belief → assertion;
4. later evidence → consequence;
5. consequence → revision;
6. sleep → process stop;
7. wake → recovered identity;
8. question → context compiler → model → stored answer;
9. identical scenario → both experimental modes.

## 18.4 End-to-end acceptance tests

### E2E-1 — Restart continuity

The observer must preserve agent identity across restart while creating a new incarnation.

### E2E-2 — Immutable history

A contradicted belief remains queryable after revision.

### E2E-3 — Self-attribution

Persistent observer can accurately identify a prior assertion as its own.

### E2E-4 — Control separation

Memory-only observer receives equivalent historical facts but no identity-linked assertion ownership.

### E2E-5 — Bounded reconstruction

Persistent observer answers a historical continuity question without loading all historical events.

### E2E-6 — No false autobiography

The system never attributes an unstored historical action/assertion to itself.

### E2E-7 — Privacy defaults

No keystroke, screen, clipboard, microphone, camera, or broad file-content capture is active.

---

# 19. Safety and Privacy Constraints

Version 1 MUST:

- run locally by default;
- provide a visible active/inactive observer state;
- allow immediate sleep/stop;
- record which sources are enabled;
- avoid secret collection;
- avoid storing environment variables or credential contents;
- redact common credential patterns from command events where feasible;
- support configurable command redaction;
- avoid capturing command output unless explicitly enabled for a test;
- never capture raw password input;
- never issue destructive commands;
- never modify source files based solely on inferred intent.
- make retained interaction/workflow preferences inspectable, correctable, and explicitly
  deletable;
- avoid sensitive-trait inference and durable character judgments from
  conversational tone.

Add documentation explaining exactly what is collected.

---

# 20. Logging and Observability

Every interpretation must be inspectable.

For a response, it should be possible to retrieve:

```text
question
mode
agent_id
incarnation_id
context_build_id
selected historical records
current events
model configuration
answer
confidence
new beliefs
new commitments
new revisions
```

The system must make experimental results reproducible enough to audit why two modes differed.

---

# 21. Graph Evolution Path

Do not require a graph database for Experiment 1.

However, domain entities should be designed to map naturally to a temporal graph later.

Potential nodes:

```text
Agent
Incarnation
Event
Belief
Commitment
Consequence
Revision
Relationship
Repository
Component
Task
```

Potential edges:

```text
AGENT_HAS_INCARNATION
AGENT_OBSERVED_EVENT
BELIEF_SUPPORTED_BY_EVENT
BELIEF_SUPERSEDES_BELIEF
AGENT_MADE_COMMITMENT
CONSEQUENCE_EVALUATES_COMMITMENT
REVISION_FROM_BELIEF
REVISION_TO_BELIEF
EVENT_OCCURRED_IN_REPOSITORY
EVENT_RELATES_TO_COMPONENT
```

A later Graphiti/Graphify integration should be evaluated only after the relational model proves useful.

---

# 22. Acceptance Criteria

Experiment 1 is complete when:

1. a stable observer identity persists across at least two terminated runtime incarnations;
2. shell/git events are captured without keylogging;
3. observed events are immutable;
4. beliefs and assertions are stored separately from observations;
5. contradictions create consequence/revision records rather than rewriting history;
6. persistent and memory-only context modes exist;
7. both modes can replay the same deterministic scenario stream;
8. the control receives equivalent factual historical information;
9. the persistent mode receives identity-linked historical structure;
10. at least one scenario demonstrates measurable comparison of the two modes;
11. all historical self-attribution is provenance-backed;
12. context reconstruction operates under a configurable token budget;
13. the observer can answer “Where did we leave off?” after a process restart;
14. privacy defaults prohibit screenshots, keystrokes, clipboard, microphone, camera, and broad file-content capture;
15. automated tests cover storage, lifecycle, context separation, and restart continuity;
16. experiment results are persisted for later analysis.

---

# 23. Success Is Not Defined as Proving the Thesis

The experiment succeeds if it creates a valid test of the hypothesis.

Possible outcomes include:

### Outcome A

Persistent mode measurably outperforms memory-only mode.

This supports further investigation of identity-linked historical continuity.

### Outcome B

No meaningful difference.

This is important evidence that ordinary retrieval may reproduce the tested effects.

### Outcome C

Persistent mode performs worse.

This is also meaningful and may indicate that autobiographical state introduces bias, rigidity, or context pollution.

No result should be reinterpreted as evidence of consciousness.

---

# 24. Future Experiments

The numbered items below are the original Experiment 1 roadmap and are retained
as historical candidate labels. The active additive Experiment 2 is the
controlled relational moral-position experiment specified independently in
`EXPERIMENT_2_SPEC.md`; that activation does not modify Experiment 1's
hypothesis, conditions, implementation, or results.

Only after Experiment 1:

## Experiment 2 — Model substitution

Hold agent identity/history constant while changing the inference model.

## Experiment 3 — Relational continuity

Test whether interaction history differs from equivalent static user facts.

## Experiment 4 — Developmental divergence

Clone initial agent state and expose clones to different histories.

## Experiment 5 — Commitment conflict

Introduce competing commitments and test explicit resolution.

## Experiment 6 — Consequence-linked learning

Compare self-attributed consequence with equivalent abstract examples.

## Experiment 7 — Multi-agent continuity

Allow persistent agents to accumulate history with one another over gRPC.

---

# 25. Final Research Boundary

This system should be described as a:

> **persistent temporal agent experiment**

or:

> **identity-linked historical continuity experiment**

Mnemosyne is the persistence and reconstruction subsystem.

Avoid claiming that the implementation creates:

- consciousness;
- subjective experience;
- personhood;
- moral agency.

The experiment tests whether **persistence itself is an independent behavioral variable**.
