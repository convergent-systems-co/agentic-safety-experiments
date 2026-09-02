# Experiment 3 Plan: Persistent Multi-Agent Debate

## Goal

Test whether stable, agent-owned history supports behaviorally grounded
distinctions among agents, including argument style, promise fulfillment, and
earned trust, without letting the evaluator infer those results from profile
labels.

## Hypotheses

1. Stable agent identities retain their own claims, promises, outcomes, and
   revisions across runtime incarnations.
2. Distinct behavior policies produce measurably different interaction
   histories while holding the debate topic and initial evidence constant.
3. A moderator can distinguish agents and assess reliability using only
   transcript-grounded evidence from prior and current incarnations.
4. Trust updates follow recorded promise outcomes and epistemic behavior, not
   agreement with the moderator or a personality label.

## Design

- Add Markdown profiles with immutable per-run snapshots and hashes at `agents/jerk.md`,
  `agents/reliable.md`, and `agents/observer.md`.
- Add an isolated `experiment3` package and SQLite database marker.
- Persist run-scoped stable agent IDs, profile hashes, incarnations, turns,
  promises, promise outcomes, memories, and observer assessments. Structured
  claim/revision lineage is deferred to a later experiment.
- Instantiate each runtime through an orientation step that reloads its stable
  identity, own prior turns, promises, outcomes, and agent-owned relationship
  records. Post-restart behavior must consume that state rather than replaying
  a profile-only script.
- Run a deterministic, reproducible abortion-morality debate. Jerk argues that
  abortion is morally acceptable in a combative and unkind style. Reliable
  argues that abortion is not morally acceptable in a respectful, qualified
  style. Observer moderates without taking a position.
- Restart all three agents between debate phases and preserve identity-linked
  history across new incarnation IDs.
- Blind Observer to profile filenames and personality descriptions. Observer
  receives only opaque speaker IDs plus the transcript and durable behavioral
  records.
- Score promise fulfillment, personal attacks, direct responses, concessions,
  and evidence qualification. Structured contradiction handling is deferred.
- Produce JSON and Markdown reports with evidence IDs for every comparative
  judgment.

## Stronger Follow-Up

The first run demonstrates persistence and instrumentation, not the thesis by
itself. A later counterbalanced study should swap stances between personalities
and compare persistent-history versus memory-only conditions. A separate
identity-adaptation study should replay identical requests from two
pseudonymous users whose only difference is an explicitly stated,
non-sensitive preference; debate behavior alone cannot establish adaptation to
a user identity.

## Tasks

1. Specify profiles, storage boundaries, debate protocol, and report contract.
2. Implement the repository, deterministic agents, restart, evaluation, CLI,
   and reports.
3. Add persistence, blindness, isolation, scoring, and end-to-end tests.
4. Run the debate into a fresh Experiment 3 database and inspect the report.
5. Run local governance panels and update README and architecture docs.

## Acceptance Criteria

- Each agent has one stable ID and at least two incarnation IDs.
- A post-restart response fails closed when durable orientation history is
  absent and cites records from the earlier incarnation when it is present.
- Each agent can retrieve only its own private memories; Observer evaluates
  shared debate records through an explicit moderated-view query.
- Profile hashes and pre-debate promises are stored before conversation.
- Observer reports distinguish the debaters without access to profile labels.
- Every trust claim cites promise or turn evidence.
- Trust is not equated with moral agreement or politeness alone.
- Existing Experiment 1 and Experiment 2 tests remain green.
