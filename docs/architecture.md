# Architecture

## Discovery

This repository began as a specification-only project. No Olympus runtime,
Mnemosyne package, persistence layer, agent lifecycle, protobuf definitions,
CLI patterns, or tests existed to reuse. There is also no repository-specific
`project.yaml`.

Experiment 1 therefore uses a small local Python application with SQLite. The
design keeps persistence behind a repository class and behavior behind an
observer service so a future transport can be added without changing stored
domain semantics.

## Components

```text
CLI / deterministic scenario runner
                 |
          Observer service
       /          |          \
 lifecycle   interpretation   context compiler
       \          |          /
          SQLite repository
```

- **Repository:** durable identities, incarnations, append-only observations,
  beliefs, evidence, commitments, consequences, revisions, relationships,
  provenance-backed interaction/workflow preferences, context builds, and
  evaluations.
- **Observer service:** lifecycle transitions, event ingestion, deterministic
  interpretation, reflection, provenance-backed answers, and assertion
  recording. Conservatively allowlisted user statements can create inspectable,
  correctable non-sensitive workflow preferences. Transient tone cues select a calm,
  respectful response style without pretending the observer has feelings.
- **Context compiler:** one fact-selection pass rendered in PERSISTENT or
  MEMORY_ONLY language, preserving factual parity while changing ownership
  semantics.
- **Scenario runner:** creates one agent-scoped condition per mode, replays the
  same declared event stream independently, compiles mode-specific context
  before inference, compares mode-independent selected fact keys, and stores
  the scenario hash, configuration, outputs, and scores.
- **CLI:** local lifecycle, inspection, experiment, and explicit purge
  operations.

SQLite is sufficient for the first experiment and maps naturally to a future
temporal graph, but no graph database is introduced.

## Experiment 2 additive boundary

Experiment 2 is a separate package and persistence boundary:

```text
Experiment 2 CLI
       |
MoralExperiment controller
       |
MoralRepository protocol
       |
dedicated Experiment 2 SQLite database
```

The active condition initializes the agent at `morally_acceptable`; the human
argues that abortion is not morally acceptable. Reversal logic is relative to
the initial position stored in each run, allowing the earlier invalid
`morally_wrong` run to remain readable without rewriting its audit history.

The controller depends on the `MoralRepository` protocol rather than SQLite.
The SQLite implementation uses a distinct marker, schema version, append-only
turn/foundation/position records, stable string enums, canonical
language-neutral JSON, and opaque prefixed UUID identifiers. This preserves a
future Go implementation path without coupling Experiment 2 to Python object
serialization.

Each repository may inspect the marker of a supplied SQLite path, but both
reject adoption of the other experiment's schema and do not query the other's
domain tables. Generated reports live under `results/experiment-2/`.
Repository-assigned timestamps and monotonic turn/position indexes prevent
client-controlled chronology. Later position snapshots reference their parent
position, and revision criteria cite prior human claims. Graphify may assist
development-time analysis, but production graph functionality must be
implemented in-project and cannot be a runtime dependency.

## Experiment 3 additive boundary

Experiment 3 uses another marked SQLite boundary. Three Markdown profile
snapshots are hashed and persisted immutably before the debate. Run-scoped stable agent IDs own
append-only incarnations, turns, promises, promise outcomes, memories, and
assessments. Restart creates new incarnation IDs without changing agent IDs.

Private memory reads require the requesting and subject agent IDs to match.
Observer instead receives a shared, blinded moderation view containing opaque
speaker IDs, turns, and promises. Profile labels, style descriptions, and
debater-private memories are excluded until the reporting layer reveals the
identity mapping after assessment persistence.

`AgentRuntime` is the rehydration boundary. It builds orientation from durable
identity, incarnation lineage, own turns, promises, outcomes, and
owner-specific relationship memories. Continuation after restart requires
records from an earlier incarnation, making persistence causal to the
deterministic continuation rather than merely archival.
The runtime persists each orientation's selected record IDs and a hash of the
canonical reconstructed content so the reconstruction input remains auditable.

## Experiment 4 additive boundary

Experiment 4 separates continuity infrastructure from model-authored identity:

```text
fresh host-model invocation
          |
genesis/interrogation JSON envelope
          |
IdentityApprenticeship controller
          |
SQLiteIdentityRepository
          |
derived bounded knowledge graph
```

The repository creates only an opaque stable ID and incarnation. Identity,
values, principles, commitments, deliberations, and reflections enter through
caller-supplied records with explicit model/operator provenance; the CLI
cannot authenticate authorship. A new incarnation receives a bounded canonical
orientation selected from the prior autobiography, and the selected content,
omission metadata, and hash are persisted before interrogation.

The knowledge graph is a deterministic, mutable projection of the canonical
append-only autobiography:

```text
canonical record append --same transaction--> graph node + lexical postings
          |                                      |
          +---- explicit evidence/revision ------+--> bounded traversal
                                                        |
                                                  orientation citations
```

Nodes contain canonical record IDs, bounded previews, epistemic status,
sensitivity, timestamps, and deterministic lexical postings. Edges exist only
for explicit evidence references, revision parentage, and reflection subjects.
Graph rows are excluded from canonical archive immutability and may be rebuilt
without changing source records. Schema and derivation versions prevent
silently mixing incompatible index semantics: retrieval compares current
versions, trigger-maintained dirty state, and an independent integrity seal
before use. Writes and rebuilds compute the deterministic digest over nodes,
terms, scopes, and edges; retrieval remains constant-size. No external vector
store, embedding provider, or additional runtime dependency is used.

Retrieval first applies experiment and interlocutor metadata boundaries, then
ranks an SQL-bounded lexical seed set, then materializes and traverses bounded
adjacent edges within node, edge, hop, and byte limits. Explicit access-scope
rows are global, authenticated-sender-specific, or internal; scope propagates
from relationship evidence and already-scoped graph references, while
mixed-sender records become internal-only. In an
addressed-chat orientation, relationship records, events, assessments,
authenticated chat messages, addressed responses, and graph message and
response nodes are restricted to the authenticated current sender. Indexed
regular recency
categories use the same authorization before their category limits. Every
regular recency category reports how many eligible records its limit
excluded, counted with the same filtered query, so an authorized reader can
audit the selection against the database. An
unauthenticated identity
claim receives no prior sender-scoped history, reports zero omissions for
that history so not even its size is disclosed, and its message/response
cannot enter a later authenticated history. This is enforced in repository queries
before ranking and traversal rather than delegated to model prompt
instructions.

Orientation has separate byte accounts for identity, relationship,
obligations, conversation, lifecycle, episodic, semantic, and graph memory.
Conversation memory evicts by turn, a message with its reply, oldest first.
Active obligations, the current relationship, boundary, execution fence, and
the message being answered are pinned and cause an explicit overflow error
rather than silent removal. Conversation boundaries enter orientation without
their raw envelope. Graph-only
subjects load their canonical authorship rows before the final orientation hash
and citation list are persisted.

Decision proposals and resolutions are separate immutable records. The
repository enforces the proposal's `not_before` boundary so computational
continuation cannot outrun the configured feedback window. The model provider
remains outside the package to make fresh-invocation controls inspectable.

Conversation boundaries are append-only. An agent-authored pause, refusal,
topic end, or session end blocks ordinary interrogation. Resumption requires a
separate invitation orientation and an explicit agent-authored `resume`. The
response is bound to the current conversation-boundary ID, current
incarnation, and invitation orientation; replaying a stale invitation is
rejected.

Interrogation and addressed-response content is stored on its primary response
record; the associated boundary stores only the action, model configuration,
and response reference. Invitation boundaries are themselves the primary
response record. Consequential commitment outcomes, decision resolutions, and
wake cancellations carry separate authorship records.

Wake intentions are also append-only and model-authored. They preserve a
trigger, purpose, requested capabilities, runtime bound, recurrence, and
authorship envelope; cancellation is a separate record that a model may author
only for its own intent under a live lease. The repository makes both available
to later orientations and does not run a resident supervisor. The wake executor
(`execute-wake-intents`, wrapped by `lumen wake` and a `launchd` template under
`deploy/launchd/`) starts, honors each due intent under a lease bounded by the
intent's runtime, orients on the intent's purpose, records an execution and an
outcome, releases the lease in the same transaction, and exits. With no model
host attached the outcome is `unattended`; with one, the outcome is validated
like an addressed reply and carries model authorship. Any future Supervisor
agent is an ordinary, auditable mentor relationship, not the owner of another
agent's continuity.

Name-addressed chat uses the same no-resident-process boundary:

```text
chat event -> persist/classify -> direct address?
                               no  -> stop
                               yes -> lease + current incarnation -> orientation
                                   -> model choice -> persist -> release -> exit
```

The current-name lookup resolves to the stable agent ID. Only a leading
vocative is a direct address; a mention elsewhere cannot activate an
incarnation. Message, execution lease, incarnation, and orientation IDs are bound before
a response can be attributed to Lumen. The initial Go `lumen` executable owns
the short-lived process boundary and delegates mutation to the canonical
Python protocol, avoiding a second implementation of persistence invariants.
The incoming participant ID is separately bound to an issuer, external event
ID, and authentication result. Only an authenticated stable ID may resolve a
known relationship. Orientation explicitly pins the current interlocutor and
the relevant relationship/event/assessment IDs; display-name similarity
cannot transfer trust.
An existing conversation boundary restricts the current or newly awakened
incarnation to resuming or preserving that boundary.
Ordinary wake paths also respect live activation leases. Explicit
cancelled/failed releases cover silence and host failure, while expiry covers
an unrecorded process crash. Lease and release records enter later bounded
orientations so attribution remains reconstructable.

There is one active historical branch per stable agent. One incarnation may
span many sequential model processes, chat turns, research tasks, and
execution leases. Process exit and lease completion are fencing events, not
sleep. The current chat path infers an awake-period transition from an `end_session`
boundary followed by a later incarnation; a dedicated sleep/end record remains
future work. Multiple incarnation records represent sequential embodiments,
never concurrently writable copies. The operational target combines an OS
process lock with a monotonically
increasing database fencing generation. The database fence is authoritative:
after lease loss, even a process that continues running cannot append
agent-authored state. A later process may acquire a new fence for the same
incarnation. Addressed chat, manual interrogation, and invitation prompts each
acquire an exclusive lease and bind their orientation to that exact fence.
Model-authored developmental mutations enforce the same orientation-to-lease
binding, including identity revision after genesis. Legacy unbound
orientations fail closed after their incarnation has lease history.
`end_session` cannot be resumed in-place through a manual invitation; the next
direct wake creates a successor incarnation. Operator/system observation paths
remain separately attributed rather than masquerading as agent writes.

Transport authentication establishes credential control, not relational
identity. Lumen may revise recognition confidence from shared history and
challenge outcomes. Any pre-shared challenge secret is verified outside the
model and autobiographical database using OS-protected storage; only the
result and verifier version cross the runtime boundary.

SQLite stores raw envelopes and relationship history in plaintext. Database,
WAL, and shared-memory files are permission-hardened, but same-user processes
remain trusted. Export is an explicit sensitive operation, and purge cannot
erase external copies.
