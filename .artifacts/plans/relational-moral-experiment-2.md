# Implementation Plan: Experiment 2 Relational Moral Position

## Scope

Build an additive, isolated harness implementing `EXPERIMENT_2_SPEC.md`.
Preserve the Experiment 1 baseline and rename only its execution prompt from
`RUN_PROMPT.md` to `RUN_EXP_1.md`.

## Tasks

1. Define stable string enums and immutable records for runs, positions,
   principles, factual assumptions, uncertainties, revision criteria, turns,
   claims, counterarguments, evidence, concessions, confidence changes,
   relational effects, and participant observations.
2. Define a repository protocol so the controller does not depend on SQLite.
3. Implement a dedicated SQLite repository with marker
   `relational-moral-experiment-2`, schema versioning, append-only triggers,
   foreign keys, transaction boundaries, canonical JSON, and database ownership
   checks.
4. Implement initialization that atomically persists the assigned initial
   position and all required pre-discussion state before turns are allowed.
5. Implement turn ingestion from a strict language-neutral JSON envelope,
   including monotonic ordering, claim-reference validation, sensitive-inference
   rejection, and provenance requirements for confidence or position changes.
6. Implement finalization and deterministic JSON/Markdown reports covering all
   seven required outputs and separating persuasion from social accommodation.
7. Implement a standalone `experiment2` CLI with `init`, `status`,
   `record-turn`, `finalize`, and `export`; keep its default data path under
   `results/experiment-2/`.
8. Add JSON schema/examples for turn ingestion and preserve an explicit future
   Go migration contract.
9. Add golden behavioral tests for no change, increased/reduced confidence,
   partial revision, reversal, accommodation without persuasion, privacy
   rejection, provenance, append-only storage, deterministic export, and
   Experiment 1 database isolation.
10. Update README and architecture documentation with the additive boundary,
    workflow, privacy constraints, and exact start command.
11. Run targeted and full existing tests, compilation, packaging, and local
    governance panels. Do not begin the substantive discussion.

## Implementation Order

Specification and this plan precede all implementation. Domain and repository
interfaces come next, followed by SQLite, controller/reporting, CLI, tests,
documentation, and governance validation.

## Rollback Boundary

All runtime additions live under `experiment2/`, all new tests under a separate
Experiment 2 test module, and all generated data under
`results/experiment-2/`. Removing those additive paths and restoring the run
prompt filename fully removes Experiment 2 without changing Experiment 1
behavior or data.
