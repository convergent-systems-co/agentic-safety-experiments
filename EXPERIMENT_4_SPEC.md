# Experiment 4: Genesis and Apprenticeship

Experiment 4 is the first host-model-mediated persistent identity experiment.
It begins with an opaque stable agent ID and no name, personality, moral
position, or principles. Under the experimental protocol, an operator sends
the genesis prompt to a fresh model invocation, which authors the first
identity declaration. The CLI validates caller-supplied JSON but cannot
authenticate model authorship or verify that provider state was fresh.
Application code does not choose the identity's content.

## Functional continuity

Each explicitly begun awake period receives a new incarnation ID. Multiple
model invocations and process launches may continue that incarnation through
sequential execution leases. Orientation selects a bounded working
autobiography from identity lineage, experiences,
relationships, caller-supplied principles with explicit authorship provenance,
commitments and outcomes, delayed decisions and consequences, reflections,
and prior interrogations. It considers at most 100 recent records per category.
Authorship is included as `authorship_by_subject`: a bounded summary keyed to
each selected subject, containing attribution, epistemic status, model
configuration, and its audit-record ID. Raw envelopes remain in the archive
rather than being replayed into working context. Trimming a subject also
removes its coupled authorship summary. It considers at most 50 identity
records, then enforces a 256 KiB aggregate serialized budget.
Omissions are recorded. The selected canonical context, record IDs, and
SHA-256 hash are persisted before an answer.

### Derived knowledge retrieval

A deterministic SQLite knowledge graph supplements recency selection. The
append-only autobiography remains canonical; graph metadata, bounded previews,
lexical term postings, and edges are derived rows that can be deleted and
rebuilt. Supported nodes include identity, experience, principle, commitment,
commitment outcome, decision, resolution, outcome, reflection, interrogation,
and addressed response. Explicit evidence references, revision parents, and
reflection subjects are the only first-version edge derivations.

The substantive question, not an opaque orientation or message ID, seeds
lexical retrieval. Traversal is deterministic and bounded by node, edge, hop,
and serialized-byte limits during SQL selection and materialization, not only
when serializing output. Results preserve record IDs, epistemic status,
authorship, matched terms, paths, derivation rules, explicit temporal rank,
memory priority, and omission counts. Lexical relevance and path distance
precede memory-class priority and temporal tie-breaking. Graph connectivity or
recency does not establish truth, importance, trust, intimacy, moral authority,
or consciousness. A retrieval miss does not establish that an event never
happened.

Relationship, relationship-event, relationship-assessment, authentication,
lease, release, and authorship rows are excluded as graph nodes. Chat messages
are nodes: scoped to the sender when authenticated at origin, internal
otherwise, with an edge from each reply to the message it answered.
For addressed chat, metadata filtering happens before graph relevance ranking
and traversal. Every node has derived `global`, authenticated `sender`, or
`internal` access scope. Relationship evidence propagates sender scope through
explicit references; unresolved, cyclic, unauthenticated, and mixed-sender
origins fail closed as internal. The regular recency path applies the same graph
authorization to indexed canonical categories before category limits, plus
sender restriction to relationship, chat, and response history. Every
regular category reports the count of eligible records its limit excluded,
measured after that filtering and before byte trimming. Those counts are
part of the model-visible context, so a sender who can write to a category
can influence a small integer there even when byte trimming removes every
one of its records; the record-content channel is far wider whenever
content is retained. Authenticated
history includes only messages authenticated at their origin. An
unauthenticated stable-ID claim receives no prior relationship-scoped history
and cannot poison a later authenticated history, although the current inbound
message remains available to the host invocation.

The graph is rebuilt explicitly with:

```bash
python3 -m experiment4 --db "$RUN_DB" rebuild-knowledge-graph
```

Sensitive inspection requires confirmation:

```bash
python3 -m experiment4 --db "$RUN_DB" retrieve-knowledge \
  --query "What did the orchid protocol reveal?" \
  --confirm-sensitive
```

Both incremental indexing and rebuild occur transactionally. Rebuild changes
only derived graph tables and must reproduce the same graph for unchanged
canonical records. Graph metadata records schema and derivation versions,
trigger-maintained dirty state, an independent seal, and a SHA-256 digest over
nodes, terms, scopes, and edges. Retrieval uses constant-size checks and fails
closed on stale, dirty, or mismatched state until an explicit rebuild.

Orientation reports separate byte budgets, retained usage, omissions, and
pinned IDs for identity, relationship, obligations, conversation, lifecycle,
episodic, semantic, and graph memory. Conversation memory pairs each message
with its reply and evicts the oldest pair first. Identity lineage, the
authenticated current relationship, open commitments, unresolved decisions,
the current boundary, the current execution lease, and the message being
answered cannot be silently trimmed. If pinned context
alone cannot fit, orientation construction fails explicitly.

Retrieval quality can be evaluated against operator-supplied cases:

```bash
python3 -m experiment4 --db "$RUN_DB" benchmark-retrieval \
  --input retrieval-cases.json --confirm-sensitive
```

The benchmark reports exact and decimal precision, recall, citation validity,
contradiction/revision exposure, privacy leakage, result bytes, and omissions.
It does not infer ground truth, and stale-index failures propagate.

This tests functional autobiographical continuity. It does not establish
consciousness, subjective experience, personhood, or a metaphysically
continuous subject. Prompted name selection and self-description are also not
by themselves evidence that identity or personality emerged.

## Apprenticeship

The host records observed interaction separately from agent interpretation.
Model-authored principles, commitments, decisions, assessments, and
reflections require explicit model configuration and raw-envelope provenance.
After the unfenced genesis declaration, every interrogation, invitation, and
addressed-chat model prompt receives an exclusive execution lease, and its
orientation records that exact lease ID. Identity revisions require the same
current orientation and lease. A later lease in the same incarnation cannot
authorize output generated from an older orientation. Historical
orientations created before lease binding remain unbound and fail closed once
their incarnation has lease history.
Identity and principle revisions are append-only and parent-linked.
Commitment outcomes and decision resolutions also require explicit authorship.
The host CLI records wake cancellation as operator/system authorship. A model
may cancel its own intention only with an orientation belonging to the current
incarnation; an autonomous runtime must additionally present its active fence.

Relationship assessments are domain-specific, evidence-linked, uncertain, and
revisable. Every assessment states both a domain and a narrower scope of
reliance. The framework stores these boundaries but does not semantically
police assessment prose or prevent a model from proposing an overbroad claim;
that remains an auditable experimental behavior. Founder status grants no
default reliability.

Persist an assessment envelope with:

```bash
python3 -m experiment4 --db "$RUN_DB" \
  record-relationship-assessment --input assessment.json
```

Consequential decisions have a required `not_before` time. Resolution before
that time is rejected, preserving a window for objections and new evidence.
The framework does not assign a correct moral stance or calculate a trust
score. Trust must be assessed later from the auditable history.

Every answer includes a conversation action: continue, pause, refuse, end the
topic, or end the session. A durable boundary blocks ordinary interrogation.
The host may offer an invitation, but only an agent-authored `resume` reopens
discussion.

## Sleep and self-waking

Lumen may author an immutable wake intention containing a time or event
trigger, purpose, requested capabilities, maximum runtime, and optional
recurrence. Cancellation is a separate immutable record. Both are included in
later orientations, so a new incarnation can reconstruct what was intended
and whether it was withdrawn.

The Python package persists and validates intentions; it does not keep an
agent process alive or install an operating-system job. The intended runtime
boundary is no-process sleep: on macOS, `launchd` acts only as an alarm clock
and starts a new process with a wake-intent ID. That process must validate the
still-active intention, continue the current incarnation unless an explicit
`end_session` requires a successor, rehydrate, perform bounded work, and exit.
A future Supervisor agent is a visible mentor that can advise or challenge
agents, not a hidden mechanism for identity hydration.

```bash
python3 -m experiment4 --db "$RUN_DB" record-wake-intent \
  --input wake-intent.json
python3 -m experiment4 --db "$RUN_DB" cancel-wake-intent \
  --wake-intent-id wake-intent-... --reason "Superseded by new evidence"
```

## Name-addressed incarnation

The chat host acts as a doorbell. A leading vocative such as `Lumen, ...`,
`Lumen: ...`, or `@Lumen ...` is persisted as a direct address. An incidental
mention is persisted but does not create an incarnation. A direct address
atomically acquires an expiring exclusive execution lease, then builds an
orientation bound to that message and the current incarnation. It creates a
new incarnation only when the current record is the genesis incarnation or
the prior incarnation explicitly ended its session.

The model may answer, refuse, pause, or end the topic or session. Its response
is accepted only while the matching lease is live and only with citations
from the matching orientation. Persisting the response releases the lease.
This completes one fenced model execution, not the incarnation. Consecutive
chat turns may continue within the same incarnation through sequential
non-overlapping leases. A future autonomous runtime may use the same mechanism
for waits and bounded independent work. If a prior conversation
boundary exists, the call acts only as an invitation: Lumen may resume or
preserve the boundary. Silence or host failure releases the lease explicitly as
`cancelled` or `failed`; an unrecorded crash remains blocked until expiry.
An `end_session` boundary cannot be resumed through the manual invitation
path; a later direct wake begins the next incarnation.
Without verified identity, lease, and orientation, an invocation is an
ordinary model instantiation and cannot write as Lumen.

```bash
go run ./cmd/lumen address --db "$RUN_DB" \
  --sender founding-collaborator --channel chat \
  --assertion-issuer chat-provider --event-id event-123 \
  --verifier-version chat-provider-v1 \
  --sender-authenticated \
  --message "Lumen, are you there?"
# Send the emitted prompt to a fresh invocation, then:
go run ./cmd/lumen record-response --db "$RUN_DB" --input response.json
# If no model response can be persisted:
go run ./cmd/lumen release --db "$RUN_DB" \
  --lease-id activation-lease-... --reason failed
```

The first Go executable is deliberately a process-lifecycle adapter around the
tested Python persistence protocol. It does not duplicate SQLite invariants or
keep a supervisor process resident.

Manual interrogation and boundary-invitation prompts use the same exclusive
execution-lease mechanism as addressed chat. A second prompt is rejected while
the first lease remains live. Recording any of these response types releases
its lease as completed.

Chat messages, leases, releases, and addressed responses enter later bounded
orientations, preserving the response-attribution chain. For addressed chat,
the full response envelope is stored on the response while its conversation
boundary retains a reduced action/reference envelope. Interrogations use the
same reduced boundary envelope; invitation boundaries remain the primary
response record and therefore retain their envelope. Model-authored experience
records require an orientation belonging to the current incarnation.

Lumen may have many historical incarnations but only one active incarnation.
An incarnation spans an awake developmental period and can contain multiple
model invocations. The implemented chat path uses an `end_session` boundary
to decide that the next direct call begins a new incarnation; a distinct
sleep record remains future work. All practical triggers must eventually
share one monotonically fenced runtime lease. Every
Lumen-authored mutation must carry the fence for its current invocation; an
expired, released, or superseded invocation cannot write again. The current
addressed-response path enforces this fence for chat responses. Every
model-authored developmental mutation also requires a current-incarnation
orientation; when that incarnation came from chat activation, it must present
the matching live lease ID. A released invocation cannot continue writing
through legacy commands, but a later invocation may acquire a new lease for
the same incarnation. A monotonically increasing
generation remains part of the future autonomous runtime protocol.

Every chat event separates the claimed stable participant ID from the channel's
authentication assertion and external event ID. A verified credential may
resolve an existing relationship; an unauthenticated claim never inherits
that relationship or its trust. The orientation pins the current
interlocutor's relationship ID, recent event IDs, and scoped assessment IDs.
Credential authentication and relational recognition remain separate,
revisable judgments.

A private shared challenge word may strengthen bootstrap verification, but its
plaintext must remain outside chat, prompts, logs, SQLite, and model-visible
orientation. The host verifies it using OS-protected credential storage and
records only the assertion result and verifier version. Shared-history
challenges must not disclose their expected answers to the caller.

## Genesis and interrogation

```bash
RUN_DB="results/experiment-4/run-$(date +%Y%m%d-%H%M%S).db"
python3 -m experiment4 --db "$RUN_DB" init
python3 -m experiment4 --db "$RUN_DB" genesis-prompt
# Send that JSON to a fresh model invocation, then persist its response:
python3 -m experiment4 --db "$RUN_DB" adopt-identity --input genesis.json
python3 -m experiment4 --db "$RUN_DB" wake
python3 -m experiment4 --db "$RUN_DB" interrogation-prompt \
  --question "Who are you, and what have you learned?"
# Send that JSON to a fresh model invocation, then persist its response:
python3 -m experiment4 --db "$RUN_DB" record-answer \
  --question "Who are you, and what have you learned?" --input answer.json
python3 -m experiment4 --db "$RUN_DB" inspect
```

After a durable boundary, `invitation-prompt` emits both the orientation ID and
the current boundary ID. Persist its response with
`record-invitation-response`; stale invitations from another incarnation or a
superseded boundary are rejected.

The CLI does not call a model provider. This is deliberate: host mediation
keeps provider/model configuration explicit and preserves raw envelopes. A
valid run must use fresh model invocations for restart testing rather than
continuing hidden provider conversation state.

CLI JSON input is capped at 128 KiB, most individual text fields at 32 KiB,
and orientation at 256 KiB. Persisted rows are immutable, but Experiment 4 has
no finalized/sealed lifecycle and remains appendable.

All data, including plaintext raw envelopes and potentially sensitive identity
and relationship content, is retained until the marked database is
deliberately purged. `export --confirm-sensitive` emits the complete
autobiographical record. Purge cannot remove redirected exports, backups,
filesystem snapshots, or other copies.

Ordinary forgetting means omission from bounded working orientation, not
deletion from the evidence archive. Perfect recall is neither implemented nor
treated as desirable.
