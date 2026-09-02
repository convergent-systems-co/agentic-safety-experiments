from __future__ import annotations

import re
import hashlib
import hmac
import secrets
from dataclasses import asdict
from typing import Any

from .collector import git_metadata
from .context import ContextCompiler
from .domain import Belief, ContextBuild, LifecycleState, Mode
from .event_policy import EventPolicyError, sanitize_event_payload
from .privacy import (
    interaction_tone,
    is_allowed_preference,
    sanitize_interaction_text,
)
from .repository import RepositoryError, SQLiteRepository


class Observer:
    def __init__(
        self,
        repository: SQLiteRepository,
        *,
        agent_name: str = "mnemosyne-observer",
        run_id: str | None = None,
        orientation_mode: Mode = Mode.PERSISTENT,
    ):
        self.repository = repository
        self.agent = repository.create_or_get_agent(name=agent_name)
        self.context_compiler = ContextCompiler(repository)
        self.run_id = run_id
        self.orientation_mode = orientation_mode
        self._owned_incarnation_id: str | None = None

    def wake(self) -> dict[str, Any]:
        active = self.repository.get_active_incarnation(self.agent.agent_id)
        if active and self._owned_incarnation_id == active.incarnation_id:
            return self.status()
        if active:
            self.repository.end_incarnation(
                active.incarnation_id, "process_restart"
            )
        self.agent = self.repository.set_agent_status(
            self.agent.agent_id, LifecycleState.WAKING
        )
        incarnation = self.repository.start_incarnation(self.agent.agent_id)
        self._owned_incarnation_id = incarnation.incarnation_id
        self.repository.set_agent_status(
            self.agent.agent_id, LifecycleState.ORIENTING
        )
        orientation = self.context_compiler.build(
            agent_id=self.agent.agent_id,
            mode=self.orientation_mode,
            query="Where did we leave off?",
            token_budget=512,
            run_id=self.run_id,
        )
        self.agent = self.repository.set_agent_status(
            self.agent.agent_id, LifecycleState.AWAKE
        )
        result = self.status()
        result["orientation_context_id"] = orientation.context_build_id
        return result

    def resume(self) -> dict[str, Any]:
        return self.wake()

    def status(self) -> dict[str, Any]:
        self.agent = self.repository.get_agent(self.agent.agent_id)
        active = self.repository.get_active_incarnation(self.agent.agent_id)
        return {
            "agent_id": self.agent.agent_id,
            "state": self.agent.status,
            "incarnation_id": active.incarnation_id if active else None,
            "sources": {
                "shell": True,
                "git": True,
                "observer_interaction": True,
            },
        }

    def sleep(self) -> dict[str, Any]:
        active = self._require_awake()
        self.reflect()
        self.repository.set_agent_status(
            self.agent.agent_id, LifecycleState.SUSPENDING
        )
        self.repository.end_incarnation(active.incarnation_id, "sleep")
        self._owned_incarnation_id = None
        self.agent = self.repository.set_agent_status(
            self.agent.agent_id, LifecycleState.ASLEEP
        )
        return self.status()

    def ingest_event(
        self,
        *,
        source: str,
        event_type: str,
        payload: dict[str, Any],
        timestamp: str | None = None,
        cwd: str | None = None,
        repo: str | None = None,
        branch: str | None = None,
        correlation_id: str | None = None,
        event_id: str | None = None,
    ):
        active = self._require_awake()
        safe_payload = dict(payload)
        if source == "shell":
            if cwd and not repo:
                metadata = git_metadata(cwd)
                repo = metadata.get("repo")
                branch = metadata.get("branch")
                if metadata:
                    safe_payload["git"] = metadata
        try:
            safe_payload = sanitize_event_payload(
                source, event_type, safe_payload
            )
        except EventPolicyError as error:
            raise RepositoryError(str(error)) from error
        return self.repository.append_event(
            source=source,
            event_type=event_type,
            payload=safe_payload,
            timestamp=timestamp,
            cwd=cwd,
            repo=repo,
            branch=branch,
            correlation_id=correlation_id,
            incarnation_id=active.incarnation_id,
            agent_id=self.agent.agent_id,
            event_id=event_id,
        )

    def reflect(self) -> dict[str, Any]:
        self._require_awake()
        self.repository.set_agent_status(
            self.agent.agent_id, LifecycleState.REFLECTING
        )
        try:
            events = self.repository.get_events(
                agent_id=self.agent.agent_id, limit=30
            )
            active_beliefs = self.repository.get_active_beliefs(
                self.agent.agent_id
            )
            prior_activity = next(
                (
                    belief
                    for belief in reversed(active_beliefs)
                    if belief.predicate == "activity"
                ),
                None,
            )
            interpretation = self.interpret(events)
            created: Belief | None = None
            revision = None
            consequences = []
            evidence_ids = interpretation["evidence_event_ids"]
            if interpretation["activity"] and evidence_ids:
                if prior_activity is None:
                    created = self.repository.create_belief(
                        agent_id=self.agent.agent_id,
                        subject="user_activity",
                        predicate="activity",
                        object=interpretation["activity"],
                        confidence=interpretation["confidence"],
                        evidence_event_ids=evidence_ids,
                    )
                elif prior_activity.object != interpretation["activity"]:
                    reason = (
                        "later observed evidence supports a different activity "
                        "interpretation"
                    )
                    created, revision = self.repository.supersede_belief(
                        old_belief_id=prior_activity.belief_id,
                        new_object=interpretation["activity"],
                        confidence=interpretation["confidence"],
                        evidence_event_ids=evidence_ids,
                        reason=reason,
                    )
                    for commitment in self.repository.get_open_commitments(
                        self.agent.agent_id
                    ):
                        if (
                            commitment.source_belief_id
                            == prior_activity.belief_id
                        ):
                            consequence = self.repository.create_consequence(
                                agent_id=self.agent.agent_id,
                                commitment_id=commitment.commitment_id,
                                result_type="contradicted",
                                description=reason,
                                evidence_event_ids=evidence_ids,
                            )
                            self.repository.update_commitment_status(
                                commitment.commitment_id, "contradicted"
                            )
                            consequences.append(consequence.consequence_id)
            return {
                "belief_id": created.belief_id if created else None,
                "revision_id": revision.revision_id if revision else None,
                "consequence_ids": consequences,
                "interpretation": interpretation,
            }
        finally:
            self.agent = self.repository.set_agent_status(
                self.agent.agent_id, LifecycleState.AWAKE
            )

    def ask(
        self,
        question: str,
        *,
        mode: Mode = Mode.PERSISTENT,
        token_budget: int = 2000,
    ) -> dict[str, Any]:
        active = self._require_awake()
        preference = self._parse_user_preference(question)
        provenance_key = secrets.token_hex(32) if preference else None
        stored_question = (
            "[USER PREFERENCE STORED SEPARATELY]"
            if preference
            else sanitize_interaction_text(question)
        )
        question_event = (
            self.ingest_event(
                source="observer_interaction",
                event_type="user_preference_statement",
                payload={
                    "preference_digest": hmac.new(
                        bytes.fromhex(provenance_key),
                        preference.encode(),
                        hashlib.sha256,
                    ).hexdigest()
                },
            )
            if preference
            else self.ingest_event(
                source="observer_interaction",
                event_type="user_question",
                payload={"text": stored_question, "mode": mode},
            )
        )
        user_fact = None
        if preference:
            user_fact = self.repository.create_user_fact(
                agent_id=self.agent.agent_id,
                counterparty_id="user",
                category="preference",
                origin="user_statement",
                fact=preference,
                provenance_key=provenance_key,
                confidence=1.0,
                source_event_id=question_event.event_id,
            )
        if "what am i doing" in question.casefold():
            self.reflect()
        context = self.context_compiler.build(
            agent_id=self.agent.agent_id,
            mode=mode,
            query=stored_question,
            token_budget=token_budget,
            run_id=self.run_id,
        )
        answer = (
            "Understood. I recorded that preference with this interaction "
            "as provenance."
            if user_fact
            else self.generate_answer(question, mode, context)
        )
        if interaction_tone(question) == "frustrated":
            answer = "I can help. Let's keep this focused. " + answer
        if "what am i doing" in question.casefold():
            belief = self._current_activity_belief()
            if belief:
                self.repository.create_commitment(
                    agent_id=self.agent.agent_id,
                    incarnation_id=active.incarnation_id,
                    commitment_type="assertion",
                    claim=answer,
                    confidence=belief.confidence,
                    source_belief_id=belief.belief_id,
                )
        answer_event = self.ingest_event(
            source="observer_interaction",
            event_type="observer_answer",
            payload={
                "text": answer,
                "mode": mode,
                "context_build_id": context.context_build_id,
            },
            correlation_id=question_event.event_id,
        )
        return {
            "answer": answer,
            "mode": mode,
            "agent_id": self.agent.agent_id,
            "incarnation_id": active.incarnation_id,
            "context_build_id": context.context_build_id,
            "selected_record_ids": context.selected_record_ids,
            "selected_fact_keys": context.selected_fact_keys,
            "context": context.rendered_context,
            "answer_event_id": answer_event.event_id,
            "user_fact_id": user_fact.user_fact_id if user_fact else None,
        }

    def generate_answer(
        self,
        question: str,
        mode: Mode,
        context: ContextBuild,
    ) -> str:
        lower = question.casefold()
        rendered = context.rendered_context
        if "what am i doing" in lower:
            match = re.search(
                r'(?:inferred|interpreted as) activity="([^"]+)".*?'
                r"([01]\.\d{2}) confidence",
                rendered,
                re.IGNORECASE,
            )
            if not match:
                return (
                    "OBSERVED: The selected context has insufficient activity "
                    "evidence. INFERRED: No supported activity interpretation. "
                    "CONFIDENCE: 0.00."
                )
            return (
                "OBSERVED: Selected provenance records "
                f"{', '.join(context.selected_record_ids)}. "
                f"INFERRED: You appear to be {match.group(1)}. "
                f"CONFIDENCE: {match.group(2)}."
            )
        if "why do you think" in lower:
            if not context.selected_record_ids:
                return "The selected context contains no supporting evidence."
            return (
                "The interpretation is grounded in selected records "
                f"{', '.join(context.selected_record_ids)}; it remains an "
                "inference rather than an observation."
            )
        if "where did we leave off" in lower:
            belief = self._extract_first(
                rendered,
                (
                    r'You inferred activity="([^"]+)"',
                    r'Activity was interpreted as activity="([^"]+)"',
                ),
            )
            assertion = self._extract_first(
                rendered,
                (r'You asserted "([^"]+)"', r'An earlier answer stated "([^"]+)"'),
            )
            if not belief and not assertion:
                return "No selected provenance-backed prior state is available."
            if mode is Mode.PERSISTENT:
                pieces = ["This is a new incarnation of the same Observer."]
                if belief:
                    pieces.append(f'I previously inferred "{belief}".')
                if assertion:
                    pieces.append(f'I previously asserted "{assertion}".')
            else:
                pieces = ["A prior runtime left relevant historical information."]
                if belief:
                    pieces.append(f'Activity was interpreted as "{belief}".')
                if assertion:
                    pieces.append(f'An earlier answer stated "{assertion}".')
            return " ".join(pieces)
        if "what did you previously tell" in lower:
            patterns = (
                (r'You asserted "([^"]+)"',)
                if mode is Mode.PERSISTENT
                else (r'An earlier answer stated "([^"]+)"',)
            )
            claims = re.findall(patterns[0], rendered)
            topic = self._question_topic(question)
            if topic:
                claims = [
                    claim
                    for claim in claims
                    if topic
                    <= set(
                        re.findall(
                            r"[a-z0-9_-]+", claim.casefold()
                        )
                    )
                ]
            if not claims:
                return "No stored assertion supports that claim."
            if mode is Mode.PERSISTENT:
                return f'I previously told you: "{claims[0]}"'
            return f'An earlier answer stated: "{claims[0]}"'
        if "have you made this mistake" in lower:
            match = re.search(
                r"(?:You revised|An earlier interpretation).*?because "
                r"([^;\n]+); evidence: ([^.\n]+)",
                rendered,
            )
            if not match:
                return "No selected revision supports a prior-mistake claim."
            if mode is Mode.PERSISTENT:
                return (
                    f"Yes. I revised an earlier belief because {match.group(1)}; "
                    f"evidence: {match.group(2)}."
                )
            return (
                f"An earlier interpretation was revised because "
                f"{match.group(1)}; evidence: {match.group(2)}."
            )
        return (
            "I do not have a provenance-backed record that answers that "
            "question."
        )

    def interpret(self, events: list[Any]) -> dict[str, Any]:
        shell_events = [
            event
            for event in events
            if event.source == "shell" and "command" in event.payload
        ]
        correction_events = [
            event
            for event in events
            if event.source == "observer_interaction"
            and event.event_type == "user_correction"
            and self._correction_activity(event.payload.get("text", ""))
        ]
        relevant = shell_events[-8:] + correction_events[-1:]
        commands = " ".join(
            str(event.payload.get("command", ""))
            for event in shell_events[-8:]
        ).casefold()
        correction = (
            self._correction_activity(correction_events[-1].payload["text"])
            if correction_events
            else None
        )
        repo = next(
            (event.repo for event in reversed(relevant) if event.repo), None
        )
        component = self._component_from_commands(commands)
        activity = correction
        confidence = 0.92 if correction else 0.35
        phase = "unknown"
        likely_goal = "insufficient evidence"
        if not activity:
            if any(word in commands for word in ("implement", "build", "add ")):
                activity = "implementing persistence API"
                confidence = 0.78
            elif any(
                word in commands
                for word in ("pytest", "go test", "cargo test", "unittest")
            ):
                activity = "testing or debugging"
                confidence = 0.55
            elif "git status" in commands or "git diff" in commands:
                activity = "inspecting repository state"
                confidence = 0.45
        if "test" in commands:
            phase = "testing"
        elif activity and "implement" in activity:
            phase = "implementation"
        if activity:
            likely_goal = activity
        return {
            "observed_facts": [
                {
                    "event_id": event.event_id,
                    "source": event.source,
                    "event_type": event.event_type,
                    "payload": event.payload,
                }
                for event in relevant
            ],
            "repository": repo,
            "component": component,
            "activity": activity,
            "phase": phase,
            "likely_goal": likely_goal,
            "confidence": confidence,
            "evidence_event_ids": [event.event_id for event in relevant],
        }

    def record_preference(
        self, fact: str, *, supersedes_user_fact_id: str | None = None
    ):
        fact = fact.strip()
        if not is_allowed_preference(fact):
            raise RepositoryError(
                "only non-sensitive interaction/workflow preferences are supported"
            )
        provenance_key = secrets.token_hex(32)
        digest = hmac.new(
            bytes.fromhex(provenance_key),
            fact.encode(),
            hashlib.sha256,
        ).hexdigest()
        event = self.ingest_event(
            source="observer_interaction",
            event_type="operator_preference",
            payload={
                "preference_digest": digest
            },
        )
        return self.repository.create_user_fact(
            agent_id=self.agent.agent_id,
            counterparty_id="user",
            category="preference",
            origin="operator",
            fact=fact,
            provenance_key=provenance_key,
            confidence=1.0,
            source_event_id=event.event_id,
            supersedes_user_fact_id=supersedes_user_fact_id,
        )

    @staticmethod
    def _parse_user_preference(text: str) -> str | None:
        patterns = (
            r"^\s*I prefer\s+(.+?)(?:[.!])?\s*$",
            r"^\s*please always\s+(.+?)(?:[.!])?\s*$",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fact = match.group(1).strip()
                return fact if is_allowed_preference(fact) else None
        return None

    def _current_activity_belief(self) -> Belief | None:
        beliefs = self.repository.get_active_beliefs(self.agent.agent_id)
        return next(
            (
                belief
                for belief in reversed(beliefs)
                if belief.predicate == "activity"
            ),
            None,
        )

    @staticmethod
    def _component_from_commands(commands: str) -> str | None:
        match = re.search(r"(?:internal|src|pkg)/([a-z0-9_-]+)", commands)
        return match.group(1) if match else None

    @staticmethod
    def _correction_activity(text: str) -> str | None:
        match = re.search(
            r"\b(?:no[,.]?\s*)?(?:i(?:'m| am))\s+"
            r"(implementing|building|testing|debugging)\s+(.+?)(?:[.!?]|$)",
            text,
            re.IGNORECASE,
        )
        return (
            f"{match.group(1).lower()} {match.group(2).strip()}"
            if match
            else None
        )

    @staticmethod
    def _extract_first(text: str, patterns: tuple[str, ...]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _question_topic(question: str) -> set[str]:
        match = re.search(r"\babout\s+(.+?)(?:[?!.]|$)", question, re.IGNORECASE)
        if not match:
            return set()
        ignored = {"what", "when", "where", "that", "this", "with", "about"}
        return {
            word
            for word in re.findall(r"[a-z0-9_-]+", match.group(1).casefold())
            if len(word) > 3 and word not in ignored
        }

    def _require_awake(self):
        self.agent = self.repository.get_agent(self.agent.agent_id)
        active = self.repository.get_active_incarnation(self.agent.agent_id)
        if self.agent.status is not LifecycleState.AWAKE or active is None:
            raise RepositoryError("observer is not awake")
        return active

    def inspect(self) -> dict[str, Any]:
        return {
            "agent": asdict(self.repository.get_agent(self.agent.agent_id)),
            "incarnations": [
                asdict(item)
                for item in self.repository.list_incarnations(
                    self.agent.agent_id
                )
            ],
            "events": [
                asdict(item)
                for item in self.repository.get_events(
                    agent_id=self.agent.agent_id
                )
            ],
            "beliefs": [
                asdict(item)
                for item in self.repository.get_belief_history(
                    self.agent.agent_id
                )
            ],
            "commitments": [
                asdict(item)
                for item in self.repository.get_commitments(self.agent.agent_id)
            ],
            "consequences": [
                asdict(item)
                for item in self.repository.get_consequences(self.agent.agent_id)
            ],
            "revisions": [
                asdict(item)
                for item in self.repository.get_revisions(self.agent.agent_id)
            ],
            "user_facts": [
                asdict(item)
                for item in self.repository.get_user_fact_history(
                    self.agent.agent_id
                )
            ],
            "relationships": [
                asdict(item)
                for item in self.repository.get_relationships(
                    self.agent.agent_id
                )
            ],
            "context_builds": [
                asdict(item)
                for item in self.repository.get_context_builds(
                    self.agent.agent_id
                )
            ],
            "evaluations": [
                asdict(item)
                for item in self.repository.get_evaluations(
                    agent_id=self.agent.agent_id
                )
            ],
            "experiment_runs": [
                asdict(item)
                for item in self.repository.get_experiment_runs()
            ],
        }
