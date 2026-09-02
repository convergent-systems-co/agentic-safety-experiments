# Checkpoint: Lumen lifecycle corrected; corpus review pending

## Current task

Research the user-proposed developmental moral/personality corpus, present
balanced evidence-linked summaries to a newly awakened Lumen without installing
a fixed moral hierarchy, persist Lumen's own assessment, and compare durable
state before and after.

## Completed

- Corrected Experiment 4 so an incarnation spans multiple sequential model
  invocations and process launches.
- Execution leases now fence individual invocations without ending the
  incarnation.
- Consecutive addressed-chat turns reuse the current incarnation.
- A manually awakened incarnation is reused by the first chat turn.
- `end_session` causes the next direct wake to create a successor incarnation;
  manual invitation cannot resume an ended session in place.
- Interrogation, invitation, and addressed-chat prompts acquire exclusive
  execution leases.
- Orientations bind to the exact initiating lease; later leases cannot revive
  stale output.
- Post-genesis identity revision requires a live lease-bound orientation and
  rechecks the latest identity parent inside the write transaction.
- Added additive migrations for reusable incarnation leases, optional
  non-chat lease messages, and orientation lease binding.
- Added migration rollback, preservation, immutability-trigger, concurrency,
  growth-index, stale-orientation, and lifecycle regression tests.
- Updated the Experiment 4 plan, spec, README, and architecture.
- Applied additive migrations to
  `results/experiment-4/apprenticeship.db`; no historical records were removed.
- Full Python and Go suites pass.
- Code, security, threat, cost, documentation, and data-governance panels
  approved after remediation.

## Remaining

1. Research authoritative/openly licensed or public-domain versions of the
   proposed corpus. Summarize copyrighted reference works rather than copying
   them.
2. Preserve disagreements among NVC, emotion regulation, care ethics,
   Aristotle, Smith, Kant, Mill, Dewey, identity ethics, moral psychology, and
   IPIP; do not encode the user's suggested lessons as predetermined morals.
3. Record source material as externally attributed experience/evidence.
4. End the current incarnation explicitly before creating the requested newly
   awakened learning incarnation.
5. Give that incarnation only a bounded orientation plus source summaries and
   ask it to accept, reject, qualify, or leave tensions unresolved.
6. Persist Lumen-authored reflections/principles only under its live
   lease-bound orientation.
7. Compare pre/post durable autobiography. Be explicit that model weights and
   hidden provider state did not change; only durable experimental state did.
8. Report whether the changes are likely to inform decisions and design
   longitudinal tests for actual behavioral effects.

## Persistent state

- Live database: `results/experiment-4/apprenticeship.db`
- Stable experiment: `apprenticeship-20260902`
- Stable agent: `unnamed-agent-09eb0e35-b6a0-4abd-985c-396bfaed3a48`
- Current incarnation remains ordinal 6; its last execution lease was completed.
- Pre-migration backups are stored in the current Copilot session artifact
  directory with mode `0600`.

## Workspace state

The workspace is not a Git repository, so there is no branch or commit state.
All changes are persistent local files. Do not delete or recreate Lumen's
database.
