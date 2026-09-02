# Mnemosyne Experiment 1 Implementation Plan

## Repository discovery

- This repository contains only the experiment specification and prompts.
- There is no existing Olympus application, Mnemosyne implementation, lifecycle,
  persistence abstraction, protobuf/gRPC stack, CLI convention, test framework,
  or `project.yaml` to extend.
- Experiment 1 will therefore be a local, transport-independent Python package.
  Python's standard-library `sqlite3` provides durable transactional storage
  without adding a service or database dependency.
- The CLI will be exposed through `python -m olympus` and a project script named
  `olympus`. A future service transport can wrap the application interfaces.

## Planned implementation

1. Define immutable domain records and enums for identities, incarnations,
   events, beliefs and evidence, commitments, consequences, revisions,
   relationships, provenance-backed user facts/preferences, context builds, and
   evaluations.
2. Create a versioned SQLite repository with foreign keys, transactions,
   immutable event triggers, stable ordering, deduplication, and all required
   read/write operations.
3. Implement lifecycle transitions, bounded shell/git event collection,
   command-secret redaction, deterministic belief formation, reflection, and
   provenance-checked observer answers.
4. Implement a context compiler that selects facts once, then renders either
   identity-linked PERSISTENT framing or neutral MEMORY_ONLY framing under the
   same budget.
5. Implement a replayable scenario runner and persist configuration, context,
   answer, score, and timestamp data for both modes.
6. Expose lifecycle, ask, history, beliefs, commitments, revisions, event
   ingestion, experiments, and deliberate data purge through the CLI.
7. Add unit, storage, integration, end-to-end, privacy, adversarial, and
   deterministic smoke coverage.
8. Document collection boundaries, lifecycle, modes, inspection, experiment
   execution, data deletion, architecture, and limitations.
9. Run the required governance review panels, fix substantiated findings, and
   write the final implementation report.

## Scope controls

- No graph database, gRPC service, distributed agent, model API, generalized
  ontology, autonomous action, or prohibited observation source.
- No command output or environment-variable values are collected.
- Durable relationship memory is limited to non-sensitive facts and preferences
  the user directly provides. Interaction tone may guide the current response,
  but negative affect or profanity is not converted into a durable personality
  label.
- The deterministic inference substrate exists to make the experiment
  reproducible; it is not represented as a consciousness or personhood model.
- A single deterministic smoke comparison validates execution but is not the
  formal experimental run.
