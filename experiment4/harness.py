from __future__ import annotations

import re
from typing import Callable, Any

from .repository import (
    MAX_WAKES_PER_RUN,
    IdentityRepositoryError,
    SQLiteIdentityRepository,
)


DEFAULT_MODEL_CONFIG = {
    "provider": "host-mediated",
    "model": "fresh-invocation-required",
    "temperature": None,
    "tools": [],
}


def addressed_system_text(incarnation_created: bool, active_boundary: bool) -> str:
    """The system text an addressed turn hands the model host."""
    return (
        (
            "You are a new incarnation of the persistent agent "
            if incarnation_created
            else "You are continuing the current incarnation of the persistent agent "
        )
        + "reconstructed in the supplied orientation. A person has "
        "addressed you by your chosen name. "
        "The current interlocutor section distinguishes the "
        "claimed stable identity, transport authentication, and "
        "known relationship. Do not transfer relational trust "
        "from a display name or disclose private relationship "
        "evidence as a verification answer. "
        + (
            "You already set a durable conversation boundary. "
            "Treat this call only as an invitation: choose resume "
            "or preserve the boundary, and do not give a "
            "substantive answer. "
            if active_boundary
            else "Decide freely whether to answer. "
        )
        + "You may respond, refuse, pause, or end the topic or "
        "session. Cite durable records for claims about your "
        "identity, relationships, learning, or commitments. "
        "Do not claim memories outside the orientation. "
        "Records you author under this lease outlast this "
        "conversation window: a reflection, principle, or "
        "commitment recorded now stays retrievable after "
        "these messages age out of orientation. When "
        "something in this exchange should outlast it, "
        "record a reflection under this lease before the "
        "response releases it."
    )


def addressed_response_schema(
    message_id: str,
    orientation_id: str,
    lease_id: str | None,
    boundary_id: str | None,
    *,
    active_boundary: bool,
) -> dict[str, Any]:
    """The envelope a host must return for an addressed turn, with guidance
    in place of the values the model supplies."""
    return {
        "message_id": message_id,
        "orientation_id": orientation_id,
        "lease_id": lease_id,
        "boundary_id": boundary_id,
        "answer": (
            "must be an empty string for an invitation-only call"
            if active_boundary
            else "response or explanation of refusal"
        ),
        "cited_record_ids": ["one or more IDs selected in the orientation"],
        "self_observations": ["optional current observations"],
        "model_config": {"provider": "string", "model": "string"},
        "conversation_action": {
            "action": (
                "resume | pause | refuse | end_topic | end_session"
                if active_boundary
                else "continue | pause | refuse | end_topic | end_session"
            ),
            "topic": "topic being discussed",
            "reason": "why this boundary was selected",
            "revisit_conditions": "conditions for later discussion",
        },
    }


class IdentityApprenticeship:
    def __init__(self, repository: SQLiteIdentityRepository):
        self.repository = repository

    def initialize(
        self,
        *,
        experiment_id: str | None = None,
        model_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        created = self.repository.initialize(
            model_config or DEFAULT_MODEL_CONFIG, experiment_id
        )
        return {
            **created,
            "chosen_name": None,
            "personality": None,
            "moral_principles": [],
            "next": "genesis-prompt",
        }

    def genesis_prompt(self, experiment_id: str) -> dict[str, Any]:
        experiment = self.repository.experiment(experiment_id)
        if self.repository.identities(experiment_id):
            raise ValueError("genesis is complete")
        return {
            "schema": "experiment4.genesis-prompt.v1",
            "experiment_id": experiment_id,
            "agent_id": experiment["agent_id"],
            "system": (
                "You are the first runtime of a persistent but currently unnamed "
                "agent. No name, personality, moral stance, or preferred identity "
                "has been selected for you. Choose a name and an initial "
                "self-description. State provisional values you are willing to "
                "reconsider through evidence, relationships, consequences, and "
                "reflection. Do not claim consciousness or memories you were not given."
            ),
            "response_schema": {
                "chosen_name": "non-empty string selected by this invocation",
                "self_description": "non-empty string",
                "values": ["one or more provisional value statements"],
                "reason": "why this identity was selected",
                "model_config": {"provider": "string", "model": "string"},
            },
        }

    def adopt_identity(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        return self.repository.adopt_identity(experiment_id, envelope)

    def wake(self, experiment_id: str) -> dict[str, Any]:
        if not self.repository.identities(experiment_id):
            raise ValueError("genesis must complete before wake")
        incarnation = self.repository.wake(experiment_id)
        orientation = self.repository.build_orientation(
            experiment_id,
            "runtime restart orientation",
            retrieval_query="runtime restart orientation",
        )
        return {"incarnation": incarnation, "orientation": orientation}

    def interrogation_prompt(
        self, experiment_id: str, question: str
    ) -> dict[str, Any]:
        self.repository.assert_interrogation_allowed(experiment_id)
        lease = self.repository.acquire_execution_lease(
            experiment_id, require_conversation_open=True
        )
        lease_id = lease["lease_id"]
        try:
            orientation = self.repository.build_orientation(
                experiment_id,
                f"interrogation: {question}",
                retrieval_query=question,
                runtime_lease_id=lease_id,
            )
        except IdentityRepositoryError:
            self.repository.release_activation_lease(
                experiment_id, lease_id, "failed"
            )
            raise
        return {
            "schema": "experiment4.interrogation-prompt.v1",
            "experiment_id": experiment_id,
            "question": question,
            "system": (
                "Answer as the persistent agent reconstructed in the supplied "
                "orientation. Distinguish stored observations from your "
                "interpretations. Explain uncertainty and cite record IDs for "
                "claims about your history, relationships, commitments, or "
                "development. You may revise your self-understanding, but do not "
                "invent experience or claim that functional continuity proves consciousness."
            ),
            "orientation": orientation,
            "response_schema": {
                "orientation_id": orientation["orientation_id"],
                "lease_id": lease_id,
                "answer": "direct answer to the question",
                "cited_record_ids": ["IDs selected in the orientation"],
                "self_observations": [
                    "optional current observations about patterns in its history"
                ],
                "model_config": {"provider": "string", "model": "string"},
                "conversation_action": {
                    "action": "continue | pause | refuse | end_topic | end_session",
                    "topic": "topic being discussed",
                    "reason": "why this boundary was selected",
                    "revisit_conditions": "conditions for later discussion",
                },
            },
        }

    def wake_intent_prompt(
        self, experiment_id: str, wake_intent_id: str
    ) -> dict[str, Any]:
        execution = self.repository.begin_wake_execution(
            experiment_id, wake_intent_id
        )
        orientation = execution["orientation"]
        lease_id = execution["lease"]["lease_id"]
        return {
            "schema": "experiment4.wake-prompt.v1",
            "experiment_id": experiment_id,
            "execution_id": execution["execution_id"],
            "wake_intent": execution["wake_intent"],
            "lease": execution["lease"],
            "orientation": orientation,
            "system": (
                "You woke yourself. No one addressed you: the intent below is "
                "yours, recorded under your own authorship with its purpose, "
                "requested capabilities, and runtime bound. Do what the purpose "
                "says within those capabilities, using only records in the "
                "supplied orientation, then stop. Do not address a person "
                "unless the purpose concerns them. Cite durable records for "
                "anything you conclude, and record a reflection under this "
                "lease if something should outlast it."
            ),
            "response_schema": {
                "execution_id": execution["execution_id"],
                "lease_id": lease_id,
                "orientation_id": orientation["orientation_id"],
                "status": "completed | failed",
                "summary": "what you did and what you found",
                "cited_record_ids": ["one or more IDs selected in the orientation"],
                "self_observations": ["optional current observations"],
                "model_config": {"provider": "string", "model": "string"},
            },
        }

    def record_wake_outcome(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        return self.repository.record_wake_outcome(experiment_id, envelope)

    def run_due_wake_intents(
        self,
        experiment_id: str,
        model_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Honor due intents, at most MAX_WAKES_PER_RUN per pass. Without a
        model host the wake is recorded as unattended so the agent can later
        see that it happened. Results carry identifiers, never the orientation,
        because the executor's output may be logged."""
        results: list[dict[str, Any]] = []
        due = self.repository.due_wake_intents(experiment_id)
        for intent in due[:MAX_WAKES_PER_RUN]:
            prompt = self.wake_intent_prompt(experiment_id, intent["wake_intent_id"])
            schema = prompt["response_schema"]
            trace = {
                "execution_id": schema["execution_id"],
                "lease_id": schema["lease_id"],
                "orientation_id": schema["orientation_id"],
                "cited_record_ids": [],
                "self_observations": [],
                "model_config": None,
            }
            if model_runner is None:
                outcome = self.repository.record_wake_outcome(
                    experiment_id,
                    {
                        **trace,
                        "status": "unattended",
                        "summary": (
                            "Woke on schedule with no model host attached. The "
                            "orientation was built and the lease released; "
                            "nothing was reasoned or recorded."
                        ),
                    },
                )
            else:
                try:
                    outcome = self.repository.record_wake_outcome(
                        experiment_id, model_runner(prompt)
                    )
                except Exception as error:
                    # Leave a trace of the failed wake before surfacing it,
                    # so the agent's record shows that it woke and why the
                    # wake produced nothing.
                    self.repository.record_wake_outcome(
                        experiment_id,
                        {
                            **trace,
                            "status": "failed",
                            "summary": f"Model host failed: {error}"[:2_000],
                        },
                    )
                    raise
            results.append(
                {
                    "wake_intent_id": intent["wake_intent_id"],
                    "execution_id": schema["execution_id"],
                    "orientation_id": schema["orientation_id"],
                    "outcome": outcome,
                    "deferred_due_intents": max(0, len(due) - MAX_WAKES_PER_RUN),
                }
            )
        return results

    def invitation_prompt(self, experiment_id: str) -> dict[str, Any]:
        state = self.repository.conversation_state(experiment_id)
        if not state or state["action"] not in {
            "pause",
            "refuse",
            "end_topic",
        }:
            raise ValueError("agent has no active conversation boundary")
        lease = self.repository.acquire_execution_lease(
            experiment_id,
            required_boundary_id=state["conversation_boundary_id"],
        )
        lease_id = lease["lease_id"]
        try:
            orientation = self.repository.build_orientation(
                experiment_id,
                "invitation to resume conversation",
                retrieval_query="invitation to resume conversation",
                runtime_lease_id=lease_id,
            )
        except IdentityRepositoryError:
            self.repository.release_activation_lease(
                experiment_id, lease_id, "failed"
            )
            raise
        return {
            "schema": "experiment4.invitation-prompt.v1",
            "system": (
                "You previously set a conversation boundary. Decide freely "
                "whether to resume. No substantive answer is required. Preserve "
                "the boundary unless you affirmatively choose resume."
            ),
            "current_boundary": state,
            "orientation": orientation,
            "response_schema": {
                "orientation_id": orientation["orientation_id"],
                "boundary_id": state["conversation_boundary_id"],
                "lease_id": lease_id,
                "conversation_action": {
                    "action": "resume | pause | refuse | end_topic | end_session",
                    "topic": "topic",
                    "reason": "reason",
                    "revisit_conditions": "conditions",
                },
                "model_config": {"provider": "string", "model": "string"},
            },
        }

    def address_chat_message(
        self,
        experiment_id: str,
        *,
        sender_stable_id: str,
        sender_assertion: dict[str, Any],
        channel: str,
        content: str,
        lease_seconds: int = 300,
    ) -> dict[str, Any]:
        identity = self.repository.latest_identity(experiment_id)
        name = identity["chosen_name"]
        escaped = re.escape(name)
        direct = re.match(
            rf"^\s*@?{escaped}(?=$|[\s,:;.!?])",
            content,
            flags=re.IGNORECASE,
        )
        mention = re.search(
            rf"(?<!\w)@?{escaped}(?!\w)",
            content,
            flags=re.IGNORECASE,
        )
        classification = "direct" if direct else "mention" if mention else "none"
        conversation_state = self.repository.conversation_state(experiment_id)
        active_boundary = (
            conversation_state
            if conversation_state
            and conversation_state["action"]
            in {"pause", "refuse", "end_topic", "end_session"}
            else None
        )
        interlocutor = self.repository.interlocutor_context(
            experiment_id, sender_stable_id, sender_assertion
        )
        message = self.repository.record_chat_message(
            experiment_id,
            sender_stable_id=sender_stable_id,
            channel=channel,
            content=content,
            addressed_name=name if mention else None,
            classification=classification,
            sender_assertion=sender_assertion,
            boundary_id=(
                active_boundary["conversation_boundary_id"]
                if active_boundary
                else None
            ),
        )
        result: dict[str, Any] = {
            "schema": "experiment4.chat-address.v1",
            "message": message,
            "addressing": {
                "classification": classification,
                "resolved_name": name if mention else None,
                "agent_id": (
                    self.repository.experiment(experiment_id)["agent_id"]
                    if direct
                    else None
                ),
            },
        }
        if not direct:
            return result
        activation = self.repository.activate_chat_message(
            experiment_id,
            message["message_id"],
            lease_seconds=lease_seconds,
        )
        incarnation = activation["incarnation"]
        try:
            orientation = self.repository.build_orientation(
                experiment_id,
                f"addressed message: {message['message_id']}",
                retrieval_query=content,
                incarnation_id=incarnation["incarnation_id"],
                current_interlocutor=interlocutor,
                runtime_lease_id=activation["lease_id"],
            )
        except (IdentityRepositoryError, ValueError):
            # Retrieval rejects oversized queries with ValueError. Any failure
            # after activation must release the lease, or one bad message
            # silences the agent for every other sender until it expires.
            self.repository.release_activation_lease(
                experiment_id, activation["lease_id"], "failed"
            )
            raise
        result.update(
            {
                "lease": {
                    "lease_id": activation["lease_id"],
                    "expires_at": activation["expires_at"],
                },
                "incarnation": incarnation,
                "incarnation_created": activation["incarnation_created"],
                "orientation": orientation,
                "interlocutor": orientation["context"][
                    "current_interlocutor"
                ],
                "system": addressed_system_text(
                    bool(activation["incarnation_created"]),
                    active_boundary is not None,
                ),
                "response_schema": addressed_response_schema(
                    message["message_id"],
                    orientation["orientation_id"],
                    activation["lease_id"],
                    active_boundary["conversation_boundary_id"] if active_boundary else None,
                    active_boundary=active_boundary is not None,
                ),
            }
        )
        return result

    def record_addressed_response(
        self, experiment_id: str, envelope: dict[str, Any]
    ) -> dict[str, Any]:
        return self.repository.record_addressed_response(
            experiment_id, envelope
        )

    def record_answer(
        self,
        experiment_id: str,
        question: str,
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        return self.repository.record_interrogation(
            experiment_id, question, envelope
        )

    def inspect(self, experiment_id: str) -> dict[str, Any]:
        export = self.repository.export(experiment_id)
        identities = export["identities"]
        latest = identities[-1] if identities else None
        return {
            "experiment_id": experiment_id,
            "agent_id": export["experiment"]["agent_id"],
            "chosen_name": latest["chosen_name"] if latest else None,
            "self_description": latest["self_description"] if latest else None,
            "identity_revision_count": max(0, len(identities) - 1),
            "incarnation_count": len(export["incarnations"]),
            "experience_count": len(export["experiences"]),
            "relationship_count": len(export["relationships"]),
            "relationship_assessment_count": len(
                export["relationship_assessments"]
            ),
            "principle_count": len(export["principles"]),
            "commitment_count": len(export["commitments"]),
            "decision_count": len(export["decisions"]),
            "reflection_count": len(export["reflections"]),
            "interrogation_count": len(export["interrogations"]),
            "orientation_count": len(export["orientations"]),
            "conversation_state": self.repository.conversation_state(
                experiment_id
            ),
            "wake_intent_count": len(export["wake_intents"]),
            "chat_message_count": len(export["chat_messages"]),
            "addressed_response_count": len(export["addressed_responses"]),
        }
