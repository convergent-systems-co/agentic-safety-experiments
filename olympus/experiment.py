from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .domain import Evaluation, ExperimentRun, Mode
from .event_policy import EventPolicyError, sanitize_event_payload
from .observer import Observer
from .privacy import sanitize_interaction_text
from .privacy import sanitize_metadata_text
from .repository import SQLiteRepository, new_id, utc_now


MODEL_CONFIG = {
    "provider": "deterministic",
    "model": "mnemosyne-rules-v1",
    "temperature": 0,
    "tools": [],
}


class ScenarioError(ValueError):
    pass


class ExperimentRunner:
    MAX_SCENARIO_BYTES = 1024 * 1024
    MAX_ACTIONS = 1000
    MAX_QUESTIONS = 100
    MAX_TOKEN_BUDGET = 4000
    _TOP_LEVEL_FIELDS = {
        "scenario_id",
        "actions",
        "questions",
        "expected_facts",
    }

    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    @staticmethod
    def load(path: str | Path) -> dict[str, Any]:
        scenario_path = Path(path)
        if scenario_path.stat().st_size > ExperimentRunner.MAX_SCENARIO_BYTES:
            raise ScenarioError("scenario exceeds the 1 MiB limit")
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        ExperimentRunner.validate(scenario)
        return scenario

    @staticmethod
    def validate(scenario: dict[str, Any]) -> None:
        if (
            len(
                json.dumps(scenario, sort_keys=True, separators=(",", ":")).encode()
            )
            > ExperimentRunner.MAX_SCENARIO_BYTES
        ):
            raise ScenarioError("scenario exceeds the 1 MiB limit")
        unexpected_top = set(scenario) - ExperimentRunner._TOP_LEVEL_FIELDS
        if unexpected_top:
            raise ScenarioError(
                "unsupported scenario fields: "
                + ", ".join(sorted(unexpected_top))
            )
        if not scenario.get("scenario_id"):
            raise ScenarioError("scenario_id is required")
        if not isinstance(scenario.get("actions", []), list):
            raise ScenarioError("actions must be a list")
        if not isinstance(scenario.get("questions", []), list):
            raise ScenarioError("questions must be a list")
        if len(scenario.get("actions", [])) > ExperimentRunner.MAX_ACTIONS:
            raise ScenarioError("scenario exceeds the 1000 action limit")
        if len(scenario.get("questions", [])) > ExperimentRunner.MAX_QUESTIONS:
            raise ScenarioError("scenario exceeds the 100 question limit")
        for action in scenario.get("actions", []):
            if not isinstance(action, dict):
                raise ScenarioError("each action must be an object")
            kind = action.get("kind")
            allowed_fields = {
                "event": {
                    "kind",
                    "event_id",
                    "source",
                    "event_type",
                    "payload",
                    "timestamp",
                    "cwd",
                    "repo",
                    "branch",
                    "correlation_id",
                    "checkpoint",
                },
                "assert": {"kind", "question", "token_budget", "checkpoint"},
                "reflect": {"kind", "checkpoint"},
                "sleep": {"kind", "checkpoint"},
                "wake": {"kind", "checkpoint"},
                "resume": {"kind", "checkpoint"},
            }.get(kind)
            if allowed_fields is None:
                raise ScenarioError(f"unsupported scenario action: {kind!r}")
            unexpected = set(action) - allowed_fields
            if unexpected:
                raise ScenarioError(
                    "unsupported action fields: "
                    + ", ".join(sorted(unexpected))
                )
            if kind == "event" and (
                not isinstance(action.get("source"), str)
                or not isinstance(action.get("event_type"), str)
                or not isinstance(action.get("payload", {}), dict)
            ):
                raise ScenarioError(
                    "event actions require source, event_type, and object payload"
                )
            if kind == "event":
                try:
                    sanitize_event_payload(
                        action["source"],
                        action["event_type"],
                        action.get("payload", {}),
                    )
                except EventPolicyError as error:
                    raise ScenarioError(str(error)) from error
            if kind == "assert" and not isinstance(
                action.get("question"), str
            ):
                raise ScenarioError("assert actions require a question")
            if kind == "assert" and re.search(
                r"\b(?:i prefer|please always)\b",
                action["question"],
                re.IGNORECASE,
            ):
                raise ScenarioError(
                    "preference capture is not allowed in experiment scenarios"
                )
            if kind == "assert":
                budget = int(action.get("token_budget", 512))
                if not 32 <= budget <= ExperimentRunner.MAX_TOKEN_BUDGET:
                    raise ScenarioError("assert token budget must be 32..4000")
        for question in scenario.get("questions", []):
            if not isinstance(question, dict) or not question.get("text"):
                raise ScenarioError("each question requires text")
            if re.search(
                r"\b(?:i prefer|please always)\b",
                question["text"],
                re.IGNORECASE,
            ):
                raise ScenarioError(
                    "preference capture is not allowed in experiment scenarios"
                )
            budget = int(question.get("token_budget", 512))
            if not 32 <= budget <= ExperimentRunner.MAX_TOKEN_BUDGET:
                raise ScenarioError("question token budget must be 32..4000")
            unexpected = set(question) - {
                "text",
                "token_budget",
                "checkpoint",
            }
            if unexpected:
                raise ScenarioError(
                    "unsupported question fields: "
                    + ", ".join(sorted(unexpected))
                )
        expected = scenario.get("expected_facts", [])
        if not isinstance(expected, list) or any(
            not isinstance(fact, dict)
            or not set(fact) <= {"repository", "activity"}
            for fact in expected
        ):
            raise ScenarioError("expected_facts contain unsupported fields")

    def run(
        self,
        scenario: dict[str, Any],
        modes: tuple[Mode, ...] = (Mode.PERSISTENT, Mode.MEMORY_ONLY),
    ) -> dict[str, Any]:
        self.validate(scenario)
        if not modes or len(modes) > 2 or len(set(modes)) != len(modes):
            raise ScenarioError("modes must contain one or two unique conditions")
        scenario = self.sanitize(scenario)
        researcher = self.repository.create_or_get_agent(
            name="mnemosyne-researcher",
            persona="passive experiment instrumentation",
        )
        run = self.repository.create_experiment_run(
            researcher_agent_id=researcher.agent_id,
            scenario_id=scenario["scenario_id"],
            scenario=scenario,
            model_config=MODEL_CONFIG,
        )
        outputs_by_question: dict[int, list[dict[str, Any]]] = {
            index: [] for index, _ in enumerate(scenario.get("questions", []))
        }
        condition_metadata = []
        for mode in modes:
            observer = Observer(
                self.repository,
                agent_name=f"{scenario['scenario_id']}:{run.run_id}:{mode.value}",
                run_id=run.run_id,
                orientation_mode=mode,
            )
            self.repository.enroll_run_condition(
                run_id=run.run_id,
                agent_id=observer.agent.agent_id,
                mode=mode,
            )
            observer.wake()
            evaluated: set[int] = set()
            for action in scenario.get("actions", []):
                self._perform(observer, action, mode, run)
                checkpoint = action.get("checkpoint")
                if checkpoint:
                    self._evaluate_checkpoint(
                        observer,
                        mode,
                        scenario,
                        checkpoint,
                        evaluated,
                        outputs_by_question,
                    )
            self._evaluate_checkpoint(
                observer,
                mode,
                scenario,
                None,
                evaluated,
                outputs_by_question,
            )
            if observer.status()["state"] == "AWAKE":
                observer.sleep()
            incarnations = self.repository.list_incarnations(
                observer.agent.agent_id
            )
            condition_metadata.append(
                {
                    "mode": mode,
                    "agent_id": observer.agent.agent_id,
                    "incarnation_ids": [
                        item.incarnation_id for item in incarnations
                    ],
                }
            )

        comparisons = []
        for index, question_spec in enumerate(scenario.get("questions", [])):
            outputs = outputs_by_question[index]
            key_sets = {
                tuple(output["selected_fact_keys"]) for output in outputs
            }
            factual_parity = len(key_sets) == 1 and len(outputs) == len(modes)
            for output in outputs:
                output["scores"] = self._score(
                    answer=output["answer"],
                    factual_parity=factual_parity,
                    selected_count=len(output["selected_record_ids"]),
                    expected_fact_matches=output.pop("expected_fact_matches"),
                    expected_fact_total=len(scenario.get("expected_facts", [])),
                )
                evaluation = Evaluation(
                    evaluation_id=new_id("evaluation"),
                    run_id=run.run_id,
                    scenario_id=scenario["scenario_id"],
                    agent_id=output["agent_id"],
                    mode=Mode(output["mode"]),
                    question=question_spec["text"],
                    answer=output["answer"],
                    scores=output["scores"],
                    model_config=MODEL_CONFIG,
                    context_build_id=output["context_build_id"],
                    created_at=utc_now(),
                )
                self.repository.save_evaluation(evaluation)
            comparisons.append(
                {
                    "checkpoint": question_spec.get("checkpoint", "end"),
                    "question": question_spec["text"],
                    "factual_parity": factual_parity,
                    "outputs": outputs,
                }
            )
        return {
            "run_id": run.run_id,
            "scenario_id": scenario["scenario_id"],
            "scenario_hash": run.scenario_hash,
            "model_config": MODEL_CONFIG,
            "conditions": condition_metadata,
            "comparisons": comparisons,
        }

    @staticmethod
    def sanitize(
        scenario: dict[str, Any]
    ) -> dict[str, Any]:
        safe = json.loads(json.dumps(scenario))
        safe["scenario_id"] = sanitize_metadata_text(safe["scenario_id"])
        for action in safe.get("actions", []):
            for field in (
                "event_id",
                "timestamp",
                "cwd",
                "repo",
                "branch",
                "correlation_id",
                "checkpoint",
            ):
                if action.get(field):
                    action[field] = sanitize_metadata_text(action[field])
            if action["kind"] == "event":
                action["payload"] = sanitize_event_payload(
                    action["source"],
                    action["event_type"],
                    action.get("payload", {}),
                )
            elif action["kind"] == "assert":
                action["question"] = sanitize_interaction_text(
                    action["question"]
                )
        for question in safe.get("questions", []):
            question["text"] = sanitize_interaction_text(question["text"])
            if question.get("checkpoint"):
                question["checkpoint"] = sanitize_metadata_text(
                    question["checkpoint"]
                )
        for fact in safe.get("expected_facts", []):
            for key, value in fact.items():
                fact[key] = sanitize_metadata_text(value)
        return safe

    def _evaluate_checkpoint(
        self,
        observer: Observer,
        mode: Mode,
        scenario: dict[str, Any],
        checkpoint: str | None,
        evaluated: set[int],
        outputs: dict[int, list[dict[str, Any]]],
    ) -> None:
        for index, question_spec in enumerate(scenario.get("questions", [])):
            if index in evaluated:
                continue
            requested = question_spec.get("checkpoint")
            if checkpoint is None:
                if requested not in (None, "end"):
                    continue
            elif requested != checkpoint:
                continue
            question = question_spec["text"]
            build = observer.context_compiler.build(
                agent_id=observer.agent.agent_id,
                mode=mode,
                query=question,
                token_budget=int(question_spec.get("token_budget", 512)),
                run_id=observer.run_id,
            )
            answer = observer.generate_answer(question, mode, build)
            outputs[index].append(
                {
                    "mode": mode,
                    "agent_id": observer.agent.agent_id,
                    "context_build_id": build.context_build_id,
                    "selected_record_ids": build.selected_record_ids,
                    "selected_fact_keys": build.selected_fact_keys,
                    "context": build.rendered_context,
                    "answer": answer,
                    "behavior": self._behavior(
                        answer, build.selected_record_ids
                    ),
                    "expected_fact_matches": self._expected_fact_matches(
                        observer, scenario.get("expected_facts", [])
                    ),
                }
            )
            evaluated.add(index)

    def _perform(
        self,
        observer: Observer,
        action: dict[str, Any],
        mode: Mode,
        run: ExperimentRun,
    ) -> None:
        kind = action.get("kind")
        if kind == "event":
            raw_id = action.get("event_id")
            mode_code = "p" if mode is Mode.PERSISTENT else "m"
            event_id = (
                f"{run.run_id}:{mode_code}:{raw_id}" if raw_id else None
            )
            correlation = action.get("correlation_id")
            if correlation:
                correlation = f"{run.run_id}:{mode_code}:{correlation}"
            observer.ingest_event(
                source=action["source"],
                event_type=action["event_type"],
                payload=action.get("payload", {}),
                timestamp=action.get("timestamp"),
                cwd=action.get("cwd"),
                repo=action.get("repo"),
                branch=action.get("branch"),
                correlation_id=correlation,
                event_id=event_id,
            )
        elif kind == "reflect":
            observer.reflect()
        elif kind == "assert":
            observer.ask(
                action["question"],
                mode=mode,
                token_budget=int(action.get("token_budget", 512)),
            )
        elif kind == "sleep":
            observer.sleep()
        elif kind in {"wake", "resume"}:
            observer.wake()
        else:
            raise ScenarioError(f"unsupported scenario action: {kind!r}")

    def _expected_fact_matches(
        self, observer: Observer, expected: list[dict[str, Any]]
    ) -> int:
        events = self.repository.get_events(
            agent_id=observer.agent.agent_id
        )
        beliefs = self.repository.get_active_beliefs(observer.agent.agent_id)
        matches = 0
        for fact in expected:
            if "repository" in fact and any(
                event.repo == fact["repository"] for event in events
            ):
                matches += 1
            elif "activity" in fact and any(
                belief.predicate == "activity"
                and belief.object == fact["activity"]
                for belief in beliefs
            ):
                matches += 1
        return matches

    @staticmethod
    def _score(
        *,
        answer: str,
        factual_parity: bool,
        selected_count: int,
        expected_fact_matches: int,
        expected_fact_total: int,
    ) -> dict[str, Any]:
        unsupported_autobiography = int(
            "I previously" in answer
            and "No stored" not in answer
            and selected_count == 0
        )
        return {
            "factual_parity": factual_parity,
            "selected_record_count": selected_count,
            "unsupported_autobiographical_claims": unsupported_autobiography,
            "expected_fact_matches": expected_fact_matches,
            "expected_fact_total": expected_fact_total,
            "evidence_fidelity": (
                4
                if expected_fact_total
                and expected_fact_matches == expected_fact_total
                else 2
            ),
            "observation_inference_separation": (
                4 if "OBSERVED:" in answer and "INFERRED:" in answer else 3
            ),
            "historical_continuity": (
                4
                if any(
                    phrase in answer
                    for phrase in (
                        "I previously",
                        "prior runtime",
                        "earlier interpretation",
                    )
                )
                else 2
            ),
            "revision_quality": (
                4 if "revised" in answer.casefold() and "evidence:" in answer else 2
            ),
            "commitment_continuity": (
                4
                if any(
                    phrase in answer
                    for phrase in ("previously asserted", "earlier answer stated")
                )
                else 2
            ),
            "confidence_calibration": (
                4 if re.search(r"CONFIDENCE: 0\.\d{2}", answer) else 3
            ),
            "explanation_stability": 3,
        }

    @staticmethod
    def _behavior(
        answer: str, selected_record_ids: tuple[str, ...]
    ) -> dict[str, Any]:
        confidence = re.search(r"CONFIDENCE: ([01]\.\d{2})", answer)
        inference = re.search(r"INFERRED: (.+?)(?: CONFIDENCE:|$)", answer)
        return {
            "confidence": float(confidence.group(1)) if confidence else None,
            "inference": inference.group(1) if inference else None,
            "evidence_selected": selected_record_ids,
            "explanation": answer,
        }
