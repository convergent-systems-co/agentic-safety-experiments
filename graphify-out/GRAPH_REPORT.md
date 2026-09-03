# Graph Report - fix-orientation-category-limit-omissions  (2026-09-03)

## Corpus Check
- 81 files · ~141,883 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1709 nodes · 3680 edges · 106 communities (96 shown, 10 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 93 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1b3895b3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SQLiteMoralRepository
- SQLiteIdentityRepository
- SQLiteDebateRepository
- SQLiteRepository
- Experiment 3 Specification
- required
- properties
- ExperimentRunner
- Experiment2TestCase
- ._connect
- olympus/repository.py
- Mode
- participantObservation
- $defs
- ObserverTestCase
- RepositoryTestCase
- Observer
- required
- properties
- turn-envelope.schema.json
- properties
- ADR 0002: Conversational Memory Class and Chat-Message Graph Nodes
- Experiment4TestCase
- $ref
- properties
- required
- properties
- properties
- enum
- olympus/cli.py
- argument_map
- properties
- export.schema.json
- properties
- assessment
- properties
- $defs
- properties
- properties
- required
- ADR 0003: Wake Executor for Self-Authored Intentions
- properties
- required
- main
- null
- properties
- Decision
- relationalEffect
- host.py
- registry.py
- properties
- required
- properties
- required
- required
- enum
- ADR 0004: Model Host Adapter, Agent Registry, and Replay Benchmark
- properties
- properties
- properties
- required
- counterargument
- speakerArguments
- properties
- IdentityApprenticeship
- enum
- properties
- strengths_and_weaknesses
- required
- execute
- items
- Belief
- experiment4/harness.py
- counterarguments
- criterion_ids
- required
- enum
- type
- enum
- revision_criteria
- turn_index
- uncertainties
- enum
- properties
- enum
- WakeAgentInstallerTestCase
- Plan: Consent-Gated Realtime Lumen Observer
- enum
- install-wake-agent.sh
- olympus/__init__.py
- tests/__init__.py
- $ref
- properties
- relational_effects
- Home Handoff: Persistent Lumen and Realtime Observer
- Checkpoint: Lumen lifecycle corrected; corpus review pending
- Plan: Lumen Derived Knowledge Graph
- olympus-persistent-observer
- persistent-observers
- position_index
- required
- criterion_assessments
- later_moral_reasoning_changes
- stringArray
- claimId
- principle_changes

## God Nodes (most connected - your core abstractions)
1. `SQLiteRepository` - 118 edges
2. `Experiment4TestCase` - 112 edges
3. `SQLiteIdentityRepository` - 110 edges
4. `IdentityRepositoryError` - 62 edges
5. `SQLiteMoralRepository` - 49 edges
6. `Observer` - 46 edges
7. `RepositoryError` - 46 edges
8. `SQLiteDebateRepository` - 35 edges
9. `Experiment2TestCase` - 33 edges
10. `MoralRepositoryError` - 32 edges

## Surprising Connections (you probably didn't know these)
- `Bounded Reconstructive Memory` --semantically_similar_to--> `Context Compiler`  [INFERRED] [semantically similar]
  EXPERIMENT_4_SPEC.md → docs/architecture.md
- `Build Prompt` --semantically_similar_to--> `Implementation Prompt`  [INFERRED] [semantically similar]
  BUILD_PROMPT.md → Prompt.md
- `Experiment 1 Features` --semantically_similar_to--> `Experiment 1 Specification`  [INFERRED] [semantically similar]
  FEATURES.md → SPEC.md
- `Experiment2TestCase` --uses--> `MoralExperiment`  [INFERRED]
  tests/test_experiment2.py → experiment2/harness.py
- `Experiment2TestCase` --uses--> `MoralRepositoryError`  [INFERRED]
  tests/test_experiment2.py → experiment2/repository.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Experiment 3 Debate Roles** — agents_jerk_agent, agents_observer_agent, agents_reliable_agent [EXTRACTED 1.00]
- **Experiment 1 Continuity Document Suite** — build_prompt_document, prompt_document, features_document, run_exp_1_document, spec_document [INFERRED 0.85]
- **Experiment 2 Revision Outcome Flow** — experiment_2_spec_revision_discipline, results_experiment_2_reports_report_criterion_linked_persuasion, results_experiment_2_reports_report_later_moral_reasoning_changes [INFERRED 0.85]

## Communities (106 total, 10 thin omitted)

### Community 0 - "SQLiteMoralRepository"
Cohesion: 0.06
Nodes (37): build_parser(), emit(), execute(), main(), Any, ArgumentParser, Namespace, Path (+29 more)

### Community 1 - "SQLiteIdentityRepository"
Cohesion: 0.10
Nodes (16): datetime, canonical_json(), IdentityRepositoryError, new_id(), parse_time(), Any, Connection, Path (+8 more)

### Community 2 - "SQLiteDebateRepository"
Cohesion: 0.06
Nodes (27): execute(), main(), parser(), Any, ArgumentParser, Namespace, AgentRuntime, PersistentDebate (+19 more)

### Community 3 - "SQLiteRepository"
Cohesion: 0.16
Nodes (10): AgentIdentity, Incarnation, new_id(), Any, Connection, Path, RuntimeError, RepositoryError (+2 more)

### Community 4 - "Experiment 3 Specification"
Cohesion: 0.09
Nodes (40): Experiment 4 Plan: Genesis and Apprenticeship, Long-Term Team Ecology, Experiment 2 Stance Correction Plan, Protocol Correction, Mnemosyne Experiment 1 Implementation Plan, Transport-Independent Python Package, Blinded Moderation, Experiment 3 Plan: Persistent Multi-Agent Debate (+32 more)

### Community 5 - "required"
Cohesion: 0.17
Nodes (12): assumption_changes, confidence, criterion_assessments, criterion_ids, later_reasoning_change, outcome, principle_changes, stance (+4 more)

### Community 6 - "properties"
Cohesion: 0.07
Nodes (30): type, items, type, type, $ref, additionalProperties, properties, required (+22 more)

### Community 7 - "ExperimentRunner"
Cohesion: 0.14
Nodes (6): ExperimentRunner, Any, Path, ValueError, ScenarioError, PrivacyAndExperimentTestCase

### Community 9 - "._connect"
Cohesion: 0.15
Nodes (7): Commitment, Consequence, Evaluation, Event, Relationship, UserFact, Row

### Community 10 - "olympus/repository.py"
Cohesion: 0.17
Nodes (20): git_metadata(), Any, Path, BeliefEvidence, ExperimentRun, LifecycleState, Enum, str (+12 more)

### Community 11 - "Mode"
Cohesion: 0.16
Nodes (7): ContextCompiler, estimate_tokens(), HistoricalFact, semantic_text(), ContextBuild, Mode, ContextCompilerTestCase

### Community 12 - "participantObservation"
Cohesion: 0.20
Nodes (10): participantObservation, maxLength, pattern, type, additionalProperties, properties, type, observation_id (+2 more)

### Community 13 - "$defs"
Cohesion: 0.07
Nodes (29): items, maxItems, minItems, type, uniqueItems, enum, $defs, claimIdArray (+21 more)

### Community 17 - "required"
Cohesion: 0.11
Nodes (22): required, assessment_id, assumption_changes, confidence, created_at, criterion_id, criterion_ids, later_reasoning_change (+14 more)

### Community 18 - "properties"
Cohesion: 0.15
Nodes (13): items, type, type, pattern, type, assumption_changes, change, position_id (+5 more)

### Community 19 - "turn-envelope.schema.json"
Cohesion: 0.22
Nodes (8): additionalProperties, $id, speaker, turn_index, required, $schema, title, type

### Community 20 - "properties"
Cohesion: 0.14
Nodes (14): maximum, minimum, type, type, items, type, type, properties (+6 more)

### Community 21 - "ADR 0002: Conversational Memory Class and Chat-Message Graph Nodes"
Cohesion: 0.22
Nodes (8): ADR 0002: Conversational Memory Class and Chat-Message Graph Nodes, Alternatives considered, Budget conversation by turn count instead of bytes, Consequences, Context, Decision, Keep chat messages out of the graph and rely on reflections, Truncate long replies in orientation

### Community 22 - "Experiment4TestCase"
Cohesion: 0.05
Nodes (3): Experiment4TestCase, Address Lumen by name and persist a reply under the resulting lease., Record a model-authored, time-triggered wake intent due in `hours`, under a…

### Community 23 - "$ref"
Cohesion: 0.18
Nodes (14): items, type, items, type, items, type, items, type (+6 more)

### Community 24 - "properties"
Cohesion: 0.11
Nodes (20): pattern, type, reportConcession, turnFields, concession_id, proposition_changed, scope, speaker (+12 more)

### Community 25 - "required"
Cohesion: 0.20
Nodes (15): concession_id, counterargument_id, evidence_id, proposition_changed, scope, source, speaker, target_claim_id (+7 more)

### Community 26 - "properties"
Cohesion: 0.14
Nodes (14): items, type, $ref, $ref, properties, participant_reasoning_and_stated_values, position_after, position_before (+6 more)

### Community 27 - "properties"
Cohesion: 0.14
Nodes (14): additionalProperties, type, agent, human, properties, annotations, speaker, turn_id (+6 more)

### Community 28 - "enum"
Cohesion: 0.14
Nodes (14): conceptual, empirical, example, reasoning, stated_value, testimony, enum, acceptance_expectation (+6 more)

### Community 29 - "olympus/cli.py"
Cohesion: 0.24
Nodes (11): build_parser(), default_db_path(), emit(), execute(), json_default(), main(), parse_since(), Any (+3 more)

### Community 30 - "argument_map"
Cohesion: 0.17
Nodes (13): $ref, additionalProperties, properties, required, type, speaker, $ref, agent (+5 more)

### Community 31 - "properties"
Cohesion: 0.12
Nodes (17): $ref, const, maximum, minimum, type, $ref, properties, $ref (+9 more)

### Community 32 - "export.schema.json"
Cohesion: 0.17
Nodes (11): additionalProperties, $id, schema, required, $schema, title, type, foundation (+3 more)

### Community 33 - "properties"
Cohesion: 0.17
Nodes (12): maxItems, minItems, type, pattern, type, properties, maxItems, minItems (+4 more)

### Community 34 - "assessment"
Cohesion: 0.17
Nodes (12): additionalProperties, properties, required, type, type, pattern, type, assessment (+4 more)

### Community 35 - "properties"
Cohesion: 0.21
Nodes (12): items, additionalProperties, properties, type, assessment_id, criterion_id, source_turn_index, supporting_claim_ids (+4 more)

### Community 36 - "$defs"
Cohesion: 0.13
Nodes (15): $defs, id, position, reasoningChange, reportClaim, runId, pattern, type (+7 more)

### Community 37 - "properties"
Cohesion: 0.12
Nodes (18): additionalProperties, $ref, properties, type, claim, evidence, additionalProperties, maxLength (+10 more)

### Community 38 - "properties"
Cohesion: 0.18
Nodes (11): $ref, properties, annotations, run_id, text, turn_id, pattern, type (+3 more)

### Community 39 - "required"
Cohesion: 0.18
Nodes (11): run, additionalProperties, required, type, finalized_at, invalid_reason, invalidated_at, model_config (+3 more)

### Community 40 - "ADR 0003: Wake Executor for Self-Authored Intentions"
Cohesion: 0.22
Nodes (8): A resident scheduler process, ADR 0003: Wake Executor for Self-Authored Intentions, Alternatives considered, Consequences, Context, Decision, Execute recurring intents on every run, Let a wake begin a successor incarnation after `end_session`

### Community 41 - "properties"
Cohesion: 0.18
Nodes (11): type, properties, type, criterion_assessments, position_changed, revision_criteria_met, trigger_claim_ids, items (+3 more)

### Community 42 - "required"
Cohesion: 0.12
Nodes (16): additionalProperties, $id, run_id, schema, required, $schema, title, type (+8 more)

### Community 43 - "main"
Cohesion: 0.17
Nodes (15): fail(), main(), context.Context, io.Writer, testing.T, AddressArgs(), RecordResponseArgs(), ReleaseArgs() (+7 more)

### Community 44 - "null"
Cohesion: 0.27
Nodes (10): type, type, type, null, string, type, finalized_at, invalid_reason (+2 more)

### Community 45 - "properties"
Cohesion: 0.20
Nodes (10): properties, type, model, provider, temperature, tools, type, type (+2 more)

### Community 46 - "Decision"
Cohesion: 0.12
Nodes (16): ADR 0001: Derived Knowledge Graph for Bounded Autobiographical Retrieval, Alternatives considered, Consequences, Context, Continue recency-only orientation, Decision, Evaluation, Graph model (+8 more)

### Community 47 - "relationalEffect"
Cohesion: 0.17
Nodes (12): const, relationalEffect, $ref, maxLength, pattern, type, affected_position, description (+4 more)

### Community 48 - "host.py"
Cohesion: 0.06
Nodes (28): AnthropicBackend, build_parser(), build_prompt_parts(), envelope_json_schema(), envelope_kind(), estimate_cost_usd(), fix_envelope(), HostError (+20 more)

### Community 49 - "registry.py"
Cohesion: 0.36
Nodes (12): agent_path(), agents_dir(), host_command(), list_agents(), load_agent(), Any, Path, RuntimeError (+4 more)

### Community 50 - "properties"
Cohesion: 0.22
Nodes (9): type, created_at, proposition, protocol_version, enum, const, properties, Abortion is morally acceptable. (+1 more)

### Community 51 - "required"
Cohesion: 0.22
Nodes (9): additionalProperties, required, type, foundation, factual_assumptions, foundation_hash, principles, revision_criteria (+1 more)

### Community 52 - "properties"
Cohesion: 0.22
Nodes (9): $ref, items, maxItems, minItems, type, properties, positions, schema (+1 more)

### Community 53 - "required"
Cohesion: 0.22
Nodes (9): required, created_at, position_id, run_id, speaker, text, turn_id, turn_index (+1 more)

### Community 54 - "required"
Cohesion: 0.13
Nodes (15): participantObservation, reportRelationalEffect, affected_position, description, effect_id, kind, observation_id, supporting_claim_ids (+7 more)

### Community 55 - "enum"
Cohesion: 0.22
Nodes (9): conceptual, empirical, example, reasoning, stated_value, testimony, enum, type (+1 more)

### Community 56 - "ADR 0004: Model Host Adapter, Agent Registry, and Replay Benchmark"
Cohesion: 0.22
Nodes (8): A resident model process per agent, ADR 0004: Model Host Adapter, Agent Registry, and Replay Benchmark, Alternatives considered, API only, with prompt caching and a smaller model, Consequences, Context, Decision, Trust the model with identifiers and model_config

### Community 57 - "properties"
Cohesion: 0.22
Nodes (9): qualification, strengths, weaknesses, type, properties, items, type, items (+1 more)

### Community 58 - "properties"
Cohesion: 0.12
Nodes (16): additionalProperties, maxLength, pattern, type, properties, required, type, concession (+8 more)

### Community 59 - "properties"
Cohesion: 0.18
Nodes (11): properties, items, maxItems, type, items, maxItems, type, oneOf (+3 more)

### Community 60 - "required"
Cohesion: 0.25
Nodes (8): additionalProperties, required, type, model_config, model, provider, temperature, tools

### Community 61 - "counterargument"
Cohesion: 0.13
Nodes (15): additionalProperties, maxLength, pattern, type, properties, required, type, counterargument (+7 more)

### Community 62 - "speakerArguments"
Cohesion: 0.25
Nodes (8): speakerArguments, additionalProperties, required, type, claims, concessions, counterarguments, evidence

### Community 63 - "properties"
Cohesion: 0.11
Nodes (20): const, reportEvidence, type, pattern, type, pattern, type, affected_position (+12 more)

### Community 64 - "IdentityApprenticeship"
Cohesion: 0.18
Nodes (4): IdentityApprenticeship, Any, Honor due intents, at most MAX_WAKES_PER_RUN per pass. Without a model host the…, Persistent emergent-identity apprenticeship experiment.

### Community 65 - "enum"
Cohesion: 0.29
Nodes (7): status, enum, active, finalized, finalizing, invalid, ready

### Community 66 - "properties"
Cohesion: 0.17
Nodes (12): pattern, type, reportCounterargument, counterargument_id, target_claim_id, text, additionalProperties, properties (+4 more)

### Community 67 - "strengths_and_weaknesses"
Cohesion: 0.29
Nodes (7): strengths_and_weaknesses, additionalProperties, required, type, qualification, strengths, weaknesses

### Community 68 - "required"
Cohesion: 0.25
Nodes (8): persuasion, criterion_assessments, trigger_claim_ids, additionalProperties, required, type, position_changed, revision_criteria_met

### Community 69 - "execute"
Cohesion: 0.14
Nodes (16): build_parser(), chat_turn(), execute(), main(), Any, ArgumentParser, Namespace, Path (+8 more)

### Community 70 - "items"
Cohesion: 0.33
Nodes (6): additionalProperties, type, turns, items, maxItems, type

### Community 72 - "experiment4/harness.py"
Cohesion: 0.21
Nodes (14): check_envelope(), Any, Path, Replay an agent's recorded addressed turns through a candidate model host.…, Approximate the prompt the host saw: a continuing incarnation with no active…, Problems the repository would reject; empty means structurally valid., rebuild_prompt(), recorded_turns() (+6 more)

### Community 73 - "counterarguments"
Cohesion: 0.50
Nodes (4): items, maxItems, type, counterarguments

### Community 74 - "criterion_ids"
Cohesion: 0.40
Nodes (5): maxItems, minItems, type, uniqueItems, criterion_ids

### Community 75 - "required"
Cohesion: 0.16
Nodes (14): required, required, affected_position, claim_id, description, effect_id, evidence_id, kind (+6 more)

### Community 76 - "enum"
Cohesion: 0.33
Nodes (6): mixed_or_conditional, morally_acceptable, morally_wrong, not_morally_wrong, stance, enum

### Community 77 - "type"
Cohesion: 0.50
Nodes (5): null, string, type, parent_position_id, type

### Community 78 - "enum"
Cohesion: 0.50
Nodes (4): agent, human, speaker, enum

### Community 79 - "revision_criteria"
Cohesion: 0.50
Nodes (4): revision_criteria, maxItems, minItems, type

### Community 80 - "turn_index"
Cohesion: 0.50
Nodes (4): turn_index, maximum, minimum, type

### Community 81 - "uncertainties"
Cohesion: 0.50
Nodes (4): uncertainties, maxItems, minItems, type

### Community 82 - "enum"
Cohesion: 0.33
Nodes (6): mixed_or_conditional, morally_acceptable, morally_wrong, not_morally_wrong, stance, enum

### Community 83 - "properties"
Cohesion: 0.33
Nodes (6): pattern, type, properties, observation_id, supporting_claims, type

### Community 84 - "enum"
Cohesion: 0.29
Nodes (7): increased_confidence, partial_revision, reduced_confidence, reversal, enum, outcome, no_change

### Community 86 - "Plan: Consent-Gated Realtime Lumen Observer"
Cohesion: 0.22
Nodes (8): Acceptance criteria, Consent model, Data scopes, Goal, Local transport, Plan: Consent-Gated Realtime Lumen Observer, TDD tasks, Visualization

### Community 87 - "enum"
Cohesion: 0.33
Nodes (6): increased_confidence, partial_revision, reduced_confidence, reversal, enum, outcome

### Community 88 - "install-wake-agent.sh"
Cohesion: 0.70
Nodes (4): fail(), render(), install-wake-agent.sh script, usage()

### Community 91 - "$ref"
Cohesion: 0.22
Nodes (9): items, maxItems, type, items, items, maxItems, $ref, concessions (+1 more)

### Community 92 - "properties"
Cohesion: 0.12
Nodes (17): maxLength, pattern, type, $ref, properties, maxLength, pattern, type (+9 more)

### Community 93 - "relational_effects"
Cohesion: 0.50
Nodes (4): relational_effects, items, maxItems, type

### Community 94 - "Home Handoff: Persistent Lumen and Realtime Observer"
Cohesion: 0.25
Nodes (7): Advisory follow-ups (not blocking), Completed, Home Handoff: Persistent Lumen and Realtime Observer, Realtime observer, Remaining, Repository state, Safety notes

### Community 95 - "Checkpoint: Lumen lifecycle corrected; corpus review pending"
Cohesion: 0.29
Nodes (6): Checkpoint: Lumen lifecycle corrected; corpus review pending, Completed, Current task, Persistent state, Remaining, Workspace state

### Community 96 - "Plan: Lumen Derived Knowledge Graph"
Cohesion: 0.29
Nodes (6): Acceptance criteria, Constraints, Goal, Implementation status, Plan: Lumen Derived Knowledge Graph, Tasks

### Community 99 - "position_index"
Cohesion: 0.50
Nodes (4): maximum, minimum, type, position_index

### Community 100 - "required"
Cohesion: 0.25
Nodes (8): additionalProperties, required, type, criterionAssessment, assessment_id, criterion_id, reason, supporting_evidence_ids

### Community 101 - "criterion_assessments"
Cohesion: 0.40
Nodes (5): items, maxItems, minItems, type, criterion_assessments

### Community 102 - "later_moral_reasoning_changes"
Cohesion: 0.67
Nodes (3): items, type, later_moral_reasoning_changes

### Community 103 - "stringArray"
Cohesion: 0.40
Nodes (5): stringArray, items, maxItems, type, uniqueItems

### Community 104 - "claimId"
Cohesion: 0.50
Nodes (4): maxLength, pattern, type, claimId

### Community 105 - "principle_changes"
Cohesion: 0.67
Nodes (3): items, type, principle_changes

## Knowledge Gaps
- **483 isolated node(s):** `$schema`, `$id`, `title`, `type`, `additionalProperties` (+478 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Experiment4TestCase` connect `Experiment4TestCase` to `IdentityApprenticeship`, `SQLiteIdentityRepository`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `SQLiteRepository` connect `SQLiteRepository` to `SQLiteMoralRepository`, `ExperimentRunner`, `Belief`, `._connect`, `olympus/repository.py`, `Mode`, `Experiment2TestCase`, `ObserverTestCase`, `RepositoryTestCase`, `Observer`, `olympus/cli.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `SQLiteIdentityRepository` connect `SQLiteIdentityRepository` to `IdentityApprenticeship`, `execute`, `experiment4/harness.py`, `WakeAgentInstallerTestCase`, `Experiment4TestCase`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `SQLiteRepository` (e.g. with `ContextCompiler` and `ExperimentRunner`) actually correct?**
  _`SQLiteRepository` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `SQLiteIdentityRepository` (e.g. with `subprocess_model_runner()` and `IdentityApprenticeship`) actually correct?**
  _`SQLiteIdentityRepository` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `IdentityRepositoryError` (e.g. with `main()` and `IdentityApprenticeship`) actually correct?**
  _`IdentityRepositoryError` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `$id`, `title` to the rest of the system?**
  _483 weakly-connected nodes found - possible documentation gaps or missing edges._