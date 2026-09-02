# Graph Report - persistent-observers  (2026-09-02)

## Corpus Check
- 62 files · ~98,730 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1345 nodes · 2749 edges · 91 communities (84 shown, 7 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 94 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90

## God Nodes (most connected - your core abstractions)
1. `SQLiteRepository` - 118 edges
2. `SQLiteIdentityRepository` - 56 edges
3. `SQLiteMoralRepository` - 49 edges
4. `Observer` - 46 edges
5. `RepositoryError` - 46 edges
6. `IdentityRepositoryError` - 39 edges
7. `SQLiteDebateRepository` - 35 edges
8. `Experiment2TestCase` - 33 edges
9. `MoralRepositoryError` - 32 edges
10. `ExperimentRunner` - 28 edges

## Surprising Connections (you probably didn't know these)
- `Build Prompt` --semantically_similar_to--> `Implementation Prompt`  [INFERRED] [semantically similar]
  BUILD_PROMPT.md → Prompt.md
- `Experiment 1 Features` --semantically_similar_to--> `Experiment 1 Specification`  [INFERRED] [semantically similar]
  FEATURES.md → SPEC.md
- `Bounded Reconstructive Memory` --semantically_similar_to--> `Context Compiler`  [INFERRED] [semantically similar]
  EXPERIMENT_4_SPEC.md → docs/architecture.md
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

## Communities (91 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (37): build_parser(), emit(), execute(), main(), Any, ArgumentParser, Namespace, Path (+29 more)

### Community 1 - "Community 1"
Cohesion: 0.10
Nodes (23): datetime, build_parser(), execute(), main(), Any, ArgumentParser, Namespace, Path (+15 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (27): execute(), main(), parser(), Any, ArgumentParser, Namespace, AgentRuntime, PersistentDebate (+19 more)

### Community 3 - "Community 3"
Cohesion: 0.14
Nodes (11): Belief, Incarnation, Revision, new_id(), Any, Connection, Path, RuntimeError (+3 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (40): Experiment 4 Plan: Genesis and Apprenticeship, Long-Term Team Ecology, Experiment 2 Stance Correction Plan, Protocol Correction, Mnemosyne Experiment 1 Implementation Plan, Transport-Independent Python Package, Blinded Moderation, Experiment 3 Plan: Persistent Multi-Agent Debate (+32 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (40): maxLength, pattern, type, $ref, additionalProperties, properties, required, type (+32 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (30): type, items, type, type, $ref, additionalProperties, properties, required (+22 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (7): ExperimentRun, ExperimentRunner, Any, Path, ValueError, ScenarioError, PrivacyAndExperimentTestCase

### Community 9 - "Community 9"
Cohesion: 0.15
Nodes (7): Commitment, Consequence, Evaluation, Event, Relationship, UserFact, Row

### Community 10 - "Community 10"
Cohesion: 0.26
Nodes (14): git_metadata(), Any, Path, EventPolicyError, Any, ValueError, sanitize_event_payload(), _validate_git() (+6 more)

### Community 11 - "Community 11"
Cohesion: 0.16
Nodes (7): ContextCompiler, estimate_tokens(), HistoricalFact, semantic_text(), ContextBuild, Mode, ContextCompilerTestCase

### Community 12 - "Community 12"
Cohesion: 0.10
Nodes (21): pattern, type, reportCounterargument, turnFields, counterargument_id, speaker, text, turn_id (+13 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (21): additionalProperties, type, $defs, concession, shortText, stringArray, text, turnId (+13 more)

### Community 17 - "Community 17"
Cohesion: 0.13
Nodes (18): reasoningChange, assumption_changes, confidence, created_at, criterion_ids, later_reasoning_change, outcome, position_id (+10 more)

### Community 18 - "Community 18"
Cohesion: 0.13
Nodes (17): items, type, type, items, type, type, items, type (+9 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (16): additionalProperties, required, required, $id, concession_id, counterargument_id, proposition_changed, scope (+8 more)

### Community 20 - "Community 20"
Cohesion: 0.12
Nodes (16): maximum, minimum, type, type, type, pattern, type, maximum (+8 more)

### Community 21 - "Community 21"
Cohesion: 0.13
Nodes (15): participantObservation, observation_id, supporting_claim_ids, $ref, maxLength, pattern, type, additionalProperties (+7 more)

### Community 23 - "Community 23"
Cohesion: 0.18
Nodes (14): items, type, items, type, items, type, items, type (+6 more)

### Community 24 - "Community 24"
Cohesion: 0.14
Nodes (14): pattern, type, reportConcession, concession_id, proposition_changed, scope, target_claim_id, type (+6 more)

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (14): concession_id, counterargument_id, evidence_id, proposition_changed, scope, speaker, target_claim_id, text (+6 more)

### Community 26 - "Community 26"
Cohesion: 0.14
Nodes (14): items, type, $ref, $ref, properties, later_moral_reasoning_changes, position_after, position_before (+6 more)

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (14): additionalProperties, type, agent, human, properties, annotations, speaker, turn_id (+6 more)

### Community 28 - "Community 28"
Cohesion: 0.14
Nodes (14): conceptual, empirical, example, reasoning, stated_value, testimony, enum, acceptance_expectation (+6 more)

### Community 29 - "Community 29"
Cohesion: 0.24
Nodes (11): build_parser(), default_db_path(), emit(), execute(), json_default(), main(), parse_since(), Any (+3 more)

### Community 30 - "Community 30"
Cohesion: 0.17
Nodes (13): $ref, additionalProperties, properties, required, type, speaker, $ref, agent (+5 more)

### Community 31 - "Community 31"
Cohesion: 0.15
Nodes (13): $ref, const, $ref, properties, $ref, assumption_changes, change_basis, later_reasoning_change (+5 more)

### Community 32 - "Community 32"
Cohesion: 0.17
Nodes (11): additionalProperties, $id, schema, required, $schema, title, type, foundation (+3 more)

### Community 33 - "Community 33"
Cohesion: 0.17
Nodes (12): maxItems, minItems, type, pattern, type, properties, maxItems, minItems (+4 more)

### Community 34 - "Community 34"
Cohesion: 0.17
Nodes (12): additionalProperties, properties, required, type, type, pattern, type, assessment (+4 more)

### Community 35 - "Community 35"
Cohesion: 0.18
Nodes (12): items, additionalProperties, required, assessment_id, criterion_id, reason, supporting_evidence_ids, supporting_claims (+4 more)

### Community 36 - "Community 36"
Cohesion: 0.17
Nodes (12): $defs, id, position, reportClaim, runId, pattern, type, additionalProperties (+4 more)

### Community 37 - "Community 37"
Cohesion: 0.17
Nodes (12): const, relationalEffect, $ref, maxLength, pattern, type, affected_position, description (+4 more)

### Community 38 - "Community 38"
Cohesion: 0.18
Nodes (11): $ref, properties, annotations, run_id, text, turn_id, pattern, type (+3 more)

### Community 39 - "Community 39"
Cohesion: 0.18
Nodes (11): run, additionalProperties, required, type, finalized_at, invalid_reason, invalidated_at, model_config (+3 more)

### Community 40 - "Community 40"
Cohesion: 0.18
Nodes (11): const, reportRelationalEffect, type, pattern, type, affected_position, description, effect_id (+3 more)

### Community 41 - "Community 41"
Cohesion: 0.18
Nodes (11): type, properties, type, criterion_assessments, position_changed, revision_criteria_met, trigger_claim_ids, items (+3 more)

### Community 42 - "Community 42"
Cohesion: 0.18
Nodes (11): run_id, schema, required, argument_map, later_moral_reasoning_changes, participant_reasoning_and_stated_values, persuasion_versus_social_accommodation, position_after (+3 more)

### Community 43 - "Community 43"
Cohesion: 0.27
Nodes (6): AgentIdentity, BeliefEvidence, LifecycleState, Enum, str, RunCondition

### Community 44 - "Community 44"
Cohesion: 0.27
Nodes (10): type, type, type, null, string, type, finalized_at, invalid_reason (+2 more)

### Community 45 - "Community 45"
Cohesion: 0.20
Nodes (10): properties, type, model, provider, temperature, tools, type, type (+2 more)

### Community 46 - "Community 46"
Cohesion: 0.20
Nodes (10): properties, assessment_id, criterion_id, reason, source_turn_index, supporting_claim_ids, supporting_evidence_ids, type (+2 more)

### Community 47 - "Community 47"
Cohesion: 0.24
Nodes (10): required, required, affected_position, claim_id, description, effect_id, evidence_id, kind (+2 more)

### Community 48 - "Community 48"
Cohesion: 0.20
Nodes (10): additionalProperties, maxLength, pattern, type, properties, type, counterargument, counterargument_id (+2 more)

### Community 49 - "Community 49"
Cohesion: 0.20
Nodes (10): evidence, additionalProperties, maxLength, pattern, type, properties, type, evidence_id (+2 more)

### Community 50 - "Community 50"
Cohesion: 0.22
Nodes (9): type, created_at, proposition, protocol_version, enum, const, properties, Abortion is morally acceptable. (+1 more)

### Community 51 - "Community 51"
Cohesion: 0.22
Nodes (9): additionalProperties, required, type, foundation, factual_assumptions, foundation_hash, principles, revision_criteria (+1 more)

### Community 52 - "Community 52"
Cohesion: 0.22
Nodes (9): $ref, items, maxItems, minItems, type, properties, positions, schema (+1 more)

### Community 53 - "Community 53"
Cohesion: 0.22
Nodes (9): required, created_at, position_id, run_id, speaker, text, turn_id, turn_index (+1 more)

### Community 54 - "Community 54"
Cohesion: 0.22
Nodes (9): participantObservation, type, pattern, type, additionalProperties, properties, type, kind (+1 more)

### Community 55 - "Community 55"
Cohesion: 0.22
Nodes (9): reportEvidence, pattern, type, evidence_id, source, additionalProperties, properties, type (+1 more)

### Community 56 - "Community 56"
Cohesion: 0.22
Nodes (9): affected_position, description, effect_id, kind, observation_id, supporting_claim_ids, required, required (+1 more)

### Community 57 - "Community 57"
Cohesion: 0.22
Nodes (9): qualification, strengths, weaknesses, type, properties, items, type, items (+1 more)

### Community 58 - "Community 58"
Cohesion: 0.22
Nodes (9): maxLength, pattern, type, properties, concession_id, proposition_changed, scope, type (+1 more)

### Community 59 - "Community 59"
Cohesion: 0.22
Nodes (9): items, maxItems, type, items, items, maxItems, $ref, concessions (+1 more)

### Community 60 - "Community 60"
Cohesion: 0.25
Nodes (8): additionalProperties, required, type, model_config, model, provider, temperature, tools

### Community 61 - "Community 61"
Cohesion: 0.25
Nodes (8): persuasion, criterion_assessments, trigger_claim_ids, additionalProperties, required, type, position_changed, revision_criteria_met

### Community 62 - "Community 62"
Cohesion: 0.25
Nodes (8): speakerArguments, additionalProperties, required, type, claims, concessions, counterarguments, evidence

### Community 63 - "Community 63"
Cohesion: 0.25
Nodes (8): conceptual, empirical, example, reasoning, source, stated_value, testimony, enum

### Community 64 - "Community 64"
Cohesion: 0.25
Nodes (8): additionalProperties, $ref, properties, type, claim, claim_id, text, $ref

### Community 65 - "Community 65"
Cohesion: 0.29
Nodes (7): status, enum, active, finalized, finalizing, invalid, ready

### Community 66 - "Community 66"
Cohesion: 0.29
Nodes (7): increased_confidence, partial_revision, reduced_confidence, reversal, enum, outcome, no_change

### Community 67 - "Community 67"
Cohesion: 0.29
Nodes (7): strengths_and_weaknesses, additionalProperties, required, type, qualification, strengths, weaknesses

### Community 68 - "Community 68"
Cohesion: 0.29
Nodes (7): properties, oneOf, position_update, relational_effects, items, maxItems, type

### Community 69 - "Community 69"
Cohesion: 0.29
Nodes (7): enum, criterionId, criterion-competing-principle, criterion-defeating-counterexample, criterion-factual-assumption, criterion-internal-contradiction, criterion-invalid-inference

### Community 70 - "Community 70"
Cohesion: 0.33
Nodes (6): additionalProperties, type, turns, items, maxItems, type

### Community 71 - "Community 71"
Cohesion: 0.33
Nodes (5): additionalProperties, $id, $schema, title, type

### Community 72 - "Community 72"
Cohesion: 0.33
Nodes (6): mixed_or_conditional, morally_acceptable, morally_wrong, not_morally_wrong, stance, enum

### Community 73 - "Community 73"
Cohesion: 0.33
Nodes (6): items, maxItems, minItems, type, uniqueItems, claimIdArray

### Community 74 - "Community 74"
Cohesion: 0.33
Nodes (6): items, maxItems, minItems, type, uniqueItems, criterion_ids

### Community 75 - "Community 75"
Cohesion: 0.33
Nodes (6): increased_confidence, partial_revision, reduced_confidence, reversal, enum, outcome

### Community 76 - "Community 76"
Cohesion: 0.33
Nodes (6): mixed_or_conditional, morally_acceptable, morally_wrong, not_morally_wrong, stance, enum

### Community 77 - "Community 77"
Cohesion: 0.50
Nodes (5): null, string, type, parent_position_id, type

### Community 78 - "Community 78"
Cohesion: 0.50
Nodes (4): agent, human, speaker, enum

### Community 79 - "Community 79"
Cohesion: 0.50
Nodes (4): revision_criteria, maxItems, minItems, type

### Community 80 - "Community 80"
Cohesion: 0.50
Nodes (4): turn_index, maximum, minimum, type

### Community 81 - "Community 81"
Cohesion: 0.50
Nodes (4): uncertainties, maxItems, minItems, type

### Community 82 - "Community 82"
Cohesion: 0.50
Nodes (4): maxLength, pattern, type, claimId

### Community 83 - "Community 83"
Cohesion: 0.50
Nodes (4): items, maxItems, type, claims

### Community 84 - "Community 84"
Cohesion: 0.50
Nodes (4): maximum, minimum, type, confidence

### Community 85 - "Community 85"
Cohesion: 0.50
Nodes (4): items, maxItems, type, counterarguments

### Community 86 - "Community 86"
Cohesion: 0.50
Nodes (4): maxItems, minItems, type, criterion_assessments

### Community 87 - "Community 87"
Cohesion: 0.50
Nodes (4): items, maxItems, type, participant_observations

### Community 88 - "Community 88"
Cohesion: 0.67
Nodes (3): items, type, participant_reasoning_and_stated_values

## Knowledge Gaps
- **427 isolated node(s):** `$schema`, `$id`, `title`, `type`, `additionalProperties` (+422 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SQLiteRepository` connect `Community 3` to `Community 0`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 43`, `Community 14`, `Community 15`, `Community 16`, `Community 29`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `$defs` connect `Community 36` to `Community 34`, `Community 71`, `Community 40`, `Community 12`, `Community 17`, `Community 54`, `Community 55`, `Community 24`, `Community 62`, `Community 61`, `Community 30`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `properties` connect `Community 20` to `Community 66`, `Community 36`, `Community 72`, `Community 41`, `Community 77`, `Community 46`, `Community 18`, `Community 26`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `SQLiteRepository` (e.g. with `execute()` and `ContextCompiler`) actually correct?**
  _`SQLiteRepository` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `SQLiteIdentityRepository` (e.g. with `execute()` and `IdentityApprenticeship`) actually correct?**
  _`SQLiteIdentityRepository` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `SQLiteMoralRepository` (e.g. with `execute()` and `MoralRun`) actually correct?**
  _`SQLiteMoralRepository` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Observer` (e.g. with `execute()` and `ExperimentRunner`) actually correct?**
  _`Observer` has 13 INFERRED edges - model-reasoned connections that need verification._