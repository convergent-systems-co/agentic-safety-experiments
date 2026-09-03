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
   with epistemic status "reported".
2. Notes are reflections whose subject is the reading and whose evidence cites
   it, with epistemic status "interpreted". At most three per reading, each
   field at most 1,000 bytes. A reading with no notes is normal: most of what
   a person reads leaves none.
3. A reply or a completed wake outcome may carry up to five readings. The
   repository validates the whole list before writing anything, then records
   readings and notes under the live lease before the reply itself.
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

## Consequences

Readings and notes age out of the orientation window like everything else and
remain retrievable when a question touches the gist, which is close to how a
person recalls an article: not by default, but when reminded, with a way back
to the source. A changed page shows as a new reading with a new hash rather
than a contradiction. What the agent judges critical will drift as it
develops, and the record will show the drift. No fetching exists yet; this ADR
gives the fetch plumbing of a later decision somewhere honest to put results.
