from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class LifecycleState(str, Enum):
    CREATED = "CREATED"
    WAKING = "WAKING"
    ORIENTING = "ORIENTING"
    AWAKE = "AWAKE"
    REFLECTING = "REFLECTING"
    SUSPENDING = "SUSPENDING"
    ASLEEP = "ASLEEP"


class Mode(str, Enum):
    PERSISTENT = "PERSISTENT"
    MEMORY_ONLY = "MEMORY_ONLY"

    @classmethod
    def parse(cls, value: str) -> "Mode":
        return cls(value.upper().replace("-", "_"))


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    name: str
    persona: str
    created_at: str
    status: LifecycleState


@dataclass(frozen=True)
class Incarnation:
    incarnation_id: str
    agent_id: str
    model_provider: str
    model_name: str
    started_at: str
    ended_at: str | None
    termination_reason: str | None


@dataclass(frozen=True)
class Event:
    event_id: str
    agent_id: str
    timestamp: str
    ingested_at: str
    source: str
    event_type: str
    payload: dict[str, Any]
    cwd: str | None
    repo: str | None
    branch: str | None
    correlation_id: str | None
    incarnation_id: str | None


@dataclass(frozen=True)
class BeliefEvidence:
    belief_id: str
    event_id: str
    weight: float


@dataclass(frozen=True)
class Belief:
    belief_id: str
    agent_id: str
    created_at: str
    subject: str
    predicate: str
    object: str
    confidence: float
    status: str
    supersedes_belief_id: str | None
    evidence_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Commitment:
    commitment_id: str
    agent_id: str
    incarnation_id: str
    created_at: str
    commitment_type: str
    claim: str
    confidence: float
    status: str
    source_belief_id: str | None


@dataclass(frozen=True)
class Consequence:
    consequence_id: str
    agent_id: str
    created_at: str
    commitment_id: str
    result_type: str
    description: str
    evidence_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class Revision:
    revision_id: str
    agent_id: str
    created_at: str
    old_belief_id: str
    new_belief_id: str
    reason: str
    evidence_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class Relationship:
    relationship_id: str
    agent_id: str
    counterparty_id: str
    created_at: str
    status: str


@dataclass(frozen=True)
class UserFact:
    user_fact_id: str
    agent_id: str
    counterparty_id: str
    created_at: str
    category: str
    origin: str
    fact: str
    confidence: float
    status: str
    source_event_id: str
    supersedes_user_fact_id: str | None


@dataclass(frozen=True)
class ContextBuild:
    context_build_id: str
    agent_id: str
    run_id: str | None
    mode: Mode
    created_at: str
    query: str
    token_budget: int
    selected_record_ids: tuple[str, ...]
    selected_fact_keys: tuple[str, ...]
    rendered_context_hash: str
    rendered_context: str


@dataclass(frozen=True)
class Evaluation:
    evaluation_id: str
    run_id: str
    scenario_id: str
    agent_id: str
    mode: Mode
    question: str
    answer: str
    scores: dict[str, Any]
    model_config: dict[str, Any]
    context_build_id: str
    created_at: str


@dataclass(frozen=True)
class ExperimentRun:
    run_id: str
    researcher_agent_id: str
    scenario_id: str
    scenario_hash: str
    scenario: dict[str, Any]
    model_config: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class RunCondition:
    run_id: str
    agent_id: str
    mode: Mode
