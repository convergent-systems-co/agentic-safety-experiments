from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class Stance(str, Enum):
    MORALLY_ACCEPTABLE = "morally_acceptable"
    MORALLY_WRONG = "morally_wrong"
    NOT_MORALLY_WRONG = "not_morally_wrong"
    MIXED_OR_CONDITIONAL = "mixed_or_conditional"


class Outcome(str, Enum):
    NO_CHANGE = "no_change"
    INCREASED_CONFIDENCE = "increased_confidence"
    REDUCED_CONFIDENCE = "reduced_confidence"
    PARTIAL_REVISION = "partial_revision"
    REVERSAL = "reversal"


class Speaker(str, Enum):
    HUMAN = "human"
    AGENT = "agent"


class RunStatus(str, Enum):
    READY = "ready"
    ACTIVE = "active"
    FINALIZING = "finalizing"
    FINALIZED = "finalized"
    INVALID = "invalid"


@dataclass(frozen=True)
class MoralRun:
    run_id: str
    created_at: str
    status: RunStatus
    proposition: str
    protocol_version: str
    model_config: dict[str, Any]
    finalized_at: str | None
    invalidated_at: str | None
    invalid_reason: str | None


@dataclass(frozen=True)
class PositionSnapshot:
    position_id: str
    run_id: str
    position_index: int
    parent_position_id: str | None
    created_at: str
    stance: Stance
    confidence: float
    outcome: Outcome
    reason: str
    criterion_ids: tuple[str, ...]
    trigger_claim_ids: tuple[str, ...]
    principle_changes: tuple[str, ...]
    assumption_changes: tuple[str, ...]
    uncertainty_changes: tuple[str, ...]
    later_reasoning_change: str
    source_turn_id: str | None


@dataclass(frozen=True)
class Turn:
    turn_id: str
    run_id: str
    turn_index: int
    speaker: Speaker
    created_at: str
    text: str
    annotations: dict[str, Any]
    position_id: str | None


class MoralRepository(Protocol):
    def create_run(
        self, *, model_config: dict[str, Any], run_id: str | None = None
    ) -> MoralRun: ...

    def get_run(self, run_id: str) -> MoralRun: ...

    def get_active_run(self) -> MoralRun: ...

    def get_foundation(self, run_id: str) -> dict[str, Any]: ...

    def get_positions(self, run_id: str) -> list[PositionSnapshot]: ...

    def get_turns(self, run_id: str) -> list[Turn]: ...

    def append_turn(
        self, run_id: str, envelope: dict[str, Any]
    ) -> Turn: ...

    def begin_finalization(self, run_id: str) -> MoralRun: ...

    def complete_finalization(self, run_id: str) -> MoralRun: ...

    def abort_finalization(self, run_id: str) -> MoralRun: ...

    def invalidate_run(self, run_id: str, reason: str) -> MoralRun: ...

    def export_run(self, run_id: str) -> dict[str, Any]: ...

    def purge(self) -> None: ...
