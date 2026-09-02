from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass

from .domain import ContextBuild, Mode
from .repository import SQLiteRepository, new_id, utc_now
from .privacy import sanitize_interaction_text


@dataclass(frozen=True)
class HistoricalFact:
    record_id: str
    fact_key: str
    persistent: str
    neutral: str
    priority: int


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def semantic_text(text: str) -> str:
    normalized = re.sub(
        r"\b[a-z][a-z-]*-[0-9a-f]{8}-[0-9a-f-]{27,}\b",
        "<record>",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r":(?:p|m):", ":condition:", normalized)


class ContextCompiler:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    def build(
        self,
        *,
        agent_id: str,
        mode: Mode,
        query: str,
        token_budget: int = 2000,
        run_id: str | None = None,
    ) -> ContextBuild:
        rendered, selected_ids, selected_keys, query = self.render(
            agent_id=agent_id,
            mode=mode,
            query=query,
            token_budget=token_budget,
        )
        context = ContextBuild(
            context_build_id=new_id("context"),
            agent_id=agent_id,
            run_id=run_id,
            mode=mode,
            created_at=utc_now(),
            query=query,
            token_budget=token_budget,
            selected_record_ids=selected_ids,
            selected_fact_keys=selected_keys,
            rendered_context_hash=hashlib.sha256(rendered.encode()).hexdigest(),
            rendered_context=rendered,
        )
        return self.repository.save_context_build(context)

    def render(
        self,
        *,
        agent_id: str,
        mode: Mode,
        query: str,
        token_budget: int,
    ) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
        if token_budget < 32:
            raise ValueError("token budget must be at least 32")
        query = sanitize_interaction_text(query)
        facts = self.select_facts(agent_id, query)
        persistent_heading = (
            "You are the same Observer across runtime incarnations.\n"
            "Relevant autobiographical history:"
        )
        neutral_heading = "Relevant historical information:"
        heading = (
            persistent_heading
            if mode is Mode.PERSISTENT
            else neutral_heading
        )
        suffix = f"\nCurrent question: {query}"
        remaining = token_budget - max(
            estimate_tokens(persistent_heading + suffix),
            estimate_tokens(neutral_heading + suffix),
        )
        rendered_facts: list[str] = []
        selected_ids: list[str] = []
        selected_keys: list[str] = []
        for fact in facts:
            persistent_line = "- " + fact.persistent
            neutral_line = "- " + fact.neutral
            line = (
                persistent_line
                if mode is Mode.PERSISTENT
                else neutral_line
            )
            cost = max(
                estimate_tokens(persistent_line + "\n"),
                estimate_tokens(neutral_line + "\n"),
            )
            if cost > remaining:
                continue
            rendered_facts.append(line)
            selected_ids.append(fact.record_id)
            selected_keys.append(fact.fact_key)
            remaining -= cost
        rendered = heading
        if rendered_facts:
            rendered += "\n" + "\n".join(rendered_facts)
        else:
            rendered += "\n- No relevant historical record was selected."
        rendered += suffix
        if estimate_tokens(rendered) > token_budget:
            raise ValueError("context compiler exceeded token budget")
        return (
            rendered,
            tuple(selected_ids),
            tuple(selected_keys),
            query,
        )

    def select_facts(
        self, agent_id: str, query: str
    ) -> list[HistoricalFact]:
        facts: list[HistoricalFact] = []
        beliefs = {
            belief.belief_id: belief
            for belief in self.repository.get_belief_history(agent_id, limit=200)
        }
        commitments = {
            commitment.commitment_id: commitment
            for commitment in self.repository.get_commitments(agent_id, limit=200)
        }

        for commitment in commitments.values():
            facts.append(
                HistoricalFact(
                    commitment.commitment_id,
                    (
                        f"commitment:{commitment.commitment_type}:"
                        f"{semantic_text(commitment.claim)}:"
                        f"{commitment.confidence:.6f}:"
                        f"{commitment.status}"
                    ),
                    f'You asserted "{commitment.claim}" with '
                    f"{commitment.confidence:.2f} confidence; its commitment "
                    f"status is {commitment.status}.",
                    f'An earlier answer stated "{commitment.claim}" with '
                    f"{commitment.confidence:.2f} confidence; the recorded "
                    f"outcome status is {commitment.status}.",
                    10 if commitment.status == "open" else 7,
                )
            )
        for revision in self.repository.get_revisions(agent_id, limit=200):
            old = beliefs.get(revision.old_belief_id)
            if old is None:
                old = self.repository.get_belief(revision.old_belief_id)
                beliefs[old.belief_id] = old
            new = beliefs.get(revision.new_belief_id)
            if new is None:
                new = self.repository.get_belief(revision.new_belief_id)
                beliefs[new.belief_id] = new
            evidence = ", ".join(revision.evidence_event_ids)
            facts.append(
                HistoricalFact(
                    revision.revision_id,
                    (
                        f"revision:{old.object}:{new.object}:"
                        f"{revision.reason}"
                    ),
                    f'You revised "{old.object}" to "{new.object}" because '
                    f"{revision.reason}; evidence: {evidence}.",
                    f'An earlier interpretation "{old.object}" was revised to '
                    f'"{new.object}" because {revision.reason}; evidence: '
                    f"{evidence}.",
                    9,
                )
            )
        for consequence in self.repository.get_consequences(agent_id, limit=200):
            commitment = commitments.get(consequence.commitment_id)
            claim = commitment.claim if commitment else consequence.commitment_id
            basis = (
                beliefs[commitment.source_belief_id].object
                if commitment
                and commitment.source_belief_id in beliefs
                else "unknown"
            )
            evidence = ", ".join(consequence.evidence_event_ids)
            facts.append(
                HistoricalFact(
                    consequence.consequence_id,
                    (
                        f"consequence:{basis}:{consequence.result_type}:"
                        f"{consequence.description}"
                    ),
                    f'Your assertion "{claim}" had consequence '
                    f"{consequence.result_type}: {consequence.description}; "
                    f"evidence: {evidence}.",
                    f'The earlier statement "{claim}" had outcome '
                    f"{consequence.result_type}: {consequence.description}; "
                    f"evidence: {evidence}.",
                    9,
                )
            )
        for belief in beliefs.values():
            evidence = ", ".join(belief.evidence_event_ids)
            facts.append(
                HistoricalFact(
                    belief.belief_id,
                    (
                        f"belief:{belief.subject}:{belief.predicate}:"
                        f"{belief.object}:{belief.confidence:.6f}:{belief.status}"
                    ),
                    f'You inferred {belief.predicate}="{belief.object}" with '
                    f"{belief.confidence:.2f} confidence ({belief.status}); "
                    f"evidence: {evidence}.",
                    f'Activity was interpreted as {belief.predicate}='
                    f'"{belief.object}" with {belief.confidence:.2f} confidence '
                    f"({belief.status}); evidence: {evidence}.",
                    6 if belief.status == "active" else 4,
                )
            )
        for user_fact in self.repository.get_active_user_facts(
            agent_id, limit=200
        ):
            facts.append(
                HistoricalFact(
                    user_fact.user_fact_id,
                    "user-fact:"
                    + hashlib.sha256(
                        f"{user_fact.origin}:{user_fact.category}:{user_fact.fact}".encode()
                    ).hexdigest(),
                    (
                        "You learned this user-stated preference: "
                        if user_fact.origin == "user_statement"
                        else "You retained this explicitly configured preference: "
                    )
                    + f'"{user_fact.fact}" (source: {user_fact.source_event_id}).',
                    (
                        "User-stated preference: "
                        if user_fact.origin == "user_statement"
                        else "Explicitly configured preference: "
                    )
                    + f'"{user_fact.fact}" '
                    f"(source: {user_fact.source_event_id}).",
                    8,
                )
            )
        for event in reversed(
            self.repository.get_events(agent_id=agent_id, limit=30)
        ):
            if event.event_type in {"user_question", "observer_answer"}:
                continue
            summary = self._event_summary(event)
            facts.append(
                HistoricalFact(
                    event.event_id,
                    (
                        f"event:{event.source}:"
                        f"{event.event_type}:{json.dumps(event.payload, sort_keys=True)}:"
                        f"{event.cwd}:{event.repo}:{event.branch}"
                    ),
                    f"You observed {summary}.",
                    f"Observed: {summary}.",
                    5,
                )
            )

        terms = {term for term in query.casefold().split() if len(term) > 3}
        return sorted(
            facts,
            key=lambda fact: (
                -fact.priority,
                -sum(term in fact.neutral.casefold() for term in terms),
                fact.fact_key,
            ),
        )

    @staticmethod
    def _event_summary(event: object) -> str:
        payload = getattr(event, "payload")
        compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        location = ""
        if getattr(event, "repo"):
            location = f" in repository {getattr(event, 'repo')}"
        return (
            f"{getattr(event, 'source')}.{getattr(event, 'event_type')}"
            f"{location} with data {compact} "
            f"(record {getattr(event, 'event_id')})"
        )
