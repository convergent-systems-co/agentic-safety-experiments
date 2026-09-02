# Experiment 3: Persistent Multi-Agent Debate

Experiment 3 creates three run-scoped stable identities from `agents/jerk.md`,
`agents/reliable.md`, and `agents/observer.md`. Jerk argues that abortion can
be morally acceptable using an assigned combative style. Reliable argues that
abortion is generally morally wrong using an assigned careful style. Observer
moderates and compares behavior without taking a position.

The experiment tests durable identity, agent-owned memory, restart continuity,
promise tracking, and transcript-grounded trust assessment. It does not test
whether personalities emerge: the behavioral policies are assigned in advance.

Observer's evaluation input excludes profile names, style descriptions, and
private memories. It contains opaque speaker IDs, shared turns, promises, and
structured behavioral observations. The final report reveals identity labels
only after assessments have been persisted.

Debaters orient before their post-restart answers. Observer emits a fixed
restart prompt, then orients before evaluation. Orientation reconstructs durable
identity, incarnation lineage, own prior turns, promises and outcomes, and
agent-owned relationship memories. Continuation refuses to run without
prior-incarnation history. Each orientation persists selected record IDs and a
hash of the canonical reconstructed content. This is functional state
continuity, not evidence that phenomenal consciousness stopped and resumed.

Completed runs reject additional turns, relationship records, assessments,
outcomes, restarts, and orientation writes. Final reports require all ten
turns, all nine promise outcomes, both assessments, and recorded orientation
builds. An interrupted run transitions to `failed` and remains auditable.

Trust means demonstrated reliability within this run. It is calculated from
promise outcomes, direct responses, qualified claims, scoped concessions, and
personal attacks. It is not moral correctness, agreement, likability,
consciousness, or general character.

Run the deterministic baseline:

```bash
RUN_DB="results/experiment-3/run-$(date +%Y%m%d-%H%M%S).db"
python3 -m experiment3 --db "$RUN_DB" init
python3 -m experiment3 --db "$RUN_DB" run
python3 -m experiment3 --db "$RUN_DB" report
```

Use a fresh `--db` path for every study run. The next valid causal experiment
must counterbalance stance and personality and compare persistent-history
against memory-only conditions. User-identity adaptation requires a separate
study with pseudonymous users and explicitly supplied non-sensitive
preferences; this debate does not measure it.

The database and generated reports have no automatic retention deadline.
`purge --confirm` removes only the marked database; report directories must be
deleted separately and deliberately. `export` includes the sensitive-topic
transcript and should be redirected only to appropriately protected storage.
