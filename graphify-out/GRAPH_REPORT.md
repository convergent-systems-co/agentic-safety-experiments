# Graph Report - fix-orientation-category-limit-omissions  (2026-09-03)

## Corpus Check
- 89 files · ~149,605 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1839 nodes · 3956 edges · 107 communities (95 shown, 12 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 94 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `00020600`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SQLiteMoralRepository
- SQLiteIdentityRepository
- SQLiteDebateRepository
- SQLiteRepository
- Experiment 3 Specification
- required
- claim
- ExperimentRunner
- Experiment2TestCase
- ._connect
- olympus/repository.py
- Mode
- kind
- $defs
- ObserverTestCase
- RepositoryTestCase
- Observer
- required
- type
- turn-envelope.schema.json
- enum
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
- claimIdArray
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
- enum
- properties
- ADR 0004: Model Host Adapter, Agent Registry, and Replay Benchmark
- properties
- properties
- relational_effects
- required
- required
- speakerArguments
- ReadingsTestCase
- IdentityApprenticeship
- enum
- AgentChatApp
- strengths_and_weaknesses
- properties
- execute
- items
- Belief
- benchmark_host.py
- concessions
- criterion_ids
- required
- enum
- confidence
- enum
- revision_criteria
- turn_index
- uncertainties
- AgentFixture
- properties
- later_moral_reasoning_changes
- WakeAgentInstallerTestCase
- Plan: Consent-Gated Realtime Lumen Observer
- properties
- install-wake-agent.sh
- olympus/__init__.py
- tests/__init__.py
- run_turn
- properties
- ADR 0005: agent-chat Terminal UI and Cancel-Safe Turns
- Home Handoff: Persistent Lumen and Realtime Observer
- Checkpoint: Lumen lifecycle corrected; corpus review pending
- Plan: Lumen Derived Knowledge Graph
- olympus-persistent-observer
- persistent-observers
- $ref
- required
- criterion_assessments
- properties
- stringArray
- install-agent-chat.sh
- properties
- ADR 0006: Readings, Remembered as Gist and Notes

## God Nodes (most connected - your core abstractions)
1. `SQLiteIdentityRepository` - 120 edges
2. `SQLiteRepository` - 118 edges
3. `Experiment4TestCase` - 112 edges
4. `IdentityRepositoryError` - 71 edges
5. `SQLiteMoralRepository` - 49 edges
6. `Observer` - 46 edges
7. `RepositoryError` - 46 edges
8. `SQLiteDebateRepository` - 35 edges
9. `IdentityApprenticeship` - 33 edges
10. `Experiment2TestCase` - 33 edges

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

## Communities (107 total, 12 thin omitted)

### Community 0 - "SQLiteMoralRepository"
Cohesion: 0.06
Nodes (37): build_parser(), emit(), execute(), main(), Any, ArgumentParser, Namespace, Path (+29 more)

### Community 1 - "SQLiteIdentityRepository"
Cohesion: 0.07
Nodes (35): datetime, One addressed turn with a registered agent's host, safe to cancel. The address…, main(), Wake-executor runner: the host is bounded by the same clipped runtime as the…, subprocess_model_runner(), The vocative rule that wakes an agent: the name at the start, followed by the…, starts_with_name(), Persistent emergent-identity apprenticeship experiment. (+27 more)

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

### Community 6 - "claim"
Cohesion: 0.25
Nodes (8): additionalProperties, $ref, properties, type, claim, claim_id, text, $ref

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

### Community 12 - "kind"
Cohesion: 0.22
Nodes (9): $ref, maxLength, pattern, type, properties, kind, observation_id, supporting_claim_ids (+1 more)

### Community 13 - "$defs"
Cohesion: 0.10
Nodes (20): maxLength, pattern, type, $defs, claimId, positionUpdate, shortText, text (+12 more)

### Community 17 - "required"
Cohesion: 0.16
Nodes (16): assumption_changes, confidence, created_at, criterion_ids, later_reasoning_change, outcome, position_id, principle_changes (+8 more)

### Community 18 - "type"
Cohesion: 0.08
Nodes (28): items, type, type, items, type, reasoningChange, type, pattern (+20 more)

### Community 19 - "turn-envelope.schema.json"
Cohesion: 0.20
Nodes (9): additionalProperties, $id, speaker, text, turn_index, required, $schema, title (+1 more)

### Community 20 - "enum"
Cohesion: 0.29
Nodes (7): enum, criterionId, criterion-competing-principle, criterion-defeating-counterexample, criterion-factual-assumption, criterion-internal-contradiction, criterion-invalid-inference

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
Cohesion: 0.08
Nodes (30): pattern, type, reportCounterargument, reportEvidence, turnFields, pattern, type, counterargument_id (+22 more)

### Community 25 - "required"
Cohesion: 0.12
Nodes (23): affected_position, concession_id, counterargument_id, description, effect_id, evidence_id, kind, observation_id (+15 more)

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
Cohesion: 0.11
Nodes (19): $ref, const, increased_confidence, partial_revision, reduced_confidence, reversal, $ref, enum (+11 more)

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
Cohesion: 0.12
Nodes (18): items, additionalProperties, properties, required, assessment_id, criterion_id, reason, supporting_evidence_ids (+10 more)

### Community 36 - "$defs"
Cohesion: 0.17
Nodes (12): $defs, id, position, reportClaim, runId, pattern, type, additionalProperties (+4 more)

### Community 37 - "properties"
Cohesion: 0.20
Nodes (10): evidence, additionalProperties, maxLength, pattern, type, properties, type, evidence_id (+2 more)

### Community 38 - "properties"
Cohesion: 0.18
Nodes (11): $ref, properties, annotations, run_id, text, turn_id, pattern, type (+3 more)

### Community 39 - "required"
Cohesion: 0.18
Nodes (11): run, additionalProperties, required, type, finalized_at, invalid_reason, invalidated_at, model_config (+3 more)

### Community 40 - "ADR 0003: Wake Executor for Self-Authored Intentions"
Cohesion: 0.22
Nodes (8): A resident scheduler process, ADR 0003: Wake Executor for Self-Authored Intentions, Alternatives considered, Consequences, Context, Decision, Execute recurring intents on every run, Let a wake begin a successor incarnation after `end_session`

### Community 41 - "claimIdArray"
Cohesion: 0.33
Nodes (6): items, maxItems, minItems, type, uniqueItems, claimIdArray

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
Nodes (30): AnthropicBackend, attach_readings(), build_parser(), build_prompt_parts(), envelope_json_schema(), envelope_kind(), estimate_cost_usd(), fix_envelope() (+22 more)

### Community 49 - "registry.py"
Cohesion: 0.37
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

### Community 54 - "enum"
Cohesion: 0.10
Nodes (20): participantObservation, conceptual, empirical, example, reasoning, source, stated_value, testimony (+12 more)

### Community 55 - "properties"
Cohesion: 0.18
Nodes (11): const, reportRelationalEffect, type, pattern, type, affected_position, description, effect_id (+3 more)

### Community 56 - "ADR 0004: Model Host Adapter, Agent Registry, and Replay Benchmark"
Cohesion: 0.22
Nodes (8): A resident model process per agent, ADR 0004: Model Host Adapter, Agent Registry, and Replay Benchmark, Alternatives considered, API only, with prompt caching and a smaller model, Consequences, Context, Decision, Trust the model with identifiers and model_config

### Community 57 - "properties"
Cohesion: 0.22
Nodes (9): qualification, strengths, weaknesses, type, properties, items, type, items (+1 more)

### Community 58 - "properties"
Cohesion: 0.12
Nodes (16): maxLength, pattern, type, properties, maxLength, pattern, type, properties (+8 more)

### Community 59 - "relational_effects"
Cohesion: 0.50
Nodes (4): relational_effects, items, maxItems, type

### Community 60 - "required"
Cohesion: 0.25
Nodes (8): additionalProperties, required, type, model_config, model, provider, temperature, tools

### Community 61 - "required"
Cohesion: 0.15
Nodes (13): additionalProperties, required, type, additionalProperties, required, type, concession, counterargument (+5 more)

### Community 62 - "speakerArguments"
Cohesion: 0.25
Nodes (8): speakerArguments, additionalProperties, required, type, claims, concessions, counterarguments, evidence

### Community 64 - "IdentityApprenticeship"
Cohesion: 0.16
Nodes (5): addressed_response_schema(), IdentityApprenticeship, Any, Honor due intents, at most MAX_WAKES_PER_RUN per pass. Without a model host the…, The envelope a host must return for an addressed turn, with guidance in place…

### Community 65 - "enum"
Cohesion: 0.29
Nodes (7): status, enum, active, finalized, finalizing, invalid, ready

### Community 66 - "AgentChatApp"
Cohesion: 0.09
Nodes (23): ComposeResult, agent_presence(), _connect(), Any, Connection, Read-only presence and transcript for a registered agent. Everything here opens…, The last `limit` messages with their replies, oldest first., recent_transcript() (+15 more)

### Community 67 - "strengths_and_weaknesses"
Cohesion: 0.29
Nodes (7): strengths_and_weaknesses, additionalProperties, required, type, qualification, strengths, weaknesses

### Community 68 - "properties"
Cohesion: 0.13
Nodes (15): type, persuasion, criterion_assessments, trigger_claim_ids, additionalProperties, properties, required, type (+7 more)

### Community 69 - "execute"
Cohesion: 0.14
Nodes (12): build_parser(), chat_turn(), execute(), Any, ArgumentParser, Namespace, Path, Run a model host with a prompt on stdin and read its envelope. Host stderr goes… (+4 more)

### Community 70 - "items"
Cohesion: 0.33
Nodes (6): additionalProperties, type, turns, items, maxItems, type

### Community 72 - "benchmark_host.py"
Cohesion: 0.27
Nodes (12): check_envelope(), Any, Path, Replay an agent's recorded addressed turns through a candidate model host.…, Approximate the prompt the host saw: a continuing incarnation with no active…, Problems the repository would reject; empty means structurally valid., rebuild_prompt(), recorded_turns() (+4 more)

### Community 73 - "concessions"
Cohesion: 0.50
Nodes (4): items, maxItems, type, concessions

### Community 74 - "criterion_ids"
Cohesion: 0.40
Nodes (5): maxItems, minItems, type, uniqueItems, criterion_ids

### Community 75 - "required"
Cohesion: 0.24
Nodes (10): required, required, affected_position, claim_id, description, effect_id, evidence_id, kind (+2 more)

### Community 76 - "enum"
Cohesion: 0.33
Nodes (6): mixed_or_conditional, morally_acceptable, morally_wrong, not_morally_wrong, stance, enum

### Community 77 - "confidence"
Cohesion: 0.50
Nodes (4): maximum, minimum, type, confidence

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

### Community 82 - "AgentFixture"
Cohesion: 0.16
Nodes (5): AgentFixture, ChatSessionTestCase, PresenceTestCase, RegistryFieldsTestCase, ScreenTestCase

### Community 83 - "properties"
Cohesion: 0.07
Nodes (28): type, items, type, type, $ref, additionalProperties, properties, required (+20 more)

### Community 84 - "later_moral_reasoning_changes"
Cohesion: 0.67
Nodes (3): items, type, later_moral_reasoning_changes

### Community 86 - "Plan: Consent-Gated Realtime Lumen Observer"
Cohesion: 0.22
Nodes (8): Acceptance criteria, Consent model, Data scopes, Goal, Local transport, Plan: Consent-Gated Realtime Lumen Observer, TDD tasks, Visualization

### Community 87 - "properties"
Cohesion: 0.20
Nodes (10): properties, items, maxItems, type, items, maxItems, oneOf, counterarguments (+2 more)

### Community 88 - "install-wake-agent.sh"
Cohesion: 0.70
Nodes (4): fail(), render(), install-wake-agent.sh script, usage()

### Community 91 - "run_turn"
Cohesion: 0.27
Nodes (10): address_text(), ChatCancelled, Any, RuntimeError, Only a leading vocative wakes the agent. When the registry records the agent's…, Run a host as a child process; kill it on cancel or timeout. Host stderr goes…, run_host_process(), run_turn() (+2 more)

### Community 92 - "properties"
Cohesion: 0.12
Nodes (17): maxLength, pattern, type, $ref, properties, maxLength, pattern, type (+9 more)

### Community 93 - "ADR 0005: agent-chat Terminal UI and Cancel-Safe Turns"
Cohesion: 0.25
Nodes (7): A Go TUI over the existing adapter, ADR 0005: agent-chat Terminal UI and Cancel-Safe Turns, Alternatives considered, Consequences, Context, Decision, Standard-library curses

### Community 94 - "Home Handoff: Persistent Lumen and Realtime Observer"
Cohesion: 0.25
Nodes (7): Advisory follow-ups (not blocking), Completed, Home Handoff: Persistent Lumen and Realtime Observer, Realtime observer, Remaining, Repository state, Safety notes

### Community 95 - "Checkpoint: Lumen lifecycle corrected; corpus review pending"
Cohesion: 0.29
Nodes (6): Checkpoint: Lumen lifecycle corrected; corpus review pending, Completed, Current task, Persistent state, Remaining, Workspace state

### Community 96 - "Plan: Lumen Derived Knowledge Graph"
Cohesion: 0.29
Nodes (6): Acceptance criteria, Constraints, Goal, Implementation status, Plan: Lumen Derived Knowledge Graph, Tasks

### Community 99 - "$ref"
Cohesion: 0.20
Nodes (10): items, maxItems, type, items, $ref, items, maxItems, type (+2 more)

### Community 100 - "required"
Cohesion: 0.14
Nodes (14): additionalProperties, required, type, criterionAssessment, participantObservation, assessment_id, criterion_id, observation_id (+6 more)

### Community 101 - "criterion_assessments"
Cohesion: 0.40
Nodes (5): items, maxItems, minItems, type, criterion_assessments

### Community 102 - "properties"
Cohesion: 0.07
Nodes (32): maximum, minimum, type, type, increased_confidence, mixed_or_conditional, morally_acceptable, morally_wrong (+24 more)

### Community 103 - "stringArray"
Cohesion: 0.40
Nodes (5): stringArray, items, maxItems, type, uniqueItems

### Community 110 - "properties"
Cohesion: 0.14
Nodes (14): pattern, type, reportConcession, concession_id, proposition_changed, scope, target_claim_id, type (+6 more)

### Community 112 - "ADR 0006: Readings, Remembered as Gist and Notes"
Cohesion: 0.22
Nodes (8): ADR 0006: Readings, Remembered as Gist and Notes, Alternatives considered, Consequences, Context, Decision, Let the model supply provenance, Store fetched pages as experiences, Trust boundary

## Knowledge Gaps
- **494 isolated node(s):** `$schema`, `$id`, `title`, `type`, `additionalProperties` (+489 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Experiment4TestCase` connect `Experiment4TestCase` to `IdentityApprenticeship`, `SQLiteIdentityRepository`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `SQLiteRepository` connect `SQLiteRepository` to `SQLiteMoralRepository`, `ExperimentRunner`, `Belief`, `._connect`, `olympus/repository.py`, `Mode`, `Experiment2TestCase`, `ObserverTestCase`, `RepositoryTestCase`, `Observer`, `olympus/cli.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `SQLiteIdentityRepository` connect `SQLiteIdentityRepository` to `IdentityApprenticeship`, `execute`, `AgentFixture`, `WakeAgentInstallerTestCase`, `Experiment4TestCase`, `run_turn`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `SQLiteIdentityRepository` (e.g. with `subprocess_model_runner()` and `IdentityApprenticeship`) actually correct?**
  _`SQLiteIdentityRepository` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `SQLiteRepository` (e.g. with `ContextCompiler` and `ExperimentRunner`) actually correct?**
  _`SQLiteRepository` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `IdentityRepositoryError` (e.g. with `main()` and `IdentityApprenticeship`) actually correct?**
  _`IdentityRepositoryError` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `$id`, `title` to the rest of the system?**
  _494 weakly-connected nodes found - possible documentation gaps or missing edges._