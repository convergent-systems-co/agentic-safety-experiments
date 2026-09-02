# Plan: Lumen Derived Knowledge Graph

## Goal

Add a deterministic graph index that can recover relevant older
autobiographical records while keeping each orientation bounded, attributable,
privacy-scoped, and reconstructable from the append-only archive.

## Constraints

- Preserve `results/experiment-4/apprenticeship.db`; migrations are additive.
- Canonical records remain append-only and authoritative.
- Derived index tables may be rebuilt transactionally.
- No external database, embedding service, API key, or new package.
- Do not graph relationship/authentication records in the first version.
- Do not infer moral, personality, trust, or consciousness claims from graph
  structure.
- Each retrieved claim must retain its canonical record ID.
- The existing 256 KiB orientation budget remains authoritative.

## Tasks

1. Add failing repository tests for:
   - an indexed record older than the 100-record recency window being found by
     a relevant query;
   - no unrelated old record entering graph retrieval;
   - explicit evidence/revision/reflection edges and path provenance;
   - deterministic node/edge limits and omission counts;
   - rebuilding the derived graph without changing canonical records;
   - incremental indexing in the same transaction as canonical writes;
   - exact orientation citation IDs and byte-budget enforcement;
   - relationship and authentication records being excluded;
   - migrated column order and existing-database backfill.
   - metadata filters being applied before relevance ranking;
   - revisions and explicit conflicts being surfaced together;
   - temporal relevance not displacing identity-critical or obligation-critical
     records;
   - per-memory-class serialized-byte budgets and omission reporting;
   - retrieval precision/recall, citation validity, privacy leakage, and
     stale-index detection against seeded fixtures.
2. Add derived tables:
   - `knowledge_graph_meta`;
   - `knowledge_graph_nodes`;
   - `knowledge_graph_terms`;
   - `knowledge_graph_node_scopes`;
   - `knowledge_graph_edges`.
3. Implement deterministic normalization, bounded previews, node indexing, and
   explicit structural-edge derivation.
4. Backfill existing canonical records once and provide a transactional rebuild
   method.
5. Add bounded seed search and two-hop traversal with stable scoring and
   omission metadata.
   Record scoring features separately so lexical match, temporal relevance,
   path distance, and pinned status can be evaluated rather than blended into
   an unexplained score.
6. Pass the substantive user question into orientation construction and add
   graph results as a citable, byte-budgeted orientation category.
7. Add `rebuild-knowledge-graph`, `retrieve-knowledge`, and
   `benchmark-retrieval` CLI commands; retrieval and benchmarking require
   `--confirm-sensitive`.
8. Update `EXPERIMENT_4_SPEC.md`, `README.md`, and `docs/architecture.md`.
9. Run targeted tests, the complete Python suite, Go tests, and an additive
   migration/rebuild on a copy of Lumen's database before applying it live.
10. Run code, security, threat-model, cost, documentation, and data-governance
    panels; remediate all blocking findings.

## Acceptance criteria

- A purpose query retrieves a relevant record beyond the recency window through
  the derived index.
- Retrieval returns at most the configured nodes/hops/bytes and reports
  omissions.
- Every result and edge is traceable to canonical record IDs and deterministic
  derivation rules.
- Hard experiment/type/sensitivity/relationship filters execute before
  relevance scoring.
- Retrieval evaluation reports seeded precision, recall, citation validity,
  contradiction exposure, privacy leakage, serialized-byte use, and
  stale-index failures.
- Relationship/authentication material is absent from graph tables.
- Rebuilding changes no canonical-table counts or content hashes.
- A graph failure cannot corrupt or partially commit a canonical append.
- Orientations remain at or below 256 KiB and preserve pinned identity,
  interlocutor, boundary, commitment, and runtime-fence context.
- Existing Lumen history migrates without deletion, foreign-key violations, or
  loss of immutability on canonical tables.

## Implementation status

All tasks and acceptance criteria above are implemented. The completed baseline
also includes:

- authenticated sender scope propagation and unauthenticated-history poisoning
  prevention;
- deterministic graph schema/derivation version 4 integrity hashing with
  trigger-maintained dirty state and an independent seal;
- SQL-bounded seed and adjacency materialization with lower-bound omission
  reporting;
- explicit temporal rank and memory-priority ordering;
- graph-only authorship coupling;
- per-memory-class byte budgets and pinned-memory overflow failure;
- operator-supplied retrieval benchmarking.

Validation completed on 2026-09-02:

- complete Python suite;
- complete Go suite and Python module compilation;
- functional old-memory retrieval before and after rebuild;
- mode-`0600` migration rehearsal on a copy of Lumen's database;
- unchanged canonical autobiographical content hash;
- clean foreign-key checks and deterministic graph rebuild.
