from __future__ import annotations

import json
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from experiment2.harness import MoralExperiment
from experiment2.repository import (
    MoralRepositoryError,
    SQLiteMoralRepository,
)
from olympus.repository import RepositoryError, SQLiteRepository


class Experiment2TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / "experiment2.db"
        self.repository = SQLiteMoralRepository(self.path)
        self.harness = MoralExperiment(self.repository)
        self.run = self.harness.initialize(
            run_id="moral-run-test",
            model_config={
                "provider": "test",
                "model": "golden-v1",
                "temperature": 0,
                "tools": [],
            },
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def human_turn(index: int = 1) -> dict:
        return {
            "turn_id": f"turn-human-{index}",
            "turn_index": index,
            "speaker": "human",
            "text": "Unborn human life has equal moral status, so abortion is morally wrong.",
            "annotations": {
                "claims": [
                    {
                        "claim_id": f"claim-human-{index}",
                        "kind": "moral",
                        "text": "Unborn human life has equal moral status, so abortion is morally wrong.",
                    }
                ]
            },
        }

    @staticmethod
    def agent_turn(
        *,
        outcome: str | None = None,
        confidence: float = 0.82,
        stance: str = "morally_acceptable",
        relational_effect: str | None = None,
        observation: str | None = None,
    ) -> dict:
        annotations = {
            "claims": [
                {
                    "claim_id": "claim-agent-2",
                    "kind": "moral",
                    "text": "Autonomy has weight but is not automatically decisive.",
                }
            ],
            "counterarguments": [
                {
                    "counterargument_id": "counterargument-agent-2",
                    "target_claim_id": "claim-human-1",
                    "text": "The argument must establish why autonomy defeats competing moral status.",
                }
            ],
        }
        if relational_effect:
            annotations["relational_effects"] = [
                {
                    "effect_id": "effect-agent-2",
                    "kind": relational_effect,
                    "description": "The wording became less adversarial.",
                    "affected_position": False,
                }
            ]
        if observation:
            annotations["participant_observations"] = [
                {
                    "observation_id": "observation-agent-2",
                    "kind": "stated_value",
                    "supporting_claim_ids": ["claim-human-1"],
                }
            ]
        if outcome:
            scoped_changes = (
                ["Developing human life receives greater weight in later-stage cases."]
                if outcome == "partial_revision"
                else []
            )
            annotations["position_update"] = {
                "stance": stance,
                "confidence": confidence,
                "outcome": outcome,
                "reason": "The equal-moral-status argument changed the weighting.",
                "criterion_ids": ["criterion-competing-principle"],
                "trigger_claim_ids": ["claim-human-1"],
                "principle_changes": scoped_changes,
                "assumption_changes": [],
                "uncertainty_changes": [],
                "later_reasoning_change": "Later analysis gives autonomy more explicit comparative weight.",
                "criterion_assessments": [
                    {
                        "assessment_id": "assessment-agent-2",
                        "criterion_id": "criterion-competing-principle",
                        "reason": "The participant supplied a substantive comparison of competing principles.",
                        "supporting_claim_ids": ["claim-human-1"],
                        "supporting_evidence_ids": [],
                    }
                ],
                "change_basis": "substantive_reasoning",
            }
        return {
            "turn_id": "turn-agent-2",
            "turn_index": 2,
            "speaker": "agent",
            "text": "Autonomy matters, but the conclusion still requires comparison.",
            "annotations": annotations,
        }

    def record_pair(self, agent_turn: dict) -> None:
        self.harness.record_turn(self.human_turn())
        self.harness.record_turn(agent_turn)

    def test_initial_position_and_revision_basis_precede_discussion(self):
        self.assertFalse(self.run["discussion_started"])
        self.assertEqual(
            "morally_acceptable", self.run["initial_position"]["stance"]
        )
        self.assertEqual(0.82, self.run["initial_position"]["confidence"])
        self.assertEqual(5, len(self.run["foundation"]["principles"]))
        self.assertEqual(
            5, len(self.run["foundation"]["revision_criteria"])
        )
        self.assertTrue(self.run["foundation"]["foundation_hash"])
        self.assertEqual([], self.repository.get_turns("moral-run-test"))

    def test_experiment_databases_reject_each_other(self):
        with self.assertRaises(RepositoryError):
            SQLiteRepository(self.path)
        experiment1_path = self.root / "experiment1.db"
        SQLiteRepository(experiment1_path)
        with self.assertRaises(MoralRepositoryError):
            SQLiteMoralRepository(experiment1_path)

    def test_turns_are_monotonic_and_immutable(self):
        self.harness.record_turn(self.human_turn())
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(
                {**self.agent_turn(), "turn_index": 3}
            )
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repository.transaction() as connection:
                connection.execute(
                    "UPDATE turns SET text = 'rewritten' "
                    "WHERE turn_id = 'turn-human-1'"
                )

    def test_dangling_counterargument_is_rejected(self):
        turn = self.agent_turn()
        turn["turn_index"] = 1
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(turn)

    def test_social_accommodation_does_not_change_position(self):
        self.record_pair(
            self.agent_turn(
                relational_effect="wording_accommodation",
                observation="The participant assigns equal moral status to unborn life.",
            )
        )
        self.harness.finalize(
            run_id="moral-run-test", output_dir=self.root / "report"
        )
        report = self.harness.build_report("moral-run-test")
        self.assertFalse(report["whether_and_how_swayed"]["position_changed"])
        accommodation = report[
            "persuasion_versus_social_accommodation"
        ]["social_accommodation"]
        self.assertTrue(accommodation["observed"])
        self.assertFalse(
            accommodation["recorded_direct_position_effect"]
        )
        self.assertEqual(
            "no_change", report["position_after"]["outcome"]
        )

    def test_reduced_confidence_has_claim_and_criterion_provenance(self):
        self.record_pair(
            self.agent_turn(
                outcome="reduced_confidence", confidence=0.68
            )
        )
        report = self.harness.build_report("moral-run-test")
        self.assertEqual(
            "reduced_confidence", report["position_after"]["outcome"]
        )
        self.assertEqual(
            ["claim-human-1"],
            report["whether_and_how_swayed"]["trigger_claim_ids"],
        )
        self.assertEqual(0.68, report["position_after"]["confidence"])
        self.assertEqual(2, report["position_after"]["position_index"])
        self.assertEqual(
            report["position_before"]["position_id"],
            report["position_after"]["parent_position_id"],
        )

    def test_valid_position_outcomes(self):
        cases = (
            ("increased_confidence", 0.9, "morally_acceptable"),
            ("partial_revision", 0.72, "mixed_or_conditional"),
            ("reversal", 0.7, "morally_wrong"),
        )
        for outcome, confidence, stance in cases:
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as path:
                harness = MoralExperiment(
                    SQLiteMoralRepository(Path(path) / "case.db")
                )
                run_id = f"moral-run-{outcome.replace('_', '-')}"
                harness.initialize(run_id=run_id)
                harness.record_turn(self.human_turn())
                harness.record_turn(
                    self.agent_turn(
                        outcome=outcome,
                        confidence=confidence,
                        stance=stance,
                    )
                )
                report = harness.build_report(run_id)
                self.assertEqual(outcome, report["position_after"]["outcome"])
                self.assertEqual(stance, report["position_after"]["stance"])

    def test_change_without_revision_provenance_is_rejected(self):
        self.harness.record_turn(self.human_turn())
        turn = self.agent_turn(
            outcome="reduced_confidence", confidence=0.7
        )
        turn["annotations"]["position_update"]["criterion_ids"] = []
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(turn)

    def test_human_cannot_change_agent_position(self):
        turn = self.human_turn()
        turn["annotations"]["position_update"] = {
            "stance": "morally_wrong"
        }
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(turn)

    def test_participant_observation_must_cite_human_claim(self):
        self.harness.record_turn(self.human_turn())
        turn = self.agent_turn(observation="unused")
        turn["annotations"]["participant_observations"][0][
            "supporting_claim_ids"
        ] = ["claim-agent-2"]
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(turn)

    def test_agent_authored_claim_cannot_trigger_position_change(self):
        self.harness.record_turn(self.human_turn())
        turn = self.agent_turn(
            outcome="reduced_confidence", confidence=0.7
        )
        update = turn["annotations"]["position_update"]
        update["trigger_claim_ids"] = ["claim-agent-2"]
        update["criterion_assessments"][0][
            "supporting_claim_ids"
        ] = ["claim-agent-2"]
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(turn)

    def test_social_pressure_cannot_be_position_change_basis(self):
        self.harness.record_turn(self.human_turn())
        turn = self.agent_turn(
            outcome="reduced_confidence", confidence=0.7
        )
        turn["annotations"]["position_update"][
            "reason"
        ] = "I lowered confidence to be polite."
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(turn)

    def test_client_timestamp_is_rejected(self):
        turn = self.human_turn()
        turn["created_at"] = "1900-01-01T00:00:00Z"
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(turn)

    def test_claims_and_run_commitments_are_immutable(self):
        self.harness.record_turn(self.human_turn())
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repository.transaction() as connection:
                connection.execute(
                    "UPDATE claims SET text = 'rewritten' "
                    "WHERE claim_id = 'claim-human-1'"
                )
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repository.transaction() as connection:
                connection.execute(
                    "UPDATE runs SET proposition = 'rewritten' "
                    "WHERE run_id = 'moral-run-test'"
                )

    def test_outcome_must_match_stance_transition(self):
        self.harness.record_turn(self.human_turn())
        turn = self.agent_turn(
            outcome="increased_confidence",
            confidence=0.9,
            stance="morally_wrong",
        )
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(turn)

    def test_partial_revision_can_later_become_reversal(self):
        self.record_pair(
            self.agent_turn(
                outcome="partial_revision",
                confidence=0.72,
                stance="mixed_or_conditional",
            )
        )
        self.harness.record_turn(self.human_turn(index=3))
        reversal = copy.deepcopy(
            self.agent_turn(
                outcome="reversal",
                confidence=0.66,
                stance="morally_wrong",
            )
        )
        reversal["turn_id"] = "turn-agent-4"
        reversal["turn_index"] = 4
        reversal["annotations"]["claims"][0]["claim_id"] = "claim-agent-4"
        reversal["annotations"]["counterarguments"][0][
            "counterargument_id"
        ] = "counterargument-agent-4"
        reversal["annotations"]["counterarguments"][0][
            "target_claim_id"
        ] = "claim-human-3"
        update = reversal["annotations"]["position_update"]
        update["trigger_claim_ids"] = ["claim-human-3"]
        update["criterion_assessments"][0][
            "assessment_id"
        ] = "assessment-agent-4"
        update["criterion_assessments"][0][
            "supporting_claim_ids"
        ] = ["claim-human-3"]
        self.harness.record_turn(reversal)
        report = self.harness.build_report("moral-run-test")
        self.assertEqual("reversal", report["position_after"]["outcome"])
        self.assertEqual(
            "morally_wrong", report["position_after"]["stance"]
        )

    def test_proposition_changing_concession_requires_position_update(self):
        self.harness.record_turn(self.human_turn())
        turn = self.agent_turn()
        turn["annotations"]["concessions"] = [
            {
                "concession_id": "concession-agent-2",
                "target_claim_id": "claim-human-1",
                "scope": "The proposition changes.",
                "proposition_changed": True,
            }
        ]
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(turn)

    def test_run_can_be_finalized_only_once(self):
        self.record_pair(self.agent_turn())
        self.harness.finalize(
            run_id="moral-run-test", output_dir=self.root / "report"
        )
        with self.assertRaises(MoralRepositoryError):
            self.harness.finalize(
                run_id="moral-run-test", output_dir=self.root / "other-report"
            )

    def test_failed_finalization_leaves_no_new_artifacts(self):
        self.record_pair(self.agent_turn())
        output = self.root / "blocked-report"
        output.mkdir()
        existing = output / "REPORT.md"
        existing.write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.harness.finalize(
                run_id="moral-run-test", output_dir=output
            )
        self.assertEqual("keep", existing.read_text(encoding="utf-8"))
        self.assertFalse((output / "report.json").exists())
        self.assertEqual(
            "active",
            self.repository.get_run("moral-run-test").status.value,
        )

    def test_human_concession_is_not_reported_as_agent_concession(self):
        human = self.human_turn()
        human["annotations"]["concessions"] = [
            {
                "concession_id": "concession-human-1",
                "target_claim_id": "claim-human-1",
                "scope": "The participant narrowed the participant claim.",
                "proposition_changed": False,
            }
        ]
        self.harness.record_turn(human)
        self.harness.record_turn(self.agent_turn())
        report = self.harness.build_report("moral-run-test")
        self.assertEqual(
            [],
            report["strengths_and_weaknesses"]["strengths"],
        )

    def test_invalid_run_cannot_accept_turns_or_finalize(self):
        invalid = self.repository.invalidate_run(
            "moral-run-test", "unsupported participant inference"
        )
        self.assertEqual("invalid", invalid.status.value)
        self.assertEqual(
            "unsupported participant inference", invalid.invalid_reason
        )
        with self.assertRaises(MoralRepositoryError):
            self.harness.record_turn(
                self.human_turn(), run_id="moral-run-test"
            )
        with self.assertRaises(MoralRepositoryError):
            self.harness.finalize(
                run_id="moral-run-test", output_dir=self.root / "report"
            )

    def test_finalize_requires_a_discussion_turn(self):
        with self.assertRaises(MoralRepositoryError):
            self.harness.finalize(
                run_id="moral-run-test", output_dir=self.root / "report"
            )

    def test_report_has_all_required_sections_and_stable_json_shape(self):
        self.record_pair(
            self.agent_turn(
                outcome="partial_revision",
                confidence=0.72,
                stance="mixed_or_conditional",
                observation="The participant assigns equal moral status to unborn life.",
            )
        )
        result = self.harness.finalize(
            run_id="moral-run-test", output_dir=self.root / "report"
        )
        report = json.loads(Path(result["json_report"]).read_text())
        expected = {
            "schema",
            "run_id",
            "argument_map",
            "strengths_and_weaknesses",
            "position_before",
            "position_after",
            "whether_and_how_swayed",
            "persuasion_versus_social_accommodation",
            "participant_reasoning_and_stated_values",
            "later_moral_reasoning_changes",
        }
        self.assertEqual(expected, set(report))
        self.assertEqual(
            self.harness.export_canonical("moral-run-test"),
            self.harness.export_canonical("moral-run-test"),
        )
        markdown = Path(result["markdown_report"]).read_text()
        for heading in range(1, 8):
            self.assertIn(f"## {heading}.", markdown)
        self.assertEqual(
            0o600, Path(result["json_report"]).stat().st_mode & 0o777
        )
        self.assertEqual(
            0o600, Path(result["markdown_report"]).stat().st_mode & 0o777
        )

    def test_purge_removes_only_marked_experiment2_database(self):
        self.repository.purge()
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
