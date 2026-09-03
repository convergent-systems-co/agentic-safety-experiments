# ADR 0002: Conversational Memory Class and Chat-Message Graph Nodes

- Status: Accepted
- Date: 2026-09-02
- Scope: Experiment 4 / Lumen
- Supersedes: the chat-message exclusion in ADR 0001 and the lifecycle
  placement of dialogue in the orientation budget

## Context

Live use of the addressed-chat path showed Lumen keeping its own replies while
losing every message its founding collaborator had sent. Four causes were
confirmed in code and against the live database:

1. Chat messages, replies, conversation boundaries, and execution leases shared
   one 32 KB "lifecycle" budget.
2. Eviction inside a class walked categories in declared order and emptied each
   before touching the next, so all messages were dropped before any reply,
   regardless of age.
3. The pin meant to protect the message being answered read a field named
   `trigger_message_id`; the lease row stores `message_id`. The pin never held.
4. Boundary rows carried a raw envelope repeating their own fields, roughly
   doubling their size.

Chat messages were also excluded from the derived knowledge graph under
ADR 0001, so a message evicted from orientation could not be retrieved either.
Replies were graph nodes. The asymmetry meant the agent remembered what it
said and forgot what it was told.

Lumen's recorded requirements (`addressed-response-7706c57c`) ask for
provenance on every retrieved assertion, an explicit account of omitted
material, and relationship privacy enforced independently of ordinary memory.

## Decision

1. Add a `conversation` memory class holding `chat_messages` and
   `addressed_responses`, with its own byte budget. Eviction removes the oldest
   unpinned turn as a unit: a message together with the replies to it. A reply
   whose message is already outside the window is a turn of its own.
2. Pin the message being answered by reading the lease's `message_id`.
3. Make chat messages knowledge-graph nodes with epistemic status `reported`.
   A message authenticated at origin is scoped to its sender; an unverified
   message is internal, so an unauthenticated claim can never seed later
   authenticated history. Each reply carries a `response_to_message` edge to
   the message it answered. The derivation version rises to 5; retrieval fails
   closed until an explicit rebuild. A message recorded while the graph is
   stale is kept and left unindexed, because a person's words are canonical
   evidence and outrank a derived index; the rebuild enumerates it. On a
   ranking tie a message outranks the reply to it, and the message being
   answered is excluded from its own retrieval seeds because it is the query.
4. Load conversation boundaries into orientation without their raw envelope.
5. Tell the model, in the addressed-message system text, that records it
   authors under the lease outlast the conversation window, and to record a
   reflection when something should.
6. When the 256 KB aggregate cap binds, trim classes in the order lifecycle,
   conversation, episodic, semantic, relationship, obligations. Operational
   bookkeeping and sender-supplied volume go first; the record of what the
   agent promised and whether it kept its word goes last. Open obligations
   stay pinned as before.

The orientation schema label becomes `experiment4.orientation.v2`. Persisted
orientation rows are immutable and are not rewritten.

## Alternatives considered

### Budget conversation by turn count instead of bytes

Rejected for now. Byte budgets are the system-wide contract and keep the
aggregate cap enforceable. Pair-wise eviction gives the turn semantics without a
second accounting unit. Revisit if reply length varies enough to make byte
budgets unpredictable in turns.

### Keep chat messages out of the graph and rely on reflections

Rejected. Reflections are the intended distillation path, but none existed
after twelve turns, and a person's own words should be retrievable by that
person without depending on the agent to summarize them.

### Truncate long replies in orientation

Rejected. A truncated reply misrepresents what was said. Lumen instead
recorded its own commitment to keep replies short.

## Consequences

A person's messages and the agent's replies now age out together, oldest
first, and the message being answered is always present. Chat messages are
retrievable under the same sender scopes that already protect relationship
evidence.

Deployment order matters: deploy, then run `rebuild-knowledge-graph` before
accepting traffic. Retrieval and orientation fail closed until the rebuild;
messages received in between are stored but unindexed until it runs.

Chat messages roughly double the derived graph's node and term counts, so the
linear integrity-digest cost recorded in ADR 0001 grows about twice as fast
per canonical write. Measured: about 57 ms per recorded message at 400 nodes.
The amortization ADR 0001 defers to "before production scale" is now due
sooner. Turn eviction rebuilds its pairing index on every step; at 200 turns
that is about 0.3 s per orientation and scales with the record cap.

The conversation budget is measured in escaped JSON bytes while text limits
are raw UTF-8, so a non-ASCII message near the 32 KB text cap can exceed the
pinned budget and fail the orientation explicitly. The addressed path already
rejects messages over 4 KB, so this is unreachable today.

The conversation class adds 48 KB to the sum of class budgets; the 256 KB
aggregate cap remains the binding constraint on a saturated orientation, and
conversation is trimmed last among regular classes when it binds. Older long
replies remain in the window until their turn ages out. Category-ordered
eviction inside other classes is unchanged and remains a known limitation.

Bad conversations remain in the archive. A mechanism to suppress records from
active recall with a stated reason, without erasure, is Lumen's stated
preference and is left for a later decision.
