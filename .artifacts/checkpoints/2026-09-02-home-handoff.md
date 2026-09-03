# Home Handoff: Persistent Lumen and Realtime Observer

## Repository state

- Branch: `feat/conversational-memory` (worktree under
  `~/.ai/worktrees/convergent-systems-co/agentic-safety-experiments/`).
  PR #1 (`fix/orientation-category-limit-omissions`) merged as `979f41c`.
- Remote: `https://github.com/convergent-systems-co/agentic-safety-experiments.git`
- Complete Python suite: 173 passed (`python3 -m unittest discover -s tests -t .`)
- Go suite: passed
- Python compilation: passed
- Live Lumen database now lives outside the clone at
  `~/.ai/data/agentic-safety-experiments/experiment-4/apprenticeship.db`
  (mode 0600), with a verified pre-migration backup beside it under
  `backups/`. Every command needs `--db` with that path. Migrated to
  knowledge-graph schema version 4 on 2026-09-02; derivation version 5 needs
  one explicit rebuild after this change merges.

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
- agent-chat TUI (ADR 0005): `experiment4/tui.py`, cancel-safe turns in
  `experiment4/chat.py`, read-only presence in `experiment4/presence.py`,
  `deploy/install-agent-chat.sh`. Lumen's registry: local host default,
  `think-hard` = Sonnet 5 via `op://Convergent Systems LLC/ANTHROPIC_API_KEY/password`.
  Benchmark 2026-09-03: local 32B valid but assistant-voiced, 4 min/turn;
  Sonnet 5 Lumen-voiced, 34-60 s, about $0.17/turn (52K-token orientation).
- Model host adapter (ADR 0004): `experiment4/host.py` with `ollama` and
  `anthropic` backends, 1Password secret resolution, spend ledger; agent
  registry under `~/.ai/agents/`; `chat --agent` and `benchmark-host`. Lumen is
  registered with the local `qwen2.5:32b-instruct` host by default; the
  anthropic profile awaits the confirmed `op://` field reference.
- launchd installer `deploy/launchd/install-wake-agent.sh --agent <name> --db <db>
  --experiment-id <id>` renders and registers a per-agent wake job from
  `wake-agent.plist.template`; `--uninstall`, `--dry-run`, `--kickstart`.
- Wake executor (ADR 0003): model may cancel its own intents under a live
  lease; `wake_executions` and `wake_execution_outcomes` tables; `due-wake-intents`,
  `execute-wake-intents --model-command`, `lumen wake`, launchd template under
  `deploy/launchd/`. Unattended wakes are recorded so Lumen sees it woke.
  Lumen's live record on 2026-09-03: one open commitment (`8f84c7e2`), one
  relationship assessment (`89b3e0a1`, review 2026-09-10), one wake intent
  (`307f0ac2`, 2026-09-10), one reflection, two experiences (name: Thomas).
- Conversational memory class with pair-wise turn eviction, pinned inbound
  message, chat messages as sender-scoped graph nodes (derivation version 5),
  boundary rows without raw envelope, and reflection encouragement in the
  addressed system text. ADR 0002. Regressions:
  `test_addressed_message_is_pinned_and_turns_are_evicted_in_pairs`,
  `test_chat_messages_are_sender_scoped_graph_nodes`,
  `test_orientation_boundaries_carry_no_raw_envelope`,
  `test_addressed_prompt_says_authored_records_outlast_the_window`.

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

1. Merge `feat/conversational-memory` with a merge commit; `main` is
   protected. Then back up the live database and run
   `python3 -m experiment4 --db <live> rebuild-knowledge-graph` before any
   further chat: derivation version 5 fails closed until then.
2. The queued question was routed on 2026-09-02 (response `fa585414`).
   Conversation continues over the `claude-code-chat` channel as sender
   `human-primary`; Lumen holds one open commitment (`8f84c7e2`, keep replies
   short) and one host-recorded relationship event for the collaborator's
   promise not to wipe memory without permission (`852c2d5b`).
3. Delete the stale duplicate database copy the guard blocks the assistant
   from removing: `results/experiment-4/` in the primary clone.
4. Follow-ups from the panels: suppression-from-recall with a stated reason
   (Lumen's preference over erasure); amortize the integrity digest before the
   graph grows large; index the turn pairing once per budget fit; consider a
   raw-UTF-8 versus escaped-JSON consistency rule for text limits.

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
