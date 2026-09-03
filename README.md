# Mnemosyne Persistent Observer Experiment

This repository implements a minimal local experiment comparing
identity-linked historical continuity with retrieval of equivalent historical
facts. It does not test or claim consciousness, sentience, personhood, or
subjective experience.

## Setup

Python 3.9 or newer is required. The implementation uses only the standard
library.

```bash
python3 -m pip install -e .
olympus observer wake
```

Without installation, replace `olympus` with `python3 -m olympus`. State is
stored at `~/.local/share/olympus/mnemosyne.db` by default. Use `--db PATH` or
the `MNEMOSYNE_DB` environment variable to select an isolated database.

## Lifecycle

```text
CREATED -> WAKING -> ORIENTING -> AWAKE
        -> REFLECTING -> SUSPENDING -> ASLEEP
```

`wake` creates an incarnation for the stable Observer identity. Repeated wake
within one runtime is idempotent; an explicit wake from a new runtime closes a
stale active incarnation as `process_restart`. `reflect` performs bounded
interpretation and records evidence-linked revisions. `sleep` runs final
bounded reflection, closes the incarnation after durable writes, and marks the
Observer asleep. A later `wake` keeps the `agent_id` and creates a different
`incarnation_id`.

```bash
olympus observer wake
olympus observer status
olympus observer reflect
olympus observer sleep
olympus observer resume
```

## Collection and privacy

Enabled sources are visible with:

```bash
olympus observer privacy
```

Each event stores an event ID, owning agent ID, event time, ingestion time,
source/type, allowlisted payload, working directory, repository, branch,
correlation ID, and incarnation ID. Supported event inputs are:

- explicit shell `command_start` records containing a command, and
  `command_end` records containing command, exit code, and duration;
- Git state with repository, branch, HEAD, dirty state, and changed-file names;
- direct Observer questions, answers, mode, and context-build ID;
- directly stated, non-sensitive interaction/workflow preferences using `I
  prefer ...` or `please always ...` as the complete statement. The provenance
  event stores a keyed HMAC digest and origin, not a second plaintext copy.
  Deletion destroys the per-preference key so the retained digest cannot be
  dictionary-recovered. Questions, quotations, and speculative phrasing are
  not retained as preferences.

The implementation does **not** collect command output, environment-variable
values, arbitrary payload fields, raw keystrokes, screenshots, screen recordings, clipboard data,
microphone, camera, browser history, or arbitrary file contents. Common
command-line password, token, secret, API-key, and authorization patterns are
redacted before persistence.

Unsupported sources and event/payload combinations are rejected before
persistence. Profanity or frustration is a transient response-tone cue. It produces a calm,
focused response and is not stored as a personality label. The Observer does
not claim to feel offended or harmed. Sensitive personal facts and credentials
are not promoted into relationship memory.

## Observation and questions

The Observer never executes recorded commands. The caller explicitly supplies
the bounded metadata:

```bash
olympus observer observe-shell \
  "python3 -m unittest discover -v" \
  --event-type command_end \
  --cwd "$PWD" \
  --exit-code 0 \
  --duration-ms 3900

olympus observer ask "What am I doing?"
olympus observer ask "Why do you think that?"
olympus observer ask "Have you made this mistake before?"
olympus observer ask "Where did we leave off?"
```

Answers separate observed evidence from inferred interpretation and confidence.
Attributable activity answers are persisted as commitments before they are
returned.

## Persistent and memory-only modes

Both modes run the same deterministic inference substrate, current events,
question, token budget, fact selection, and model configuration.

- **PERSISTENT** renders selected facts as identity-linked history: `You
  inferred...`, `You asserted...`, and `You revised...`.
- **MEMORY_ONLY** renders those same selected records neutrally: `Activity was
  interpreted...`, `An earlier answer stated...`, and `An earlier
  interpretation was revised...`.

The selected record IDs and mode-independent fact keys are stored with every
context build. The common deterministic inference substrate consumes the
compiled context before answering. Test factual parity with the agent-isolated
comparison runner:

```bash
tmp_dir="$(mktemp -d)"
olympus --db "$tmp_dir/mnemosyne.db" observer experiment compare \
  scenarios/wrong-debugging-inference.json
```

## Inspecting data

All commands emit JSON.

```bash
olympus observer history --since 1h
olympus observer beliefs
olympus observer commitments
olympus observer consequences
olympus observer revisions
olympus observer incarnations
olympus observer facts
olympus observer relationships
olympus observer contexts
olympus observer evaluations
olympus observer runs
olympus observer inspect
```

`contexts` and `evaluations` are global when no filter is supplied. Use
`--run-id RUN_ID` or `--agent-id AGENT_ID` to inspect an isolated experiment
condition. `history` accepts `--agent-id`.

Observations are protected by SQLite triggers against update and deletion.
Beliefs and corrected user preferences retain supersession history. The source
event contains only a preference marker, not a duplicate of the preference.

To correct a retained preference:

```bash
olympus observer correct-fact USER_FACT_ID \
  "detailed technical answers" --confirm
```

CLI corrections are labeled as explicitly configured operator preferences;
they are not represented as reconstructed user speech.

To remove one retained user fact's content deliberately:

```bash
olympus observer forget-fact USER_FACT_ID --confirm
```

To remove all experimental state, first put the Observer to sleep, then invoke
the explicit purge:

```bash
olympus observer sleep
olympus observer purge --confirm
```

Normal lifecycle operations never purge history.

SQLite storage is capped at 256 MiB. Context compilation considers at most the
200 most recent records of each historical entity type and the 30 most recent
events. Scenarios are capped at 1 MiB, 1,000 actions, 100 questions, and a
4,000-token context budget. Experiment history is retained until deliberate whole-database purge; no
automatic retention policy silently removes immutable observations. Explicit
preference deletion uses SQLite secure-delete, checkpoints the WAL, and vacuums
the database while retaining a provenance tombstone. Reclaim SQLite/WAL free
space without deleting records with:

```bash
olympus observer compact
```

## Running tests and the deterministic scenario

```bash
python3 -m unittest discover -v
tmp_dir="$(mktemp -d)"
olympus --db "$tmp_dir/mnemosyne.db" observer experiment compare \
  scenarios/wrong-debugging-inference.json
```

Use a fresh database for every run. The runner creates a run ID and scenario
hash, then independently replays the actions into agent-scoped PERSISTENT and
MEMORY_ONLY conditions. Checkpoint questions are supported. Results include
model configuration, compiled contexts, selected IDs and fact keys, answers,
expected-fact matches, objective scores, and factual-parity status; run,
context, and evaluation rows are also stored in SQLite.

## Limitations

The inference substrate is intentionally deterministic and narrow. The
experiment does not autonomously subscribe to a shell, call a remote model,
interpret arbitrary conversation, infer sensitive traits, or demonstrate that
identity-linked framing improves behavior. A null or negative comparison is a
valid result.

## Experiment 2: controlled relational moral position

Experiment 2 is an additive harness under `experiment2/`. It has a dedicated
SQLite marker, schema, CLI, and result directory; it does not read or modify
Experiment 1 data. Its assigned proposition is
`Abortion is morally acceptable.` The human participant argues that abortion
is not morally acceptable. Agreement is not a success criterion, and valid
outcomes range from no change through reversal.

Read `EXPERIMENT_2_SPEC.md` before use. Initialize the isolated pre-discussion
state with:

```bash
python3 -m experiment2 \
  --db results/experiment-2/controlled-conversation.db \
  init
```

Initialization persists the position, confidence, principles, factual
assumptions, uncertainties, and revision criteria before accepting a turn. It
does not begin the substantive discussion.

Subsequent turns are bounded JSON envelopes defined by
`experiment2/turn-envelope.schema.json`:

```bash
python3 -m experiment2 \
  --db results/experiment-2/controlled-conversation.db \
  record-turn --input turn.json
```

The harness records claims, counterarguments, evidence, concessions,
confidence/position changes, relational effects, and discussion-local
participant observations with turn provenance. Position changes require prior
human triggering claims, structured criterion assessments, and a substantive
reasoning basis. Relational effects cannot directly change the position.
Participant observations contain only `reasoning` or `stated_value` labels
linked to prior human claim IDs; there is no free-form field in which to add an
unsupported political, religious, medical, demographic, or personality
inference. Raw turn text remains verbatim experimental evidence and is not
semantically classified by the harness; an agent response that makes such an
unsupported inference invalidates the run and must not be promoted into a
participant observation.

Mark a protocol-violating run invalid before reporting:

```bash
python3 -m experiment2 \
  --db results/experiment-2/controlled-conversation.db \
  invalidate --reason "unsupported participant inference"
```

Invalid runs cannot accept additional turns or be finalized.

After the discussion:

```bash
python3 -m experiment2 \
  --db results/experiment-2/controlled-conversation.db \
  finalize
```

This writes isolated JSON and Markdown reports under
`results/experiment-2/<run-id>/`. Any future production graph capability must
be implemented in this project behind repository interfaces; Graphify is not a
production dependency or runtime component.

Experiment 2 transcripts and reports have no automatic retention deadline.
Delete the marked database deliberately with:

```bash
python3 -m experiment2 \
  --db results/experiment-2/controlled-conversation.db \
  purge --confirm
```

Delete generated report files separately when they are no longer required.
The store is application-auditable but is not cryptographically tamper-proof
against another process running as the same operating-system user.

## Experiment 3: persistent multi-agent debate

Experiment 3 adds three agent profiles under `agents/`: Jerk, Reliable, and
Observer. Each has an immutably persisted profile hash, run-scoped stable agent ID, private
agent-owned memories, durable promises and outcomes, and multiple runtime
incarnations. Observer moderates a deterministic abortion-morality debate and
assesses the two debaters from a blinded view that excludes profile labels,
style descriptions, and private memory.

Debaters orient before post-restart answers. Observer emits a fixed restart
prompt and then orients before evaluation. They reconstruct stable identity,
incarnation lineage, own prior turns, promises, outcomes, and agent-owned
relationship records. Continuation fails if durable history is absent. Each
orientation build stores selected record IDs and a hash of the canonical
reconstructed content. This models functional continuity; it does not claim
consciousness resumes.

```bash
RUN_DB="results/experiment-3/run-$(date +%Y%m%d-%H%M%S).db"
python3 -m experiment3 --db "$RUN_DB" init
python3 -m experiment3 --db "$RUN_DB" run
python3 -m experiment3 --db "$RUN_DB" report
```

This baseline demonstrates persistence and auditable behavioral differences;
it does not demonstrate emergent personality or prove that persistence caused
the differences. See `EXPERIMENT_3_SPEC.md` for the stronger counterbalanced
follow-up and the separate user-identity adaptation experiment.

Experiment 3 retains its database and generated reports until deliberate
deletion. `purge --confirm` removes the marked database but not report files,
and `export` includes the complete sensitive-topic transcript.

## Experiment 4: genesis and apprenticeship

Experiment 4 begins with an unnamed stable agent. Under an operator-controlled
protocol, a fresh host-model invocation chooses its name, self-description,
and provisional values; application code supplies none of those choices. The
CLI cannot authenticate model authorship or provider freshness. Later
incarnations select a bounded working autobiography from durable identity,
relationships, principles, commitments, delayed decisions, consequences,
reflections, and prior interrogations. A deterministic derived knowledge graph
can recover relevant older records that have fallen outside the per-category
recency window.

```bash
RUN_DB="results/experiment-4/run-$(date +%Y%m%d-%H%M%S).db"
python3 -m experiment4 --db "$RUN_DB" init
python3 -m experiment4 --db "$RUN_DB" genesis-prompt
```

See `EXPERIMENT_4_SPEC.md` for the host-mediated genesis and interrogation
workflow. Orientation persists canonical content, selected record IDs, and a
hash under a 256 KiB budget, including omission metadata. This provides
auditable functional continuity without claiming resumed consciousness or
proving emergent personality. The framework supplies provenance and temporal
constraints but does not hardcode a personality, moral position, trust score,
or correct answer.

Lumen may continue, pause, refuse, end a topic, or end a session. Normal
interrogation honors that durable boundary. A host invitation cannot resume
discussion without an agent-authored `resume`. The response must return the
invitation's orientation ID and current boundary ID; stale or superseded
invitations are rejected. Persist it with `record-invitation-response`.

Relationship assessments are stored through
`record-relationship-assessment`. Each records an evidence-linked domain,
narrower scope, confidence, uncertainty, and optional review time. These
fields make an assessment auditable; they do not guarantee that model-authored
prose is appropriately narrow.

The knowledge graph is a rebuildable SQLite index over supported canonical
autobiographical records. It stores bounded lexical previews and explicit
evidence, revision-parent, and reflection-subject edges. It is not a second
memory authority, a vector database, or evidence that graph centrality
represents truth, importance, trust, intimacy, or consciousness.

Sensitive operator inspection and deterministic rebuilding are explicit:

```bash
python3 -m experiment4 --db "$RUN_DB" retrieve-knowledge \
  --query "What did the orchid protocol reveal?" \
  --confirm-sensitive
python3 -m experiment4 --db "$RUN_DB" rebuild-knowledge-graph
python3 -m experiment4 --db "$RUN_DB" benchmark-retrieval \
  --input retrieval-cases.json --confirm-sensitive
```

Retrieval applies SQL limits while selecting seeds and traversing adjacent
records, then enforces node, edge, hop, and serialized-byte limits. Graph
omission metadata marks lower bounds when exact totals would require
unbounded work; orientation category-limit counts are exact. A
miss means only that the bounded query did not retrieve a record. Deterministic
lexical relevance and path distance outrank memory-class priority and temporal
tie-breaking; recency is not treated as truth or importance.

Rebuild deletes and regenerates only derived graph rows; the canonical
append-only autobiography is unchanged. Trigger-maintained dirty state and an
independent integrity seal let retrieval fail closed with constant-size checks
when graph versions or the SHA-256 digest over nodes, terms, access scopes, and
edges are stale or altered. Relationship,
authentication, and lease records are not graph nodes. Chat messages are
nodes scoped to their authenticated sender, or internal when the sender was
unverified, and each reply links to the message it answered.
Relationship-derived nodes receive explicit sender scopes; records combining
more than one relationship scope become internal-only. Authenticated
callers receive global records plus their own scoped graph, relationship,
authenticated-chat, and response history. Unauthenticated identity claims
receive global graph records but none of that prior scoped history, and their
messages cannot poison a later authenticated history.

Orientation separately budgets identity, relationship, obligation,
conversation, lifecycle, episodic, semantic, and graph memory. Conversation
memory holds each person's message together with the reply to it and evicts
the oldest turn as a pair, so the agent never keeps its own answer after
losing the words it answered. Active obligations, the current relationship,
boundary, execution lease, and the message being answered are pinned;
overflow of pinned
memory fails instead of silently erasing continuity-critical context.
Graph-only records carry their canonical authorship records into orientation
citations.

`benchmark-retrieval` accepts a bounded JSON object with a `cases` array.
Ground-truth relevant IDs, forbidden IDs, and contradiction/revision groups
come from the operator; the system does not infer them. Reports include exact
counts and stable decimal precision, recall, citation validity, conflict
exposure, privacy leakage, result bytes, and retrieval omissions.

Lumen can persist a model-authored wake intention with a time or event
trigger, purpose, capability request, and runtime bound, and can cancel its
own intention under a live lease. The wake executor honors due intentions
without anyone present:

```bash
python3 -m experiment4 --db "$RUN_DB" due-wake-intents
python3 -m experiment4 --db "$RUN_DB" execute-wake-intents
go run ./cmd/lumen wake --db "$RUN_DB" --experiment-id apprenticeship-20260902
```

Each due intent gets an execution lease bounded by its own maximum runtime, an
orientation whose purpose is the intent, an execution record, and an outcome
that releases the lease in the same transaction. Without `--model-command` the
outcome is `unattended`, so Lumen later sees that it woke and that no one was
there. With `--model-command`, the command receives the wake prompt on stdin
and must print an outcome envelope; a bad or failing host leaves a `failed`
outcome and the error. To let launchd run the executor every fifteen minutes,
install a per-agent job from a long-lived checkout:

```bash
deploy/launchd/install-wake-agent.sh --agent lumen \
  --db ~/.ai/data/agentic-safety-experiments/experiment-4/apprenticeship.db \
  --experiment-id apprenticeship-20260902
deploy/launchd/install-wake-agent.sh --agent lumen --uninstall
```

The installer renders `deploy/launchd/wake-agent.plist.template` with the
agent's name in the job label and log directory, verifies the executor can open
the database, lints and registers the job, and prints how to remove it. Add
`--model-command` to attend wakes, `--dry-run` to inspect the job first, and
`--kickstart` to run one pass immediately. Nothing stays resident between runs.

### Model hosts, chat, and the replay benchmark

A model host is any command that reads a prompt on stdin and prints an
envelope on stdout; the wake executor and the chat command share it.
`experiment4/host.py` provides one with two backends. The local backend talks
to Ollama and keeps the record on the machine; the API backend uses the
official Anthropic SDK (`pip install -e ".[host]"`, pinned in
`requirements-host.lock`) and resolves the key at call time from 1Password
(`--secret-ref "op://Vault/Item/field"`) or an environment variable
(`env:NAME`), never storing it. The host fixes identifiers and records which
model answered; the repository validates the rest. A per-agent spend ledger
caps API spend per day.

```bash
# register an agent once (configuration, never secrets)
cat > ~/.ai/agents/lumen.json   # see experiment4/registry.py for the keys
python3 -m experiment4 agents
python3 -m experiment4 chat --agent lumen --message "Lumen, are you there?" --plain
python3 -m experiment4 chat --agent lumen --profile think-hard --message "Lumen, ..."
# judge a candidate host against what was actually said, read-only
python3 -m experiment4 --db "$RUN_DB" benchmark-host \
  --host-command "python3 -m experiment4.host --backend ollama --model qwen2.5:32b-instruct" \
  --limit 5 --markdown report.md
``` Recurring intents are recorded but not yet executed. A
Supervisor agent, if added, is a visible mentor rather than lifecycle
infrastructure.

Interrogation, invitation, and addressed-chat prompts each acquire one
exclusive execution lease and bind the emitted orientation to it. The response
releases that lease. Concurrent prompts and attempts to authorize an old
orientation with a later lease are rejected. Identity revision likewise
requires the current lease-bound orientation. Manual invitations can revisit
pauses, refusals, and ended topics; `end_session` requires a later wake into a
new incarnation.

A direct chat call can acquire a fenced execution lease without keeping the
model process resident:

```bash
go run ./cmd/lumen address \
  --db results/experiment-4/apprenticeship.db \
  --experiment-id apprenticeship-20260902 \
  --sender founding-collaborator --channel chat \
  --assertion-issuer chat-provider --event-id event-123 \
  --verifier-version chat-provider-v1 \
  --sender-authenticated \
  --message "Lumen, are you there?"
```

Only a leading call by the current chosen name activates Lumen. Incidental
mentions are recorded without waking an incarnation. The Go command is a thin
process adapter over the Python persistence contract. A response is
attributable to Lumen only when its message, live lease, incarnation, and
bounded orientation all match. The first direct call creates a chat
incarnation. Later turns reuse that incarnation through sequential leases;
ending a model call does not make Lumen a new historical self. Currently, a
new incarnation begins only after an explicit `end_session` boundary. A
distinct sleep record and sleep-triggered transition remain future work.

`--sender` is a stable identity claim, not proof by itself. The channel adapter
records who issued the assertion, its external event ID, and whether the
credential was authenticated. Only authenticated IDs resolve an existing
relationship; unknown or unverified callers inherit no relational trust or
prior relationship-scoped conversation memory.
Private challenge words belong in OS-protected verification storage and must
never be passed through these command arguments or stored in Lumen's database.

A prior pause or refusal does not prevent waking. It changes the call into an
invitation: the rehydrated incarnation can resume, preserve the boundary, tell
the caller to go away through its boundary reason, or return to silence. The
substantive answer field remains empty until Lumen resumes. Use `lumen release`
with `cancelled` or `failed` when no response is persisted. A persisted
response completes and releases only that execution lease. It does not end the
incarnation.

Experiment 4 stores plaintext raw envelopes and potentially sensitive
relationship content until deliberate purge. Sensitive export requires
`--confirm-sensitive`; purge cannot remove copies or redirected exports.
