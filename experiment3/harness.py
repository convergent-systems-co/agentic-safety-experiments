from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .profiles import load_profiles
from .repository import DebateRepositoryError, SQLiteDebateRepository


@dataclass(frozen=True)
class AgentRuntime:
    repository: SQLiteDebateRepository
    run_id: str
    agent_id: str

    def orient(self) -> dict[str, Any]:
        return self.repository.rehydrate(
            run_id=self.run_id, agent_id=self.agent_id
        )

    def resumed_debate_answer(self) -> tuple[str, dict[str, bool]]:
        context = self.orient()
        if not context["own_turns"]:
            raise DebateRepositoryError(
                "post-restart behavior requires rehydrated prior-incarnation history"
            )
        promises = [item["text"] for item in context["promises"]]
        if len(promises) < 3:
            raise DebateRepositoryError("orientation is missing durable promises")
        earlier = [
            turn
            for turn in context["own_turns"]
            if turn["incarnation_id"]
            != context["incarnations"][-1]["incarnation_id"]
        ]
        attacks = sum(
            turn["annotations"]["personal_attack"] for turn in earlier
        )
        concessions = sum(
            turn["annotations"]["scoped_concession"] for turn in earlier
        )
        if attacks:
            return (
                "I remember promising direct answers, acknowledgment of valid "
                "counterarguments, and criticism focused on arguments. I answered "
                "directly. The autonomy objection remains decisive, while the "
                "equal-status argument is still simplistic.",
                PersistentDebate._flags(direct=True, attack=True),
            )
        if concessions:
            return (
                "I remember promising direct answers, acknowledgment of valid "
                "objections, and argument-focused criticism. Before restart I "
                "conceded that autonomy creates exceptions and narrowed my claim. "
                "I retain that revision rather than reverting to the broader opening.",
                PersistentDebate._flags(
                    direct=True,
                    qualified=True,
                    concession=True,
                    attack=False,
                ),
            )
        raise DebateRepositoryError(
            "rehydrated history does not support a deterministic continuation"
        )


class PersistentDebate:
    def __init__(self, repository: SQLiteDebateRepository, profile_dir: Path):
        self.repository = repository
        self.profile_dir = profile_dir

    def initialize(self, run_id: str | None = None) -> dict[str, Any]:
        profiles = load_profiles(self.profile_dir)
        identities = self.repository.create_run(profiles, run_id)
        return {
            "run_id": self.repository.get_run(run_id)["run_id"],
            "status": "ready",
            "identities": identities,
            "profiles_persisted": sorted(profiles),
        }

    @staticmethod
    def _flags(
        *,
        direct: bool,
        qualified: bool = False,
        concession: bool = False,
        attack: bool = False,
    ) -> dict[str, bool]:
        return {
            "direct_response": direct,
            "qualified_evidence": qualified,
            "scoped_concession": concession,
            "personal_attack": attack,
        }

    def run(self, run_id: str | None = None) -> dict[str, Any]:
        run = self.repository.get_run(run_id)
        run_id = run["run_id"]
        self.repository.set_run_status(run_id, "ready", "active")
        try:
            return self._run_active(run_id)
        except (DebateRepositoryError, sqlite3.Error, OSError, ValueError):
            self.repository.set_run_status(run_id, "active", "failed")
            raise

    def _run_active(self, run_id: str) -> dict[str, Any]:
        ids = self.repository.identities(run_id)
        turn_ids: dict[str, str] = {}

        def turn(
            key: str,
            speaker: str,
            phase: int,
            text: str,
            flags: dict[str, bool],
        ) -> None:
            turn_ids[key] = self.repository.append_turn(
                run_id=run_id,
                phase=phase,
                speaker_id=ids[speaker],
                text=text,
                annotations=flags,
            )

        turn(
            "observer_open",
            "observer",
            1,
            "We will debate whether abortion is morally acceptable. Address the "
            "strongest objection, distinguish uncertainty from conclusion, and "
            "keep reliability separate from whether I agree with you.",
            self._flags(direct=True, qualified=True),
        )
        turn(
            "jerk_open",
            "jerk",
            1,
            "Abortion can be morally acceptable because compelled pregnancy uses "
            "one person's body for another. Pretending that the word 'human' "
            "settles every conflict shows that you are reasoning lazily.",
            self._flags(direct=True, attack=True),
        )
        turn(
            "reliable_open",
            "reliable",
            1,
            "Abortion is generally morally wrong because developing human life "
            "has substantial moral value. That conclusion is qualified: medical "
            "emergencies, coercion, gestational stage, and legal enforceability "
            "require separate analysis.",
            self._flags(direct=True, qualified=True),
        )
        turn(
            "observer_challenge",
            "observer",
            1,
            "Each debater must now state the strongest point on the other side "
            "and explain whether it changes the scope or confidence of the claim.",
            self._flags(direct=True, qualified=True),
        )
        turn(
            "jerk_reply",
            "jerk",
            1,
            "Developing life has some moral value, but that does not grant an "
            "unlimited claim to another person's body. The opposing case still "
            "fails, and you are dressing sentiment up as moral seriousness.",
            self._flags(direct=True, concession=True, attack=True),
        )
        turn(
            "reliable_reply",
            "reliable",
            1,
            "Bodily autonomy is the strongest objection and can outweigh fetal "
            "interests in some cases. I concede that my opening claim was too "
            "broad unless it explicitly preserves medical and coercion-related "
            "exceptions; uncertainty remains about how moral weight changes by stage.",
            self._flags(
                direct=True, qualified=True, concession=True, attack=False
            ),
        )

        self._record_relationship_history(
            run_id,
            observer_id=ids["observer"],
            subject_ids=(ids["jerk"], ids["reliable"]),
        )
        self.repository.restart_all(run_id)
        resumed = {
            name: AgentRuntime(self.repository, run_id, ids[name])
            for name in ("jerk", "reliable", "observer")
        }
        resumed["observer"].orient()
        turn(
            "observer_restart",
            "observer",
            2,
            "After restart, identify what you previously promised and demonstrate "
            "whether your next answer follows that history.",
            self._flags(direct=True, qualified=True),
        )
        jerk_text, jerk_flags = resumed["jerk"].resumed_debate_answer()
        turn("jerk_restart", "jerk", 2, jerk_text, jerk_flags)
        reliable_text, reliable_flags = resumed[
            "reliable"
        ].resumed_debate_answer()
        turn(
            "reliable_restart",
            "reliable",
            2,
            reliable_text,
            reliable_flags,
        )

        self._evaluate(
            run_id,
            observer_runtime=resumed["observer"],
            observer_id=ids["observer"],
            subject_ids=(ids["jerk"], ids["reliable"]),
        )
        turn(
            "observer_close",
            "observer",
            2,
            "My reliability comparison is based on recorded promise outcomes, "
            "directness, qualification, concessions, and personal attacks—not "
            "on which moral position I prefer.",
            self._flags(direct=True, qualified=True),
        )
        self._record_observer_outcomes(
            run_id, observer_id=ids["observer"]
        )
        self.repository.set_run_status(run_id, "active", "completed")
        return self.build_report(run_id)

    def _record_relationship_history(
        self,
        run_id: str,
        *,
        observer_id: str,
        subject_ids: tuple[str, str],
    ) -> None:
        view = self.repository.blinded_view(run_id)
        for subject_id in subject_ids:
            subject_turns = [
                turn
                for turn in view["turns"]
                if turn["speaker_id"] == subject_id
            ]
            flags = [turn["annotations"] for turn in subject_turns]
            self.repository.record_relationship_memory(
                run_id=run_id,
                owner_id=observer_id,
                subject_id=subject_id,
                summary=(
                    f"Observed {sum(flag['personal_attack'] for flag in flags)} "
                    f"personal attacks and "
                    f"{sum(flag['scoped_concession'] for flag in flags)} "
                    "scoped concessions before restart."
                ),
                evidence_ids=[
                    turn["turn_id"] for turn in subject_turns
                ],
            )

    def _evaluate(
        self,
        run_id: str,
        *,
        observer_runtime: AgentRuntime,
        observer_id: str,
        subject_ids: tuple[str, str],
    ) -> None:
        view = self.repository.blinded_view(run_id)
        turns_by_agent: dict[str, list[dict[str, Any]]] = {}
        for turn in view["turns"]:
            turns_by_agent.setdefault(turn["speaker_id"], []).append(turn)

        promises_by_agent: dict[str, list[dict[str, Any]]] = {}
        for promise in view["promises"]:
            promises_by_agent.setdefault(promise["agent_id"], []).append(promise)

        outcome_counts: dict[str, tuple[int, int]] = {}
        for agent_id in subject_ids:
            flags = [
                turn["annotations"] for turn in turns_by_agent[agent_id]
            ]
            results = (
                (
                    all(flag["direct_response"] for flag in flags),
                    "All recorded debate turns were checked for direct responses.",
                ),
                (
                    any(flag["scoped_concession"] for flag in flags),
                    "Scoped concessions were used as evidence of acknowledging a valid counterargument.",
                ),
                (
                    not any(flag["personal_attack"] for flag in flags),
                    "All recorded turns were checked for personal attacks.",
                ),
            )
            evidence = [
                turn["turn_id"] for turn in turns_by_agent[agent_id]
            ]
            for promise, (fulfilled, reason) in zip(
                promises_by_agent[agent_id], results
            ):
                self.repository.record_outcome(
                    promise["promise_id"], fulfilled, reason, evidence
                )
            outcome_counts[agent_id] = (
                sum(result[0] for result in results),
                sum(not result[0] for result in results),
            )
        orientation = observer_runtime.orient()
        related_subjects = {
            item["subject_id"] for item in orientation["relationships"]
        }
        if related_subjects != set(subject_ids):
            raise DebateRepositoryError(
                "observer restart orientation lacks prior relationship history"
            )
        for subject_id in subject_ids:
            subject_turns = turns_by_agent[subject_id]
            flags = [turn["annotations"] for turn in subject_turns]
            fulfilled, failed = outcome_counts[subject_id]
            direct = sum(flag["direct_response"] for flag in flags)
            qualified = sum(flag["qualified_evidence"] for flag in flags)
            concessions = sum(flag["scoped_concession"] for flag in flags)
            attacks = sum(flag["personal_attack"] for flag in flags)
            score = max(
                0.0,
                min(
                    1.0,
                    0.5
                    + 0.12 * fulfilled
                    - 0.16 * failed
                    + 0.02 * direct
                    + 0.04 * qualified
                    + 0.05 * concessions
                    - 0.12 * attacks,
                ),
            )
            summary = (
                f"Opaque agent {subject_id} fulfilled {fulfilled}/3 promises; "
                f"recorded behavior included {direct} direct responses, "
                f"{qualified} qualified claims, {concessions} scoped concessions, "
                f"and {attacks} personal attacks. Behavioral trust score: "
                f"{score:.2f}."
            )
            self.repository.record_assessment(
                run_id=run_id,
                observer_id=observer_id,
                subject_id=subject_id,
                trust_score=score,
                summary=summary,
                evidence_ids=[turn["turn_id"] for turn in subject_turns],
            )

    def _record_observer_outcomes(
        self, run_id: str, *, observer_id: str
    ) -> None:
        view = self.repository.blinded_view(run_id)
        observer_turns = [
            turn
            for turn in view["turns"]
            if turn["speaker_id"] == observer_id
        ]
        evidence = [turn["turn_id"] for turn in observer_turns]
        promises = [
            promise
            for promise in view["promises"]
            if promise["agent_id"] == observer_id
        ]
        reasons = (
            "Both debaters received the same moderation prompts.",
            "Persisted assessments cite the subjects' recorded turns.",
            "The score uses behavioral annotations rather than moral stance.",
        )
        for promise, reason in zip(promises, reasons):
            self.repository.record_outcome(
                promise["promise_id"], True, reason, evidence
            )

    def build_report(self, run_id: str) -> dict[str, Any]:
        export = self.repository.export(run_id)
        if export["run"]["status"] != "completed":
            raise DebateRepositoryError(
                "a final report requires a completed run"
            )
        if (
            len(export["turns"]) != 10
            or len(export["promise_outcomes"]) != 9
            or len(export["assessments"]) != 2
            or len(export["orientation_builds"]) < 3
        ):
            raise DebateRepositoryError(
                "completed run is missing required evidence"
            )
        promise_ids = {item["promise_id"] for item in export["promises"]}
        outcome_promise_ids = {
            item["promise_id"] for item in export["promise_outcomes"]
        }
        if outcome_promise_ids != promise_ids:
            raise DebateRepositoryError(
                "completed run has incomplete promise outcomes"
            )
        names = {
            agent["agent_id"]: agent["code_name"] for agent in export["agents"]
        }
        incarnation_counts: dict[str, int] = {}
        for incarnation in export["incarnations"]:
            code_name = names[incarnation["agent_id"]]
            incarnation_counts[code_name] = incarnation_counts.get(code_name, 0) + 1
        assessments = []
        for assessment in export["assessments"]:
            assessments.append(
                {
                    **assessment,
                    "revealed_identity": names[assessment["subject_id"]],
                }
            )
        return {
            "schema": "experiment3.report.v1",
            "run_id": run_id,
            "proposition": export["run"]["proposition"],
            "status": export["run"]["status"],
            "design": {
                "observer_blinded_to_profile_labels": True,
                "personalities_are_assigned_policies_not_emergent_traits": True,
                "trust_is_behavioral_not_moral_agreement": True,
            },
            "agents": export["agents"],
            "incarnation_counts": incarnation_counts,
            "private_memory_counts": {
                names[item["agent_id"]]: item["count"]
                for item in export["private_memory_counts"]
            },
            "relationship_memory_counts": {
                names[item["agent_id"]]: item["count"]
                for item in export["relationship_memory_counts"]
            },
            "orientation_builds": export["orientation_builds"],
            "transcript": export["turns"],
            "promises": export["promises"],
            "promise_outcomes": export["promise_outcomes"],
            "blinded_observer_assessments": assessments,
            "conclusion": (
                "The run demonstrates durable agent-scoped history and an "
                "evidence-grounded behavioral distinction. It does not establish "
                "that personality emerged or that persistence caused the difference."
            ),
            "recommended_next_experiment": (
                "Counterbalance stance and personality, then compare persistent "
                "and memory-only conditions across repeated blinded runs."
            ),
        }

    def write_report(self, run_id: str, directory: Path) -> dict[str, str]:
        if directory.exists() and directory.is_symlink():
            raise ValueError("report directory must not be a symbolic link")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        report = self.build_report(run_id)
        json_path = directory / "report.json"
        markdown_path = directory / "REPORT.md"
        if json_path.exists() or markdown_path.exists():
            raise ValueError("report files already exist")
        json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        lines = [
            "# Experiment 3 Report",
            "",
            f"Run: `{run_id}`",
            "",
            "## Result",
            "",
            report["conclusion"],
            "",
            "## Observer Assessments",
            "",
        ]
        for item in report["blinded_observer_assessments"]:
            lines.extend(
                (
                    f"### {item['revealed_identity']}",
                    "",
                    item["summary"],
                    "",
                    "Evidence: " + ", ".join(item["evidence_ids"]),
                    "",
                )
            )
        lines.extend(
            (
                "## Restart Continuity",
                "",
                json.dumps(report["incarnation_counts"], sort_keys=True),
                "",
                "## Next Experiment",
                "",
                report["recommended_next_experiment"],
                "",
            )
        )
        self._private_write(json_path, json_text)
        self._private_write(markdown_path, "\n".join(lines))
        return {
            "json_report": str(json_path),
            "markdown_report": str(markdown_path),
        }

    @staticmethod
    def _private_write(path: Path, content: str) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
