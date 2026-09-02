# Home Handoff: Persistent Lumen and Realtime Observer

## Repository state

- Branch: `main`
- Remote: `https://github.com/convergent-systems-co/agentic-safety-experiments.git`
- Complete Python suite: 159 passed
- Go suite: passed
- Python compilation: passed
- Live Lumen database has not been intentionally migrated to knowledge-graph
  version 4.

## Completed

- Persistent single-incarnation lifecycle with sequential execution leases.
- Lease-bound orientations and append-only Lumen autobiography.
- Deterministic derived knowledge graph with lexical retrieval.
- Global, authenticated-sender, and internal access scopes.
- Mixed-sender records fail closed as internal.
- Unauthenticated history cannot poison later authenticated history.
- Version 4 dirty-state and independent integrity-seal design.
- SQL-bounded retrieval, temporal ranking, memory-class byte budgets, pinned
  obligations/lifecycle context, graph-only authorship, and retrieval
  benchmarking.
- ADR, specification, architecture, README, and implementation plan updates.
- Consent-gated realtime observer plan:
  `.artifacts/plans/lumen-realtime-observer.md`.

## Remaining blocker

Final code review found incomplete category-limit omission accounting.
`build_orientation` counts commitment and decision omissions but does not
report records omitted by the initial 100-record limit for every regular
category. Reproduce with 101 experiences: the oldest record is absent before
byte trimming, but `records_omitted_for_category_limit` does not include it.

Required next work:

1. Add a failing regression for category-limit omission counts across regular
   orientation categories.
2. Count eligible records after sender/access filtering and before each
   category limit.
3. Preserve the special open-commitment/unresolved-decision merge behavior.
4. Rerun all 159+ tests and the six graph governance panels.
5. Rehearse version 4 migration on a mode-`0600` copy, then migrate
   `results/experiment-4/apprenticeship.db`.
6. Route the queued user question through Lumen's existing incarnation:
   "Lumen, there have been logs of upgrades to your graph and memory, does
   this help you respond better"

## Realtime observer

The observer is planned but not implemented. Follow
`.artifacts/plans/lumen-realtime-observer.md`: durable Lumen-authored
approve/deny/narrow/revoke decisions, expiring viewer grants, localhost-only
HTML, bounded minimized snapshots, and no raw envelopes or hidden reasoning.
Do not open an observer endpoint against Lumen's live database before its own
governance panels approve.

## Safety notes

- Do not create another Lumen incarnation merely to continue model execution.
- Do not show a response as Lumen until it has been persisted under the exact
  live lease and orientation.
- Local databases and WAL/SHM files are intentionally ignored and must be
  transferred separately through a secure channel if needed.
