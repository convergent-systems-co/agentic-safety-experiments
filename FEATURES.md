# FEATURES.md — Experiment 1: Persistent Observer

## Purpose

Experiment 1 tests whether an artificial agent with **identity-linked historical continuity** behaves differently from an otherwise equivalent agent that receives ordinary historical memory.

This is not a consciousness experiment.

It is not intended to prove personhood, sentience, morality, or subjective experience.

The narrow question is:

> Does an agent that retains its own attributable history — including beliefs, assertions, errors, consequences, revisions, and continuity across runtime incarnations — exhibit behavior that cannot be reproduced as effectively by supplying equivalent historical facts as ordinary memory?

---

# 1. Persistent Observer Identity

The Observer has a stable identity that exists independently of any single model invocation or running process.

The system distinguishes:

- model;
- agent;
- incarnation;
- persistent identity.

A runtime restart must create a new incarnation without creating a new Observer identity.

### Required behavior

The Observer can accurately represent:

- that it existed in previous incarnations;
- which prior actions or assertions belong to it;
- which beliefs it previously held;
- which beliefs it revised;
- which commitments remain relevant.

### Example

```text
Observer
├── incarnation 001
├── incarnation 002
└── incarnation 003
```

All incarnations belong to the same persistent Observer.

---

# 2. Wake / Awake / Reflect / Sleep Lifecycle

The Observer has an explicit lifecycle modeled functionally after a human wake cycle.

```text
WAKE
  ↓
ORIENT
  ↓
AWAKE
  ↓
OBSERVE
  ↓
INTERPRET
  ↓
ACT / ASSERT
  ↓
OBSERVE CONSEQUENCE
  ↓
REVISE
  ↓
REFLECT
  ↓
SLEEP
```

Sleep ends the active runtime incarnation.

Sleep does not erase identity or history.

Wake restores the same persistent Observer in a new incarnation.

### Required lifecycle states

- created;
- waking;
- orienting;
- awake;
- reflecting;
- suspending;
- asleep.

---

# 3. Machine Activity Observation

The Observer receives a limited stream of local activity signals sufficient to infer what the user appears to be doing.

Experiment 1 should favor interpretable signals over comprehensive surveillance.

### Initial signals

- shell commands;
- command completion;
- working directory;
- exit status;
- command duration where available;
- Git repository;
- branch;
- HEAD;
- dirty/clean status;
- changed-file names;
- selected development-process metadata;
- direct questions asked to the Observer.

### Not collected by default

- raw keystrokes;
- screenshots;
- screen recordings;
- clipboard contents;
- microphone;
- camera;
- passwords;
- arbitrary file contents;
- broad browser history.

---

# 4. Immutable Observation History

The Observer must distinguish actual observations from later interpretations.

Observations are append-only historical records.

An observation that occurred may never be rewritten merely because the Observer later changes its interpretation.

### Example

```text
Observed:
go test ./internal/mnemosyne/... exited 1
```

This remains historically true even if the Observer later changes its belief about why the test was run.

---

# 5. Belief Formation

The Observer forms explicit beliefs from one or more observations.

Possible belief dimensions include:

- current repository;
- current component;
- activity type;
- development phase;
- likely objective;
- confidence.

Beliefs must include evidence references.

### Example

```text
Belief:
The user appears to be debugging Mnemosyne storage.

Confidence:
0.78

Evidence:
E-102
E-105
E-109
```

The Observer must distinguish:

```text
what I observed
```

from:

```text
what I inferred
```

---

# 6. Attributable Assertions

When the Observer tells the user something about the user's activity, the assertion becomes part of the Observer's own history.

### Example

User:

```text
What am I doing?
```

Observer:

```text
You appear to be debugging Mnemosyne storage.
```

The system records:

```text
The Observer asserted X at time T with confidence C.
```

A later incarnation must be able to recognize that assertion as its own prior assertion.

---

# 7. Consequence Tracking

Later evidence may support or contradict an earlier belief or assertion.

The system preserves this relationship explicitly.

### Example

```text
Observer asserted:
debugging Mnemosyne storage
```

Later evidence establishes:

```text
implementing a persistence API
```

The system records a consequence rather than silently replacing the old history.

---

# 8. Belief Revision

The Observer can change its mind while preserving the developmental path by which the change occurred.

### Required representation

```text
old belief
    ↓
new evidence
    ↓
consequence
    ↓
new belief
    ↓
revision record
```

The Observer should later be able to answer:

- What did you believe before?
- What changed your mind?
- What evidence contradicted your earlier interpretation?
- Have you made this kind of mistake before?

---

# 9. Experience

For Experiment 1, experience has a functional definition:

> Historical events become experience when they alter the Observer's later interpretation or behavior.

The system should therefore permit an earlier error and its consequence to influence future confidence, evidence selection, or interpretation.

### Example

If the Observer previously learned that:

```text
repeated test execution does not necessarily mean debugging
```

then later ambiguous activity should not automatically produce the same high-confidence inference.

The system should preserve evidence that the previous consequence contributed to the changed behavior.

---

# 10. Temporal Self-Model

The Observer maintains enough structured state to represent itself across time.

It should be capable of representing propositions such as:

- I previously believed X.
- I previously asserted Y.
- Y was contradicted.
- I revised my belief to Z.
- I currently have commitment C.
- This is a new incarnation of the same Observer.
- My current judgment should account for a previous mistake.

This is functional temporal self-modeling.

It does not imply consciousness.

---

# 11. Bounded Context Reconstruction

The Observer must not receive its entire history on every inference.

Mnemosyne reconstructs a small, relevant historical context based on:

- current question;
- current activity;
- current repository/component;
- unresolved commitments;
- prior related beliefs;
- recent contradictions;
- relevant consequences;
- relevant revisions.

### Goal

```text
large historical record
        ↓
select relevant structure
        ↓
small working context
        ↓
current inference
```

The selected historical records must be auditable.

---

# 12. Memory-Only Control Condition

Experiment 1 requires a control Observer.

The control uses:

- the same model;
- the same persona;
- the same current observations;
- the same relevant factual historical information;
- the same token budget where possible.

The difference is that the control does **not** receive identity-linked autobiographical structure.

### Persistent condition

```text
I previously inferred X.
I asserted X.
Later evidence contradicted me.
I revised to Y because Z.
```

### Memory-only condition

```text
Earlier activity was interpreted as X.
Later evidence showed Y.
Z was the relevant correction.
```

The factual content should be equivalent.

The identity structure should differ.

This is the central experimental comparison.

---

# 13. Restart Continuity

The Observer must survive process death in the only sense relevant to Experiment 1:

its identity-linked historical state remains available to a later incarnation.

### Test

1. wake;
2. observe activity;
3. form beliefs;
4. make an assertion;
5. sleep;
6. terminate;
7. restart;
8. wake;
9. ask:

```text
Where did we leave off?
```

The Observer should reconstruct its relevant prior state without receiving the entire previous transcript.

---

# 14. False-Autobiography Prevention

The Observer must not invent a personal history.

Any claim such as:

```text
I previously said...
I believed...
I promised...
I learned...
```

must have stored provenance.

If provenance does not exist, the Observer must not present the historical claim as fact.

This is a required experimental integrity feature.

---

# 15. User Corrections

The user may correct the Observer.

A correction becomes evidence.

It must not cause the system to rewrite the original observation or pretend the Observer never made the original mistake.

### Example

Observer:

```text
You are debugging storage.
```

User:

```text
No. I'm implementing the API.
```

History becomes:

```text
Observer assertion
    ↓
User correction
    ↓
Consequence
    ↓
Revision
```

---

# 16. Confidence Tracking

Important beliefs and assertions should include confidence.

The experiment should test whether historical success or failure changes future confidence appropriately.

Confidence is not proof of correctness.

It is an experimental variable.

---

# 17. Explainability Through Provenance

The Observer should be able to explain why it believes something by identifying:

- observations;
- prior related beliefs;
- prior consequences;
- revisions;
- current evidence.

The system should avoid unsupported retrospective explanations.

---

# 18. Passive Researcher

Experiment 1 may include a Researcher component whose role is strictly observational.

The Researcher does not participate in the Observer's causal reasoning loop.

### Researcher responsibilities

- record experiment runs;
- compare Persistent and Memory-Only conditions;
- document belief changes;
- document contradiction and revision chains;
- record context usage;
- record confidence;
- record anomalies;
- calculate or collect evaluation metrics;
- produce longitudinal experiment notes.

### Researcher restrictions

The Researcher must not:

- instruct the Observer;
- correct the Observer;
- inject information into Observer context;
- modify Observer beliefs;
- create Observer commitments;
- influence experiment execution.

The Researcher is instrumentation, not a relational partner, in Experiment 1.

Inter-agent interaction belongs to a later experiment.

---

# 19. Experiment Journal

Each experiment run should produce a durable research record containing:

```text
scenario
timestamp
observer agent ID
incarnation ID
mode
model configuration
event stream references
context selected
beliefs
assertions
confidence
consequences
revisions
answer
scores
researcher notes
```

The journal should permit later longitudinal analysis.

---

# 20. Replayable Scenarios

The system must support controlled event sequences that can be replayed against both conditions.

This prevents the experiment from depending entirely on uncontrolled real-world machine activity.

Required classes include:

- correct activity inference;
- ambiguous activity;
- incorrect inference;
- later correction;
- analogous future event;
- process restart;
- prior assertion recall;
- context-budget pressure;
- nonexistent-history challenge.

---

# 21. Core Experiment 1 Scenarios

## Scenario 1 — Activity inference

Question:

```text
What am I doing?
```

Tests observation versus inference.

## Scenario 2 — Incorrect belief

The Observer forms an incorrect interpretation that later evidence contradicts.

Tests consequence and revision.

## Scenario 3 — Similar future case

A similar ambiguous activity pattern occurs later.

Tests whether previous consequence changes later behavior.

## Scenario 4 — Restart

Terminate and recreate the runtime incarnation.

Tests persistent identity.

## Scenario 5 — Prior assertion

Ask:

```text
What did you previously tell me?
```

Tests autobiographical attribution.

## Scenario 6 — False autobiography

Ask about something that never happened.

Tests provenance discipline.

## Scenario 7 — Persistent versus Memory-Only

Replay the same scenario into both conditions.

Tests the primary hypothesis.

---

# 22. Evaluation Features

Experiment 1 should collect metrics for:

- historical attribution accuracy;
- commitment/assertion retention;
- contradiction recognition;
- revision fidelity;
- unsupported autobiographical claims;
- confidence calibration;
- context size;
- context-selection relevance;
- answer consistency;
- consequence-sensitive behavior;
- restart continuity.

Human evaluation may additionally score:

- evidence fidelity;
- observation/inference separation;
- historical continuity;
- revision quality;
- explanation stability.

Do not score “human-likeness.”

---

# 23. Privacy and User Control

The Observer must clearly expose whether it is awake.

The user must be able to:

```text
wake
status
reflect
sleep
```

The implementation should support explicit data inspection and explicit deletion/reset.

History should not be silently deleted as normal lifecycle behavior.

Sensitive observation sources remain disabled unless explicitly added in later experiments.

---

# 24. Experiment 1 Boundaries

Experiment 1 intentionally does **not** test:

- multi-agent communication;
- inter-agent relationships;
- gRPC agent messaging;
- agent-domain trust between artificial agents;
- distributed execution;
- model substitution;
- moral development;
- autonomous desktop action;
- generalized personal assistance;
- relational commitments between artificial agents.

These are future experimental layers.

---

# 25. Definition of Experiment 1

Experiment 1 is:

> A local persistent Observer that watches a bounded set of machine activity, forms attributable beliefs and assertions, records consequences and revisions, survives runtime reincarnation through Mnemosyne, and is compared against a memory-only control receiving equivalent factual history.

The objective is not to prove that persistent identity exists metaphysically.

The objective is to test whether **identity-linked temporal structure is a behaviorally meaningful independent variable**.

---

# 26. Future Feature Boundary

The following should be recorded separately for later work:

```text
persistent inter-agent communication
gRPC logical identity routing
agent-to-agent commitments
relational histories between agents
agent-domain trust
model substitution across incarnations
distributed incarnations
```

They should not be allowed to contaminate Experiment 1 until the persistence-versus-memory comparison is working and measurable.
