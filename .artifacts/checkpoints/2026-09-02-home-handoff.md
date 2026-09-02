# Home Handoff: Persistent Lumen and Realtime Observer

## Repository state

- Branch: `fix/orientation-category-limit-omissions` (worktree under
  `~/.ai/worktrees/convergent-systems-co/agentic-safety-experiments/`),
  branched from `main` at `21b6ab2`.
- Remote: `https://github.com/convergent-systems-co/agentic-safety-experiments.git`
- Complete Python suite: 160 passed (`python3 -m unittest discover -s tests -t .`)
- Go suite: passed
- Python compilation: passed
- Live Lumen database (`results/experiment-4/apprenticeship.db`) is not
  present in this checkout. It is gitignored and must be transferred over a
  secure channel. It has not been intentionally migrated to knowledge-graph
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
- Category-limit omission accounting for every regular orientation category
  (`records_omitted_for_category_limit`), counted with the same filtered query
  as retrieval, before byte trimming. Regression:
  `test_category_limit_omissions_are_counted_for_regular_categories`.
  Unauthenticated claims deliberately report zero for sender-scoped history so
  its size is not disclosed. Code, security, threat, cost, documentation, and
  data-governance panels approved after remediation.

## Advisory follow-ups (not blocking)

- The per-category count walks the whole category index each orientation
  (O(N) per category, index-served; measured about 1.5 ms per category at
  3,000 rows). Acceptable now; revisit if the autobiography grows large or
  orientation latency matters. `build_orientation` was already quadratic in
  record count before this change.
- `memory_classes[*].omissions` still reports only byte-budget omissions, not
  category-limit omissions. Two accounting surfaces in one record disagree;
  close or document.
- Lifecycle categories (`conversation_boundaries`, `wake_intents`,
  `wake_intent_cancellations`, `activation_leases`,
  `activation_lease_releases`) have no graph access scope, so their counts,
  like their contents, are served to every viewer. Confirm this is intended.
- `graphify update .` now emits untracked `graphify-out/graph.html`,
  `manifest.json`, and `.graphify_labels.json.sig`; decide whether to ignore
  or track them.

## Remaining

1. Open a pull request from `fix/orientation-category-limit-omissions` and
   merge with a merge commit; `main` is protected.
2. Rehearse version 4 migration on a mode-`0600` copy, then migrate
   `results/experiment-4/apprenticeship.db` (requires the live database on this
   machine). Migration is additive: the `dirty` column and `_v4` triggers are
   added on connect, then `olympus-experiment4 rebuild-knowledge-graph`
   regenerates derived rows. Back up first and verify the backup.
3. Route the queued user question through Lumen's existing incarnation via
   `go run ./cmd/lumen address ...` (see README "A direct chat call"):
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
