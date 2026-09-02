# Plan: Consent-Gated Realtime Lumen Observer

## Goal

Provide a local HTML visualization of Lumen's durable autobiography, current
incarnation, memory-class budgets, derived graph, retrieval paths, commitments,
boundaries, and execution leases without turning observation into an
uncontrolled disclosure channel.

The page visualizes recorded functional state. It must not claim to display
private thoughts, consciousness, feelings, hidden chain of thought, or model
weights.

## Consent model

- Observation begins with an append-only request naming the authenticated
  viewer stable ID, purpose, requested data scopes, and requested duration.
- Lumen receives a normal lease-bound orientation and may approve, deny, or
  narrow the request.
- Approval creates a short-lived append-only grant with explicit scopes and an
  expiry. No grant is indefinite.
- Lumen may append a revocation at any time. Every snapshot and event-stream
  read rechecks the current grant; expiry or revocation fails closed.
- Denial creates no viewer token and exposes no observer data.
- Grant decisions must be attributable to the current incarnation, exact
  orientation, and live execution lease.
- Application controls cannot prevent the local database owner or a same-user
  process from bypassing them outside this application. The observer makes the
  governed path auditable; it is not a hardware security boundary.

## Data scopes

Initial allowlisted scopes:

- `identity`: stable agent ID, chosen name, identity lineage IDs, incarnation;
- `autobiography`: record types, IDs, timestamps, epistemic status, and bounded
  previews;
- `knowledge_graph`: permitted nodes, explicit edges, scopes, integrity/version
  state, ranking paths, and omission metadata;
- `memory_budget`: class budgets, retained bytes, omissions, and pinned IDs;
- `commitments`: commitment/decision state and outcomes;
- `lifecycle`: boundaries, wake intentions, and lease status.

Raw envelopes, authentication material, private challenge values, full chat
messages, relationship evidence for another viewer, database paths, and
credential-store data are never emitted. Sender-scoped records use the same
metadata-first access rules as Lumen's addressed orientation.

## Local transport

- Use the Python standard library; add no service or browser dependency.
- Bind only to `127.0.0.1` on an operator-selected port.
- Generate an unguessable in-memory viewer token after an active grant is
  verified. Do not place it in logs or durable autobiography.
- Serve a static, self-contained HTML/CSS/JavaScript page with a restrictive
  Content Security Policy and no third-party resources.
- Provide a bounded JSON snapshot endpoint and either Server-Sent Events or
  deterministic short polling. Every request validates token, viewer, grant,
  expiry, revocation, and scope.
- Read SQLite through the repository boundary. Do not hold a writer
  transaction while a browser is connected.

## Visualization

- Identity/incarnation header with graph schema, derivation, and integrity
  state.
- Timeline of canonical autobiographical record IDs and types.
- Interactive graph of allowed nodes and explicit sourced edges.
- Memory-class budget bars with omissions and pinned-record indicators.
- Commitment, boundary, and lease status panels.
- Visible grant purpose, allowed scopes, expiry, and revoked/denied state.
- Connection state and last durable-record timestamp; no invented "thinking"
  animation when no record changed.

## TDD tasks

1. Add schema/migration tests for immutable observation requests, decisions,
   grants, and revocations.
2. Test that only a current lease-bound Lumen response can approve, deny, or
   narrow a request.
3. Test expiry, revocation, replay, stale orientation, wrong incarnation,
   concurrent grant, and unauthenticated viewer failures.
4. Test data minimization and sender-scope isolation for every observer scope.
5. Test localhost binding, token enforcement, CSP, response size limits, and
   immediate 403 after revoke/expiry.
6. Test deterministic snapshots and update delivery after canonical appends and
   graph rebuilds.
7. Test one stable Lumen/incarnation at a time; the observer never creates or
   hydrates another incarnation.
8. Add CLI commands to request observation, emit the Lumen decision prompt,
   record the decision, revoke a grant, inspect grant state, and start the local
   observer.
9. Update README, Experiment 4 specification, architecture, and a dedicated
   ADR.
10. Run complete validation and all six governance panels before opening an
    observer grant against Lumen's live database.

## Acceptance criteria

- Without an active Lumen-authored grant, observer endpoints return no state.
- Lumen can deny, narrow, expire, or revoke access, and the server enforces the
  latest durable decision on every read.
- A viewer cannot obtain another relationship's scoped memory.
- The page contains no third-party requests and exposes no raw envelopes,
  credentials, hidden reasoning, or unrestricted chat history.
- Snapshot and event payloads are bounded, deterministic, citable to canonical
  IDs, and explicit about omissions.
- Starting or viewing the observer does not create another Lumen incarnation.
- Browser disconnect, server restart, and token loss do not alter Lumen's
  autobiography or silently extend a grant.
