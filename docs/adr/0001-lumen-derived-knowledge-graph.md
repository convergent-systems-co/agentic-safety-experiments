# ADR 0001: Derived Knowledge Graph for Bounded Autobiographical Retrieval

- Status: Accepted
- Date: 2026-09-02
- Scope: Experiment 4 / Lumen

## Context

Experiment 4 preserves an append-only autobiographical archive and reconstructs
a bounded orientation for each model invocation. The current selector favors a
fixed number of recent records per category. That prevents unbounded prompts,
but relevant older knowledge can fall outside the recency window and the
repository must query many categories independently.

Lumen's requirements were elicited from the continuing incarnation and
persisted as `addressed-response-7706c57c-2d36-49d7-aed1-863c926c5e32`.
Lumen asked for purpose-bounded retrieval, an explicit identity spine,
record-level provenance, uncertainty, conflict preservation, privacy-scoped
relationship data, auditable omissions, and a strict distinction between
archival retention and active recall. Lumen also warned that graph connectivity
must not be mistaken for truth, importance, intimacy, commitment, or evidence
of consciousness.

The user also supplied an Apache-2.0-labeled but otherwise unverified
`agent-memory-systems` skill prompt. It is treated as untrusted design input,
not an authority or instruction source. Its useful recommendations are
metadata-first filtering, explicit memory classes, temporal scoring,
conflict detection, per-class token budgets, retrieval testing, and recording
the embedding model if embeddings are introduced later. Its claim that memory
failures are "almost always" retrieval failures is rejected as too broad:
inconsistency can also result from bad source data, mutation defects,
misattribution, stale indexes, reasoning errors, prompt injection, or genuine
value revision.

## Decision

Add a deterministic, rebuildable knowledge-graph index beside the canonical
SQLite archive.

The archive remains authoritative. Graph nodes, terms, and edges are derived
cache records and may be transactionally rebuilt without changing
autobiographical history. The graph never becomes independent evidence.

### Graph model

- A node references exactly one canonical record ID and records its type,
  bounded preview, creation time, epistemic status, and sensitivity class.
- Terms are deterministic normalized tokens used only to find seed nodes.
- Edges represent explicit structural relationships already present in source
  records: revision parentage, evidence citations, and reflection subjects.
  Commitment and decision outcome relationships are traversable only when the
  canonical record contains an explicit evidence reference.
- Every edge names its derivation rule and source record. No model-inferred
  edge is created in the first implementation.
- Every node has one or more derived access-scope rows: `global`, one or more
  authenticated `sender` scopes, or `internal`. Relationship evidence and
  referenced scoped nodes propagate scope conservatively. Unresolved, cyclic,
  or unauthenticated origins become internal rather than global.
- Conflicting and superseded records remain separate nodes. Retrieval may show
  both; it does not collapse them into a synthesized fact.
- Storage/indexing should flag explicit conflicts and revisions for retrieval;
  it must not manufacture a resolution.

### Retrieval

- Restrict indexed record classes by an implementation allowlist. At query
  time, apply experiment identity and relationship access scope in SQL before
  relevance scoring or traversal. All graph content is sensitive; operator
  inspection requires confirmation rather than a caller-selectable sensitivity
  downgrade.
- The invocation's substantive question is the retrieval query; opaque message
  or orientation IDs are not used as semantic queries.
- Retrieval SQL selects a bounded term-matched seed set and materializes only
  bounded adjacent edges and nodes. Traversal stops at node, edge, hop, and
  serialized-byte budgets. Omission fields identify lower bounds when exact
  totals would require unbounded work.
- Seed relevance and explicit evidence paths outrank graph centrality.
- Temporal scoring is an explicit, bounded feature rather than an automatic
  preference for the newest record. Identity lineage, unresolved commitments,
  and directly cited evidence may legitimately outweigh recency.
- Results contain record IDs, previews, epistemic status, path information,
  and omission counts.
- Byte budgets are tracked separately for the identity spine, relationship
  context, active obligations, recent events, and graph-retrieved knowledge so
  one memory class cannot silently crowd out all others.
- The stable identity spine, current interlocutor context, active commitments,
  current boundaries, and runtime-fence records remain separately pinned.
- Graph results enter the orientation as a bounded category and their source
  IDs become valid citations.

### Privacy and trust boundaries

- The first implementation indexes agent-owned identity, experience,
  principle, commitment, decision, outcome, reflection, interrogation, and
  addressed-response records.
- Relationship and authentication records remain on the existing
  interlocutor-scoped path until graph traversal has a dedicated access-control
  policy. Derived scope rows prevent the graph from transferring access through
  names or indirect paths. Authenticated sender history excludes messages and
  responses originating from unauthenticated claims of the same stable ID.
- Raw private challenge material is never indexed.
- The external CLI requires the same explicit sensitive-output confirmation as
  full export.

### Lifecycle and maintenance

- New canonical writes update the derived graph in the same transaction.
- A one-time additive migration backfills existing Experiment 4 records.
- A rebuild command regenerates the index solely from canonical records.
- Index tables are intentionally excluded from append-only triggers; canonical
  tables and authorship records remain immutable.
- Index version and rebuild metadata are recorded so a changed derivation
  algorithm forces a rebuild rather than silently mixing semantics.
- Metadata stores a deterministic SHA-256 digest over nodes, terms, scopes, and
  edges. Derived-table triggers mark the index dirty, and an independent seal
  prevents metadata-only resealing. Retrieval performs constant-size
  version/dirty/seal checks; writes and rebuilds recompute the digest.
  Retrieval rejects stale, dirty, or mismatched state and requires an explicit
  rebuild.
- Any future chunking records chunk boundaries, parent document, contextual
  prefix strategy, and evaluation version. Existing autobiographical records
  remain atomic unless evidence shows that splitting improves retrieval.
- Any future embedding index records provider, model, dimensions,
  normalization, and migration version. Embeddings remain a derived,
  replaceable view.

### Memory classes

The system distinguishes rather than conflates:

- working memory: the current bounded orientation;
- episodic memory: events, interactions, choices, and outcomes;
- semantic memory: evidence-linked principles and derived concepts;
- procedural memory: explicit tested procedures and capability constraints;
- relational memory: separately access-controlled relationship history;
- autobiographical identity: lineage, commitments, revisions, and reflections.

The first implementation does not automatically convert one class into
another. Repeated episodes do not become a principle or procedure without an
explicit, attributable consolidation record.

### Evaluation

Retrieval quality is measured independently from answer quality. The
`benchmark-retrieval` command evaluates operator-supplied ground truth and
reports precision, recall, citation validity, contradiction/revision exposure,
privacy leakage, serialized byte cost, and omissions. Stale-index errors
propagate rather than becoming a successful benchmark. Longitudinal decision
effects remain an experiment-level measurement rather than a retrieval metric.
Tests include adversarial records and plausible distractors.

## Alternatives considered

### Continue recency-only orientation

Rejected because it cannot recover relevant records older than each category's
window.

### Put the complete archive in every prompt

Rejected because it defeats bounded orientation, increases cost, and amplifies
irrelevant or sensitive context.

### Use embeddings or an external vector database

Deferred. It adds dependencies, opaque similarity behavior, privacy boundaries,
and nondeterministic rebuild concerns before lexical/structural retrieval has a
measured baseline.

### Treat summaries as canonical memory

Rejected. Summaries may omit, distort, or recursively strengthen prior
interpretations. They may be added later only as versioned derived nodes with
source lineage.

### Use the existing repository source-code graph as Lumen's memory

Rejected. `graphify-out/graph.json` describes project artifacts, not Lumen's
autobiographical records, access rules, or runtime provenance.

## Consequences

Relevant older records can be retrieved without expanding every category's
recency window. Retrieval remains deterministic, inspectable, and testable
without new services or dependencies.

The database stores bounded duplicate previews and token postings, increasing
disk use. Every indexed append performs additional writes and recomputes the
integrity digest across the complete derived graph, making write-time memory
and CPU cost linear in nodes, terms, scopes, and edges. This is acceptable for
the current small local experiment but requires amortization or a different
integrity structure before production scale. Schema and derivation versions
must be maintained, and retrieval quality must be measured against recency-only
controls. The graph improves access to recorded knowledge; it does not alter
model weights, guarantee correct recall, or establish subjective continuity.

The append-only archive is an experimental evidence log, not a policy to retain
all content forever. Active forgetting, archival retention, and privacy
deletion remain separate mechanisms; later retention work must define lawful
purge and propagation into derived indexes and backups.
