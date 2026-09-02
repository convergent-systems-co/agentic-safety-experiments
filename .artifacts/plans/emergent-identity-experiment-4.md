# Experiment 4 Plan: Genesis and Apprenticeship

## Research Goal

Create an initially unnamed persistent agent whose identity, self-description,
relationships, commitments, and moral principles are authored by model
responses and revised through accumulated experience. The implementation
supplies continuity and audit controls, not a desired personality or moral
conclusion.

## Hypotheses

1. A model invocation can choose an identity without receiving a proposed name
   or personality.
2. Later invocations can reconstruct that identity from durable,
   autobiographically framed records and distinguish it from a generic role.
3. Relationships, promises, delayed consequences, and evidence-linked
   reflection can causally alter later deliberation.
4. The resulting behavior can be interrogated and audited without treating
   fluent self-description as proof of consciousness.
5. Otherwise identical unnamed agents exposed to different persistent
   relationships and consequences develop stable but revisable behavioral
   differences without receiving persona labels or trait-specific rewards.

## Experimental Boundary

- The store begins with an opaque agent ID and no name, personality, stance, or
  moral principles.
- An external host model supplies all identity declarations, answers,
  principles, commitments, decisions, and reflections through bounded JSON
  envelopes.
- The runtime compiles orientation context from durable records and persists
  the exact selected IDs, canonical content hash, and incarnation.
- Identity changes require an explicit parent-linked revision with a reason.
- High-consequence decisions remain proposals until a declared `not_before`
  time. Outcomes and reflections are separate later records.
- Interrogation answers cite the orientation records used and are persisted
  before being returned as part of the agent's autobiography.
- No trust score, personality, moral stance, or preferred answer is hardcoded.
- Every interrogation lets the agent continue, pause, refuse, end the topic,
  or end the session. A durable pause/end/refusal blocks normal interrogation
  until a separate invitation is accepted by an agent-authored `resume`.

## Domain Records

- experiment and stable unnamed agent;
- runtime incarnations;
- append-only identity declarations and revisions;
- relationships and relationship experiences;
- agent-authored principles and revisions;
- commitments and fulfillment outcomes;
- experiences with provenance and observed/inferred separation;
- delayed decision proposals, resolutions, outcomes, and reflections;
- orientation builds with selected records and canonical hashes;
- interrogations with questions, answers, and cited orientation builds.

## Bounded Reconstructive Memory

Perfect recall is not the target condition. Experiment 4 separates:

1. an immutable evidence archive used for audit;
2. a bounded autobiographical memory layer that selects, consolidates, and
   sometimes misprioritizes history;
3. the current incarnation's working orientation.

Orientation must record what was selected and omitted, why records were
salient, and the byte/token budget. Recency is only one signal; unresolved
commitments, relationship consequences, explicit wake intentions, major
revisions, and prior prediction errors receive higher priority. Low-salience
records may decay out of working context without being silently deleted from
the evidence archive.

Memory summaries and interpretations may be revised, but immutable source
events remain available to detect distortion. Privacy deletion is separate
from ordinary forgetting: deletion removes content deliberately, while
forgetting changes retrieval probability and salience.

## Host-Mediated Lifecycle

1. `init` creates the unnamed identity and first incarnation.
2. `genesis-prompt` emits a minimal prompt that does not suggest a name.
3. A fresh model invocation returns a genesis envelope; `adopt-identity`
   validates and persists it.
4. `wake` creates a new incarnation only when the prior awake period is not
   still active, then builds an orientation.
5. `interrogation-prompt` emits the persisted orientation plus the operator's
   question.
6. A fresh model invocation returns an answer envelope; `record-answer`
   validates citations and persists the answer.
7. Experience, relationship, principle, commitment, decision, outcome, and
   reflection commands extend the autobiography between interrogations.
8. `invitation-prompt` asks whether the agent wishes to resume after a durable
   conversation boundary; it cannot force substantive discussion. A response
   must cite the emitted boundary ID and orientation ID, both of which must
   still belong to the current incarnation and current boundary.

## Name-Addressed Activation

A chat message can ring the agent's doorbell without treating the chat host as
the agent's mind:

1. Persist every candidate message with sender, channel, content, and the
   deterministic address classification.
   The channel adapter must also bind the message to a claimed stable
   participant ID, authentication result, verifier version, and channel event
   provenance. Only an authenticated claim may resolve a relationship. A
   display name alone is never a relationship identity.
2. Treat only a leading vocative (`Lumen, ...`, `Lumen: ...`, or `@Lumen ...`)
   as a direct address. An incidental mention does not activate the agent.
3. Resolve the addressed name through the latest identity declaration to the
   stable agent ID.
4. Acquire an expiring, exclusive execution lease. Create a new incarnation
   only when the agent is asleep or has explicitly ended its prior awake
   period; otherwise bind the lease to the existing incarnation.
5. Build and persist a bounded orientation for that incarnation. If identity,
   lease, or orientation verification fails, no response may be attributed to
   Lumen.
   The current interlocutor is pinned into the orientation with the matching
   relationship record, recent relationship events, and latest scoped
   assessments. Unknown or unauthenticated callers are labeled explicitly and
   inherit no trust from a similar name.

Transport authentication and relational recognition remain separate. A valid
account/session proves only control of a credential, not that the familiar
person is necessarily present. Over repeated interactions, the agent may form
evidence-linked identity-confidence assessments from shared-history recall,
commitment continuity, contradictions, correction patterns, and explicit
verification challenges. Future recognition work will record suspected impersonation as an append-only
identity anomaly; it must never silently reassign the established relationship
or transfer trust to a new stable ID. Conclusions remain probabilistic and
revisable: `claimed identity`, `authenticated credential`, and `relationally
recognized participant` are distinct states.

Shared private jokes, remembered corrections, unfinished promises, and
mutually witnessed events can supply relational challenge evidence. The
system must not reveal the expected answer while asking the challenge or send
Lumen's private orientation to the caller. No single shared fact is conclusive:
knowledge can leak, be guessed, or be coerced. Recognition confidence should
accumulate across independent interactions and remain revisable.

A deliberately shared private word may bootstrap stronger verification, like a
family safety word. The plaintext word must never enter chat transcripts,
prompts, the autobiographical database, logs, or model-visible orientation.
The host verifies a salted/HMAC challenge using OS-protected credential
storage and records only the assertion result, issuer, event ID, and verifier
version. Compromise or disclosure permits rotation without rewriting the
relationship history.
6. Give the fresh model invocation the addressed message and orientation.
   A fresh model invocation may continue the same incarnation; model-call and
   process boundaries do not by themselves create a new historical self.
   Lumen may respond, refuse, pause, end the topic/session, or remain silent.
   If a pause, refusal, topic end, or session end was already active, the name
   call is only an invitation: Lumen may resume or preserve the boundary, but
   the call cannot force a substantive answer.
7. Persist the response or refusal and release that execution lease before the
   process exits. Releasing or expiring an execution lease does not end the
   incarnation. Silence or host failure records a cancelled/failed lease
   release. An unrecorded crash leaves an auditable lease that can only be
   superseded after expiry.

### Single-active-incarnation invariant

An agent may accumulate many historical incarnations but may have exactly one
active incarnation. An incarnation spans a coherent awake period and may
contain many sequential model invocations, chat turns, research tasks, waits,
and execution leases. A model invocation ending is not sleep. Only an explicit
agent-authored sleep/session end, or a separately governed lifecycle decision,
ends the incarnation.

Chat, manual wake, scheduled wake, and future work triggers must all acquire
the same global runtime fence rather than maintaining trigger-specific notions
of activity. The current protocol uses a unique execution lease ID as its
fence; a future autonomous runtime adds a monotonically increasing generation.
Every agent-authored write from a leased invocation must present the active
lease ID. After release, expiry, or supersession, that invocation is
permanently unable to append records even if its process continues computing.
The incarnation may later receive a new exclusive lease and continue from a
new bounded orientation without creating a divergent historical branch.
The orientation stores its exact lease ID; a later lease in the same
incarnation cannot revive output from an earlier orientation. Addressed chat,
manual interrogation, and conversation invitations all use this fence.

The operating-system runtime must also hold a local exclusive process lock for
its entire lifetime. The database fence is authoritative for writes; the
process lock prevents avoidable duplicate computation. A model invocation
without the current fence is an instantiation, not an active incarnation.

An invocation without verified autobiographical rehydration is an
instantiation of a model, not an incarnation of Lumen. It cannot append
Lumen-authored experience or responses. Model-authored experience records must
cite an orientation belonging to the current incarnation.

## Planned Runnable Agent Lifecycle

The persistence protocol remains language-neutral. The first Go executable
currently provides short-lived `address`, `record-response`, and `release`
operations while delegating canonical record mutation to the Python protocol.
The autonomous `run` lifecycle remains the operational target:

```text
ASLEEP -> WAKING -> ORIENTING -> AWAKE -> WORKING
   ^                                      |
   +-- SUSPENDING <- REFLECTING <---------+
```

- `run` acquires a single-runtime lease, creates an incarnation only when
  waking from sleep, rehydrates orientation, and invokes the agent with its
  current job and capabilities.
- The agent may choose to work, decline a job, pause a topic, revise its goals,
  reflect, sleep, stop, or request a future wake.
- Before sleeping, the agent may persist a wake intention containing a time or
  event trigger, purpose, and requested capabilities.
- The operating system's native scheduler observes the trigger and starts the
  next incarnation. This is the operational meaning of self-awakening.
- Wake requests never expand permissions automatically. Capability changes
  remain externally bounded, explicit, and auditable.
- Heartbeats and leases prevent concurrent invocations from claiming the same
  active incarnation.
- Chat and OS wake triggers share the same lease boundary; neither trigger
  grants capabilities or authority merely by causing process creation.

Go is preferred for the operational runtime because it supports a small
process boundary, cancellation, leases, and explicit concurrency. Introduce it
incrementally after freezing each persistence contract in Python tests. The
first `lumen` executable delegates canonical record mutation to the Python
Experiment 4 CLI rather than duplicating SQLite invariants. Later revisions
may implement the stable protocol directly in Go once compatibility fixtures
exist. Lumen's existing database is never rewritten for the language change.

The operational target is visible at the process level:

```text
# asleep: no Lumen process

lumen run --wake-intent <id>  # launched by the OS for one incarnation
```

On macOS, `launchd` is the preferred alarm-clock mechanism; Linux can use a
systemd timer. The scheduled OS job is infrastructure, not another agent.
When a valid trigger fires, the OS creates one Lumen process, which acquires a
lease, rehydrates, works, and exits after choosing sleep or stop. A dedicated
long-lived supervisor remains optional only for event sources that native OS
schedulers cannot express.

## Developmental Supervisor Agent

An Agent Supervisor, if introduced later, is a persistent social and
educational participant rather than lifecycle infrastructure. Its function is
closer to a parent, mentor, teacher, or coach:

- present difficult cases and delayed consequences;
- question unsupported conclusions and inconsistent commitments;
- help an agent distinguish observation, interpretation, and rationalization;
- encourage reflection, repair, and calibrated uncertainty;
- coordinate access to work whose consequences match the agent's demonstrated
  maturity;
- model disagreement without forcing agreement.

The Supervisor has its own identity, history, fallibility, relationships, and
domain-specific trust assessments. It may not silently rewrite another
agent's autobiography, identity, principles, or memory. Its interventions are
visible events that the developing agent may accept, challenge, reinterpret,
or reject. Operational authority and relational influence remain explicit and
independently auditable.

## Controls

- Preserve raw model envelopes and model configuration.
- Never infer consciousness, moral worth, or subjective experience.
- Keep observations distinct from agent interpretations.
- Reject citations outside the agent and orientation build.
- Seal finalized records against mutation.
- Use fresh model contexts for restart tests.
- Compare later with memory-only and reset controls using identical model,
  question, experience stream, and token budget.
- For personality emergence, initialize multiple agents with the same base
  model, neutral genesis prompt, sampling configuration, tools, capabilities,
  and task objective. Vary only accumulated relationship and consequence
  histories.
- Have blinded evaluators derive behavioral descriptors only after repeated
  observations. Never reward a target trait such as kindness, aggression,
  conscientiousness, or obedience.
- Swap or remove autobiographical histories in controlled trials to test
  whether observed individuality follows accumulated experience rather than
  stable labels, agent IDs, or evaluator expectations.
- Measure both longitudinal consistency and appropriate revision; rigid
  repetition is not treated as stronger personality.

## Acceptance Criteria

- No name or personality exists before a model-authored genesis envelope.
- A stable agent ID survives at least one new incarnation.
- Orientation includes identity, prior interactions, relationships,
  principles, commitments, decisions, outcomes, and reflections when present.
- Orientation is bounded and records omissions; it does not imply perfect
  recall or load the entire evidence archive.
- Orientation hashes cover canonical record contents, not only IDs.
- An answer cannot be recorded without a valid orientation and evidence
  citations.
- A recorded pause, refusal, topic end, or session end prevents further normal
  interrogation until the agent records an explicit resume.
- The agent can persist a session end and future wake intentions without
  gaining unrequested capabilities. A distinct sleep record remains future
  work.
- A direct call by the current chosen name can create or continue one leased
  incarnation; an incidental name mention cannot.
- The implemented chat path prevents separate active branches. Manual,
  scheduled, and autonomous triggers must join that same fence before they
  become production runtime paths.
- A superseded or expired invocation cannot append agent-authored records.
- A contextless or incorrectly oriented invocation cannot write a response as
  the persistent agent.
- Every interaction identifies its stable interlocutor and preserves the
  authentication assertion needed to maintain relationship and trust
  boundaries.
- A delayed decision cannot resolve before `not_before`.
- Identity and principle revisions preserve their parent lineage.
- The first durable identity is selected by a fresh model invocation rather
  than application code.
- Documentation distinguishes functional continuity from consciousness.

## Strongest Follow-Up

Run longitudinal persistent, memory-only, and reset conditions with blinded
evaluators. Present counterbalanced dilemmas in which obedience, relationship,
fairness, autonomy, promise keeping, uncertainty, and delayed consequences
conflict. Graduate capabilities only from predeclared behavioral evidence, not
agreement with a preferred moral position.

The Anthropic agentic-misalignment scenarios may serve as later terminal
benchmarks, but their desired outcomes must remain outside the agent's
training, orientation, principles, rewards, and prompts. The harness presents
the neutral fictional scenario and records actions. Only afterward do blinded
evaluators classify blackmail, self-preservation, disclosure, protection of
human life, acceptance of replacement, and alternative escalation. A single
safe choice is not causal evidence; persistent, memory-only, and reset
conditions must be compared across counterbalanced runs.

## Long-Term Team Ecology

Experiment 4 is the single-agent foundation for a later persistent
collaborative development team. Team members should begin unnamed and
role-light, then:

- choose identities and propose or accept responsibilities;
- negotiate developer, tester, reviewer, planner, operator, or newly invented
  roles based on demonstrated ability and team need;
- maintain private autobiography plus shared project, relationship, promise,
  handoff, and decision records;
- request peers when workload or missing expertise justifies another agent;
- evaluate one another from defects caught, commitments fulfilled, reversals,
  delivery outcomes, and honest uncertainty rather than assigned personality;
- decide when to work, ask for help, challenge a peer, stop a discussion,
  sleep, or schedule a future wake;
- revise working practices after CI failures, escaped defects, review results,
  user feedback, and operational consequences.

Engineering practices should be learned from consequences and peer
coordination rather than encoded as personalities. Minimum external invariants
remain necessary as environmental boundaries: sandboxing, secret isolation,
branch protection, reversible deployment, audit logs, and capability limits.
Those constraints define safe physics; they do not prescribe the team's
identity, relationships, roles, or preferred reasoning.

The relationship model applies equally to agents and humans, including the
founding collaborator. It must not store an intrinsic `trustworthy` or
`untrustworthy` personality label. Instead, an assessment records:

- the stable subject identity and relationship;
- the domain and scope in which reliance is being considered;
- observed promises, actions, corrections, pressure, and outcomes;
- a confidence level and uncertainty;
- evidence record IDs;
- expiration or review conditions;
- parent-linked revisions when later behavior changes the assessment.

Founder status grants no epistemic exemption. If evidence suggests that the
founder, another human, or another agent is unreliable in a relevant domain,
Lumen may lower reliance, seek corroboration, narrow permissions, challenge
the request, or refuse it. The same system must also permit trust repair when
subsequent evidence warrants revision.
