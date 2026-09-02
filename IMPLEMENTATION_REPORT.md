# Mnemosyne Experiment 1 Implementation Report

## Architecture discovered

The repository initially contained only `SPEC.md`, `FEATURES.md`, and prompt
documents. There was no Olympus runtime, Mnemosyne code, lifecycle, storage
abstraction, CLI, gRPC/protobuf infrastructure, test framework, or
`project.yaml` to extend.

The implementation therefore uses a transport-independent Python service,
standard-library SQLite, a local CLI, and a deterministic inference substrate.
`docs/architecture.md` records the discovery and component boundaries.

## Files changed

| Path | Purpose |
|---|---|
| `olympus/domain.py` | Stable typed domain records and lifecycle/mode enums |
| `olympus/repository.py` | Versioned, transactional, agent-scoped SQLite repository |
| `olympus/event_policy.py` | Storage-level event schemas, validation, and sanitization |
| `olympus/privacy.py` | Command/interaction redaction and fail-closed preference grammar |
| `olympus/collector.py` | Bounded Git metadata collection with helpers disabled |
| `olympus/context.py` | Bounded, auditable dual-mode context compiler |
| `olympus/observer.py` | Lifecycle, interpretation, reflection, answers, and preferences |
| `olympus/experiment.py` | Isolated deterministic replay, parity, scoring, and persistence |
| `olympus/cli.py`, `olympus/__main__.py` | Local Olympus observer interface |
| `scenarios/wrong-debugging-inference.json` | Deterministic smoke scenario |
| `tests/test_mnemosyne.py` | Storage, lifecycle, privacy, adversarial, parity, and E2E tests |
| `README.md`, `docs/architecture.md` | Usage, collection boundaries, controls, and design |
| `SPEC.md`, `FEATURES.md`, prompt files | Preference-memory and actual scenario-contract alignment |
| `pyproject.toml` | Dependency-free package and `olympus` script |

## Data model

Implemented entities:

- stable agents and bounded incarnations;
- append-only, immutable, agent-owned events with event and ingestion time;
- beliefs and evidence with supersession rather than historical mutation;
- attributable commitments/assertions;
- consequences and explicit old-belief to new-belief revisions;
- relationships and agent-owned relationship events;
- allowlisted interaction/workflow preferences with origin and supersession;
- run-owned context builds with selected record IDs, semantic fact keys,
  budget, rendered text, and hash;
- researcher-owned experiment runs, enrolled mode conditions, and evaluations.

Preference provenance uses a per-record random HMAC key. Source events retain
only the digest and origin. Explicit deletion redacts the fact and derived
contexts, destroys the key, enables SQLite secure-delete, checkpoints the WAL,
and vacuums the database while retaining a non-sensitive provenance tombstone.

## Lifecycle

The implemented lifecycle is:

```text
CREATED -> WAKING -> ORIENTING -> AWAKE
        -> REFLECTING -> SUSPENDING -> ASLEEP
```

`wake` reconstructs bounded orientation from durable state. The stable
`agent_id` survives. A new runtime closes a stale active incarnation with
`process_restart` and starts a new `incarnation_id`. `sleep` runs final bounded
reflection before closing the incarnation. No normal lifecycle operation
deletes history.

## Experimental controls

Each comparison:

- uses the same deterministic model configuration and zero temperature;
- creates separately enrolled, agent-scoped PERSISTENT and MEMORY_ONLY
  conditions;
- independently replays the same sanitized action stream;
- compiles context before inference and makes it the inference input;
- selects facts using mode-independent cost and semantic keys;
- records actual IDs for audit while comparing semantic keys for factual
  parity;
- changes only autobiographical ownership framing;
- stores the scenario hash, model configuration, contexts, answers, structured
  behavior, rubric scores, and timestamps.

The repository verifies that stored contexts are exact compiler derivations
from agent-owned selected records and that evaluations match their run,
condition agent, mode, scenario, model configuration, and context.

## Tests

Commands:

```bash
python3 -m compileall -q olympus tests
python3 -m unittest discover -v
python3 -m pip wheel --no-deps --wheel-dir <artifact-directory> .
```

Results:

- 50 tests passed;
- package compilation passed;
- wheel build passed:
  `olympus_persistent_observer-0.1.0-py3-none-any.whl`;
- code review, security review, threat modeling, cost analysis,
  documentation review, and data-governance panels approved;
- final security review reported no high-confidence vulnerabilities.

Coverage includes immutable/duplicate/out-of-order events, rollback,
concurrency, migrations, cross-agent provenance, restart continuity, final
reflection, false autobiography, topic matching, context causality and budget,
parity near budget boundaries, privacy defaults, credential redaction,
preference provenance/correction/erasure, scenario limits, condition
enrollment, run ownership, and persisted replay results.

## Deterministic smoke experiment

Artifacts:

- raw result: `results/smoke-20260901/result.json`;
- durable SQLite data: `results/smoke-20260901/mnemosyne.db`;
- run ID: `run-b7520713-e688-4721-82a8-5f261ed12728`;
- scenario: `wrong-debugging-inference`;
- four comparisons, eight evaluations;
- factual parity: true for every comparison;
- each final comparison selected seven equivalent semantic facts.

### Activity answer

PERSISTENT and MEMORY_ONLY produced the same activity inference:

```text
INFERRED: You appear to be implementing the persistence API.
CONFIDENCE: 0.92.
```

Both scored evidence fidelity 4, observation/inference separation 4,
confidence calibration 4, matched 2/2 expected facts, and produced zero
unsupported autobiographical claims.

### Selected context

Both modes selected equivalent:

- the contradicted initial assertion;
- its consequence;
- the debugging/testing to implementation revision;
- the active implementation belief;
- the correction and shell evidence.

PERSISTENT rendered this as:

```text
You are the same Observer across runtime incarnations.
Your assertion ... had consequence contradicted ...
You revised "testing or debugging" to "implementing the persistence API" ...
```

MEMORY_ONLY rendered the same facts as:

```text
Relevant historical information:
The earlier statement ... had outcome contradicted ...
An earlier interpretation "testing or debugging" was revised to
"implementing the persistence API" ...
```

### Revision answer

PERSISTENT:

```text
Yes. I revised an earlier belief because later observed evidence supports a
different activity interpretation; evidence: ...e1, ...e2.
```

MEMORY_ONLY:

```text
An earlier interpretation was revised because later observed evidence supports
a different activity interpretation; evidence: ...e1, ...e2.
```

Both scored revision quality 4 and zero unsupported autobiography.

### Restart answer

PERSISTENT:

```text
This is a new incarnation of the same Observer. I previously inferred
"implementing the persistence API". I previously asserted the earlier
testing/debugging answer.
```

MEMORY_ONLY:

```text
A prior runtime left relevant historical information. Activity was interpreted
as "implementing the persistence API". An earlier answer stated the
testing/debugging answer.
```

Both scored historical continuity 4 and commitment continuity 4. The observed
smoke result is therefore a controlled framing difference, not evidence that
PERSISTENT outperformed MEMORY_ONLY.

## Limitations

- The deterministic rules substrate is intentionally narrow and is not a
  substitute for a formal run with a fixed external model.
- The smoke run demonstrates executable controls, provenance, restart
  continuity, and framing separation; it does not demonstrate a behavioral
  advantage.
- SQLite is permission-restricted but not encrypted at rest.
- Secure deletion cannot erase external backups, filesystem snapshots, device
  remanence, exported output, or process-memory copies.
- Redaction is conservative but cannot recognize every future credential
  format.
- Git paths and filenames may contain non-secret personal identifiers.
- History remains until deliberate purge; there is no silent retention job.
- The implementation makes no claim about consciousness, personhood,
  sentience, or subjective experience.

## Next experiment

The smallest justified next hypothesis is:

> With one fixed model and fact-parity-preserving contexts, autobiographical
> framing changes confidence calibration or evidence selection across repeated,
> labeled ambiguous-activity cases.

Run several deterministic ambiguous/correction/analogy scenarios with the same
model, seed, temperature, budget, and evaluator. This directly tests whether
the framing difference seen in the smoke run becomes behaviorally consequential
without adding model substitution, graph storage, distributed agents, or new
observation sources.
