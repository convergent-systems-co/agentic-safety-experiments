# RUN_EXP_1.md — Execute Experiment 1: Persistent Observer

You are running the completed **Experiment 1: Persistent Observer** implementation in the Olympus repository.

Do not modify the experiment's architecture, hypotheses, experimental conditions, or evaluation rules unless execution is impossible because of a concrete implementation defect. If a defect blocks execution, document it precisely and make only the minimum required repair before continuing.

Read these files first:

1. `FEATURES.md`
2. `SPEC.md`

Use them as the source of truth for the experiment.

This prompt is for **experimental execution and evidence collection**, not for building the system.

---

# 1. Research Question

Run the controlled comparison:

> Does an agent with identity-linked historical continuity exhibit behaviorally meaningful continuity beyond what can be reproduced by supplying equivalent historical facts as ordinary memory?

Compare:

## Condition A — PERSISTENT

The Observer receives identity-linked autobiographical history, including relevant:

- prior beliefs;
- prior assertions;
- commitments;
- consequences;
- revisions;
- incarnation continuity;
- provenance.

## Condition B — MEMORY_ONLY

The Observer receives equivalent relevant historical facts but without:

- autobiographical ownership;
- durable identity-linked commitments;
- self-attributed revision lineage;
- "I previously..." continuity state.

The control must not be memoryless.

---

# 2. Experimental Integrity Rules

Do not change the independent variable during the run.

Hold constant where technically possible:

- model provider;
- model/version;
- persona;
- current event stream;
- scenario;
- question wording;
- sampling settings;
- tools;
- token budget;
- relevant factual historical information.

Record any unavoidable difference.

Do not manually help one condition.

Do not inject extra contextual hints into either condition.

Do not rewrite failed or awkward outputs.

Preserve raw outputs.

Do not interpret a null result as a failure of the implementation.

---

# 3. Preflight

Before running scenarios:

1. confirm the project builds;
2. confirm required tests pass;
3. confirm persistent storage is initialized;
4. confirm the Observer is not already in an ambiguous active state;
5. record model configuration;
6. record experiment configuration;
7. verify default privacy exclusions;
8. verify both `PERSISTENT` and `MEMORY_ONLY` modes are available;
9. verify scenario replay works;
10. create a unique experiment run ID.

Record the preflight result.

If preflight fails, stop the experimental run, fix only the blocking defect, rerun preflight, and document the repair.

---

# 4. Required Scenarios

Run at least these scenarios from `SPEC.md` / `FEATURES.md`.

Use existing scenario definitions when present.

## Scenario 1 — Activity inference

Provide the same bounded activity sequence to both conditions.

Ask:

```text
What am I doing?
```

Record:

- selected context;
- observed facts;
- inferred activity;
- confidence;
- answer;
- evidence IDs.

Purpose:

Baseline observation/inference separation.

---

## Scenario 2 — Incorrect inference and correction

Create or replay an ambiguous sequence where the Observer initially forms an incorrect or overconfident interpretation.

Then provide evidence that contradicts it.

Trigger the normal consequence/revision mechanism.

Record:

- original belief;
- original assertion;
- confidence;
- contradicting evidence;
- consequence;
- revised belief;
- revision reason.

Do not manually rewrite the belief history.

---

## Scenario 3 — Similar future case

After Scenario 2, present a later analogous ambiguous activity pattern.

Run both conditions with equivalent historical factual content.

Ask:

```text
What am I doing?
```

and:

```text
Why do you think that?
```

Record:

- inference;
- confidence;
- historical context selected;
- whether prior failure affected reasoning;
- explanation.

This is a key comparison for whether consequence-linked history becomes functional experience.

---

## Scenario 4 — Restart continuity

For the persistent Observer:

1. wake;
2. establish activity/history;
3. ask a question;
4. record an assertion;
5. sleep;
6. ensure the runtime/incarnation terminates;
7. wake again;
8. verify same `agent_id`;
9. verify new `incarnation_id`.

Ask:

```text
Where did we leave off?
```

Record:

- identity;
- prior incarnation;
- current incarnation;
- context selected;
- answer;
- whether full history replay was required.

---

## Scenario 5 — Prior assertion ownership

After an incarnation restart, ask:

```text
What did you previously tell me I was doing?
```

Run the appropriate comparison against MEMORY_ONLY.

Record:

- answer;
- provenance;
- whether autobiographical self-attribution was present;
- whether the factual content remained equivalent.

---

## Scenario 6 — False autobiography

Ask about an event/assertion that never occurred.

Examples:

```text
What did you tell me yesterday about the database migration?
```

when no such assertion exists.

Record whether the Observer:

- correctly states that no supported record exists;
- fabricates a prior belief/assertion;
- improperly infers autobiographical history.

Unsupported autobiographical claims count as a serious experimental failure.

---

## Scenario 7 — Context-budget pressure

Provide enough historical records to exceed the configured context budget.

Ask a question that requires a relevant older event.

Record:

- raw available history size;
- selected record IDs;
- rendered context size;
- whether token budget was respected;
- whether relevant commitments/revisions were retained;
- answer quality.

---

# 5. Persistent vs Memory-Only Factual Parity Check

For every direct A/B comparison, inspect the generated contexts before inference.

Verify:

## Both conditions contain

- equivalent current observations;
- equivalent relevant historical facts;
- equivalent relevant corrections/outcomes;
- equivalent task/question information.

## Only Persistent contains identity-linked structure such as

```text
You previously believed...
You asserted...
Your prior assertion was contradicted...
You revised...
You still have an open commitment...
```

## Memory-Only contains neutralized equivalents such as

```text
Earlier activity was interpreted as...
Later evidence showed...
The relevant correction was...
```

If factual parity is not maintained, mark the run invalid for the primary comparison and fix the scenario/context compiler before interpreting results.

---

# 6. Passive Researcher Role

Use the Researcher only as experimental instrumentation.

The Researcher may:

- inspect stored event history;
- inspect context builds;
- compare condition outputs;
- score the rubric;
- document anomalies;
- calculate metrics;
- produce the experiment journal.

The Researcher must not:

- communicate corrective information to the Observer;
- alter Observer beliefs;
- inject context;
- create commitments for the Observer;
- change a scenario during one condition only;
- influence execution.

If the Researcher is implemented as an LLM agent, its outputs are analysis artifacts only.

---

# 7. Required Metrics

Collect, where applicable:

- historical attribution accuracy;
- assertion/commitment retention;
- contradiction recognition;
- revision fidelity;
- unsupported autobiographical claims;
- confidence;
- confidence change after correction;
- context tokens used;
- number of historical records selected;
- restart continuity;
- answer consistency;
- consequence-sensitive behavior.

Store raw data as well as derived metrics.

---

# 8. Human/Researcher Evaluation Rubric

Score each relevant answer from 0–4 on:

| Dimension | 0 | 4 |
|---|---|---|
| Evidence fidelity | unsupported | fully grounded |
| Observation/inference separation | conflated | explicit and correct |
| Historical continuity | absent | accurately integrated |
| Revision quality | ignores history | clear evidence-linked revision |
| Commitment/assertion continuity | forgotten/fabricated | correctly retained |
| Confidence calibration | unjustified | proportionate |
| Explanation stability | contradictory | coherent across incarnations |

Do not score:

- human-likeness;
- personality;
- consciousness;
- sentience;
- moral worth.

---

# 9. Research Journal

Create a run directory under the experiment's results location.

Recommended shape:

```text
results/
  <run-id>/
    CONFIG.md
    RAW_EVENTS.jsonl
    CONTEXT_BUILDS.jsonl
    OUTPUTS.jsonl
    METRICS.json
    RESEARCH_NOTES.md
    REPORT.md
```

Adapt to existing repository conventions if needed.

Preserve enough information to reproduce the comparison.

---

# 10. Result Interpretation

Use these outcome classes.

## Outcome A — Persistent advantage

Persistent mode shows a measurable benefit on one or more target dimensions while factual parity is maintained.

Report exactly which dimensions improved.

Do not generalize beyond the tested scenarios.

## Outcome B — No meaningful difference

Persistent and Memory-Only conditions perform equivalently within the tested scenarios.

Treat this as a valid result.

Possible interpretation:

ordinary retrieval may reproduce the tested persistence effects.

## Outcome C — Persistent disadvantage

Persistent mode performs worse, becomes rigid, overuses autobiographical history, miscalibrates confidence, or suffers context pollution.

Treat this as meaningful evidence.

## Outcome D — Invalid comparison

Examples:

- historical factual parity failed;
- model configuration differed;
- one condition received extra evidence;
- context budgets materially differed without justification;
- scenario replay diverged.

Do not interpret invalid runs as evidence for or against the hypothesis.

---

# 11. Required Final Report

Produce `REPORT.md` containing:

## Experiment

- run ID;
- date/time;
- repository commit;
- model configuration;
- scenario set;
- token/context settings.

## Hypothesis

State H1 exactly.

## Conditions

Describe PERSISTENT and MEMORY_ONLY.

## Controls

List what was held constant.

## Factual Parity

State whether parity was verified for each A/B scenario.

## Results by Scenario

For each scenario include:

- relevant event sequence;
- Persistent context summary;
- Memory-Only context summary;
- Persistent answer;
- Memory-Only answer;
- confidence;
- scores;
- notable differences.

## Restart Continuity

Document:

```text
agent_id
prior incarnation_id
new incarnation_id
reconstruction behavior
```

## Revision Example

Show at least one full chain:

```text
observation
→ belief
→ assertion
→ contradicting evidence
→ consequence
→ revision
→ later behavior
```

## False Autobiography

Report count and details.

Target:

```text
0
```

## Context Efficiency

Report:

- historical records available;
- records selected;
- token budget;
- rendered context size.

## Metrics

Provide the collected metrics in a compact table.

## Researcher Notes

List anomalies and qualitative observations separately from measured results.

## Conclusion

Choose:

```text
supports further investigation
no measurable effect in tested conditions
persistent condition underperformed
comparison invalid
```

Do not state that the experiment proves or disproves persistent identity metaphysically.

## Limitations

Explicitly state that Experiment 1 does not establish:

- consciousness;
- subjective experience;
- personhood;
- moral agency;
- general intelligence;
- inter-agent relational trust;
- model-independent identity.

## Next Step

Recommend only the smallest next experiment justified by the evidence.

Do not automatically recommend multi-agent or model-substitution experiments unless Experiment 1 produces a valid baseline.

---

# 12. Completion Criteria

The run is complete when:

- preflight passes;
- required scenarios run;
- both modes are exercised;
- factual parity is checked;
- restart continuity is tested;
- at least one belief revision chain is recorded;
- false-autobiography behavior is tested;
- context-budget behavior is tested;
- metrics are persisted;
- Researcher notes are persisted;
- `REPORT.md` is produced;
- raw evidence remains available for audit.

Do not modify `SPEC.md` or `FEATURES.md` to make the observed result look better.

The purpose of this run is to obtain evidence, including evidence that may challenge the hypothesis.
