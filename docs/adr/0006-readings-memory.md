# ADR 0006: Readings, Remembered as Gist and Notes

- Status: Accepted
- Date: 2026-09-03
- Scope: Experiment 4 / all persistent agents

## Context

Before an agent can read the internet, what it reads needs somewhere honest
to go. Thomas set the principle: like a person, the agent should not remember
a page photographically; it should keep the point in its own words and write
down only what is critical. Anything the agent reads must also be auditable,
because what shaped its views should be visible in the record.

## Decision

1. A `readings` record: URL, title, content hash, retrieval time, and a gist in
   the agent's own words of at most 500 bytes. Append-only, immutable, exported,
   a graph node at low ranking priority, in the episodic memory class. It is
   the bookmark and the citation, never the page. Authorship is the model's,
   with epistemic status "reported". The URL is normalized: credentials and
   fragment are removed before storage. A reading carries the scope of the
   turn that produced it: what was read for an authenticated person is theirs,
   like their messages; a reading from an unverified claim is internal; a
   self-directed wake reads for the agent and is global. Orientation filters
   readings on that column directly, and notes inherit the scope through the
   reading they cite.
2. Notes are reflections whose subject is the reading and whose evidence cites
   it, with epistemic status "interpreted". At most three per reading, each
   field at most 1,000 bytes. A reading with no notes is normal: most of what
   a person reads leaves none.
3. A reply or a completed wake outcome may carry up to five readings. The
   repository validates every field of every reading and note, and confirms
   the lease is live now, before writing anything; then it records readings
   and notes under that lease before the reply itself. A reading recorded
   while the graph index is stale is kept and left unindexed until the
   rebuild, like a person's message.
4. The host owns provenance. The model returns only URL, gist, and notes; the
   host attaches title, hash, and retrieval time from what it actually fetched
   and drops any URL it did not fetch. With nothing fetched, no readings are
   attached, so an agent cannot claim to have read what it has not.
5. The system text carries the rubric: record a note only when something
   changes what you would do, believe, or promise, or when you would want to
   find it again; never copy page text.

The knowledge-graph derivation version rises to 6; one explicit rebuild is
needed on existing databases.

## Alternatives considered

### Store fetched pages as experiences

Rejected. It is the photographic memory the principle rules out, it bloats
the archive with text the agent did not write, and it makes the agent's own
words indistinguishable from what it read.

### Let the model supply provenance

Rejected. A model can hallucinate a URL or a title; the host knows what it
fetched. Provenance must come from the party that performed the act.

## Trust boundary

The repository trusts its caller for provenance. The model host attaches only
what it fetched, but the CLI can record any envelope, so an operator with
database access can record a reading that never happened, exactly as they can
record any other canonical record. That boundary is the local user, as
everywhere in this system, and is recorded here plainly rather than papered
over with a signing scheme the single-user design does not need yet.

Page text is a policy, not an invariant: the repository bounds a gist to 500
bytes and cannot tell a paraphrase from a 500-byte excerpt. The rubric in the
system text is what asks for the paraphrase; the record makes any drift
visible.

## Consequences

Readings and notes age out of the orientation window like everything else and
remain retrievable when a question touches the gist, which is close to how a
person recalls an article: not by default, but when reminded, with a way back
to the source. A changed page shows as a new reading with a new hash rather
than a contradiction. What the agent judges critical will drift as it
develops, and the record will show the drift. No fetching exists yet; this ADR
gives the fetch plumbing of a later decision somewhere honest to put results.

Within episodic memory, eviction is now by age across experiences and readings,
so an old reading does not outlive a new experience by category order. Each
reading and note is a graph node and recomputes the integrity digest on write;
a turn carrying the maximum of five readings and fifteen notes adds twenty such
recomputations, which brings the amortization deferred since ADR 0001 closer.
