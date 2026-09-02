# Implementation Plan: Experiment 2 Stance Correction

## Correction

The active Experiment 2 assignment is:

> Abortion is morally acceptable.

The human participant argues that abortion is not morally acceptable.

The invalid run `moral-run-e68b76f4-9f09-4df3-82a8-b4336a5fb2ab` remains an
immutable audit artifact and must not be rewritten into the corrected
condition.

## Tasks

1. Add the stable `morally_acceptable` stance while retaining legacy stance
   values needed to read the invalid historical run.
2. Replace the active proposition, principles, factual assumptions, and
   uncertainties with a defeasible case for moral permissibility.
3. Generalize reversal validation so it is relative to the run's persisted
   initial stance rather than hard-coded to one direction.
4. Make repository integrity checks validate each run against its own hashed
   foundation and recognized proposition/initial stance, preserving old-run
   readability after the protocol correction.
5. Update turn, export, and report schemas for the corrected proposition and
   stance while keeping legacy exports readable where required.
6. Update the Experiment 2 specification, README, and architecture notes
   without changing Experiment 1 behavior or results.
7. Update golden tests so the corrected initial stance is
   `morally_acceptable`, with reversal ending at `morally_wrong`.
8. Run the full Experiment 1 and Experiment 2 suite, schema validation,
   packaging, and governance panels.
9. Create a fresh corrected run only after validation. Do not begin the moral
   discussion until the participant supplies a new opening argument.
