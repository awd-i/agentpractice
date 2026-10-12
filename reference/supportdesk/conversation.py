"""Conversation state machine for the support agent.

Spec and diagram: docs/specs/conversation.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class State(str, Enum):
    GREETING = "greeting"
    TRIAGE = "triage"
    IDENTIFYING = "identifying"
    VERIFYING = "verifying"
    LOOKUP = "lookup"
    RESOLVING = "resolving"
    CONFIRMING = "confirming"
    ESCALATED = "escalated"
    CLOSED = "closed"


TERMINAL_STATES = {State.ESCALATED, State.CLOSED}

ALLOWED_TRANSITIONS: dict[State, set[State]] = {
    State.GREETING: {State.TRIAGE, State.CLOSED},
    State.TRIAGE: {State.TRIAGE, State.IDENTIFYING, State.RESOLVING, State.ESCALATED, State.CLOSED},
    State.IDENTIFYING: {State.IDENTIFYING, State.VERIFYING, State.ESCALATED, State.CLOSED},
    State.VERIFYING: {State.IDENTIFYING, State.LOOKUP, State.ESCALATED, State.CLOSED},
    State.LOOKUP: {State.TRIAGE, State.RESOLVING, State.ESCALATED, State.CLOSED},
    State.RESOLVING: {State.TRIAGE, State.CONFIRMING, State.ESCALATED, State.CLOSED},
    State.CONFIRMING: {State.TRIAGE, State.RESOLVING, State.ESCALATED, State.CLOSED},
    State.ESCALATED: set(),
    State.CLOSED: set(),
}

MAX_VERIFY_ATTEMPTS = 3
MAX_CLARIFICATIONS = 2

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
ORDER_RE = re.compile(r"#?\b([A-Za-z]\d{3,})\b")
YES_WORDS = {"yes", "y", "yeah", "yep", "confirm", "sure", "ok", "okay", "please do"}
NO_WORDS = {"no", "n", "nope", "cancel", "don't", "dont", "stop"}


class InvalidTransition(Exception):
    pass


@dataclass(frozen=True)
class Event:
    kind: str  # "user_message" | "tool_result" | "timeout"
    text: str = ""
    tool: str = ""
    result: Any = None


@dataclass(frozen=True)
class Action:
    kind: str  # "reply" | "tool_call" | "handoff"
    text: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)


def classify_intent(text: str) -> str:
    """Keyword intent classifier. Refund beats status when both appear."""
    lowered = text.lower()
    if any(w in lowered for w in ("human", "agent", "representative", "person")):
        return "human"
    if any(w in lowered for w in ("refund", "return", "money back")):
        return "refund"
    if any(w in lowered for w in ("where is", "status", "track", "shipped", "arrive")):
        return "order_status"
    if any(w in lowered for w in ("recommend", "looking for", "do you have", "suggest")):
        return "product"
    if any(w in lowered for w in ("bye", "thanks, that's all", "that's all", "goodbye")):
        return "bye"
    return "unknown"


def extract_slots(text: str) -> dict[str, str]:
    """Pull an email and/or order id out of free text. Missing keys are omitted."""
    slots: dict[str, str] = {}
    email = EMAIL_RE.search(text)
    if email:
        slots["email"] = email.group(0).lower()
    without_email = EMAIL_RE.sub(" ", text)
    order = ORDER_RE.search(without_email)
    if order:
        slots["order_id"] = order.group(1).upper()
    return slots


def is_affirmative(text: str) -> bool | None:
    words = text.strip().lower().rstrip("!.")
    first = re.split(r"[^a-z']+", words)[0] if words else ""
    if words in YES_WORDS or first in YES_WORDS:
        return True
    if words in NO_WORDS or first in NO_WORDS:
        return False
    return None


class ConversationMachine:
    def __init__(self) -> None:
        self.state = State.GREETING
        self.context: dict[str, Any] = self._fresh_context()
        self.transcript: list[Action] = []

    @staticmethod
    def _fresh_context() -> dict[str, Any]:
        return {
            "intent": None,
            "slots": {},
            "verify_attempts": 0,
            "clarifications": 0,
            "order": None,
            "pending_refund": None,
        }

    def reset(self) -> None:
        self.state = State.GREETING
        self.context = self._fresh_context()
        self.transcript = []

    # -- transition plumbing ------------------------------------------------

    def _go(self, new_state: State) -> None:
        if new_state not in ALLOWED_TRANSITIONS[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {new_state.value}")
        self.state = new_state

    def handle(self, event: Event) -> list[Action]:
        """Dispatch one event. Either the whole step applies or none of it."""
        if self.state in TERMINAL_STATES:
            raise InvalidTransition(f"conversation is {self.state.value}")
        before_state = self.state
        before_context = _deep_copy(self.context)
        try:
            actions = self._dispatch(event)
        except Exception:
            self.state = before_state
            self.context = before_context
            raise
        self.transcript.extend(actions)
        return actions

    def _dispatch(self, event: Event) -> list[Action]:
        if event.kind == "timeout":
            return self._on_timeout()
        handler = getattr(self, f"_in_{self.state.value}")
        return handler(event)

    # -- per state handlers -------------------------------------------------

    def _on_timeout(self) -> list[Action]:
        actions: list[Action] = []
        if self.state == State.CONFIRMING:
            self.context["pending_refund"] = None
            actions.append(Action("reply", "No reply received, so I have not issued the refund."))
        actions.append(Action("reply", "Closing this chat. Come back any time."))
        self._go(State.CLOSED)
        return actions

    def _in_greeting(self, event: Event) -> list[Action]:
        actions = [Action("reply", "Welcome to Alpine Supply Co. How can I help today?")]
        self._go(State.TRIAGE)
        if event.kind == "user_message" and event.text.strip():
            actions.extend(self._in_triage(event))
        return actions

    def _in_triage(self, event: Event) -> list[Action]:
        if event.kind != "user_message":
            raise InvalidTransition(f"unexpected {event.kind} in triage")
        intent = classify_intent(event.text)
        self._merge_slots(extract_slots(event.text))

        if intent == "human":
            self._go(State.ESCALATED)
            return [Action("handoff", "Connecting you with a teammate.")]
        if intent == "bye":
            self._go(State.CLOSED)
            return [Action("reply", "Thanks for shopping with Alpine Supply Co.")]
        if intent == "product":
            self.context["intent"] = intent
            self._go(State.RESOLVING)
            return [Action("tool_call", tool="search_products", args={"query": event.text})]
        if intent in ("refund", "order_status"):
            self.context["intent"] = intent
            self._go(State.IDENTIFYING)
            return self._ask_for_missing_slots(prefix="Happy to help with that. ")

        self.context["clarifications"] += 1
        if self.context["clarifications"] > MAX_CLARIFICATIONS:
            self._go(State.ESCALATED)
            return [Action("handoff", "Let me get a teammate who can help.")]
        self._go(State.TRIAGE)
        return [Action("reply", "I can help with orders, refunds and gear questions. Which is it?")]

    def _in_identifying(self, event: Event) -> list[Action]:
        if event.kind != "user_message":
            raise InvalidTransition(f"unexpected {event.kind} in identifying")
        if classify_intent(event.text) == "human":
            self._go(State.ESCALATED)
            return [Action("handoff", "Connecting you with a teammate.")]
        self._merge_slots(extract_slots(event.text))
        return self._ask_for_missing_slots()

    def _ask_for_missing_slots(self, prefix: str = "") -> list[Action]:
        slots = self.context["slots"]
        missing = [name for name in ("email", "order_id") if not slots.get(name)]
        if missing:
            self._go(State.IDENTIFYING)
            pretty = " and ".join(m.replace("_", " ") for m in missing)
            return [Action("reply", f"{prefix}Please share the {pretty} on the order.")]
        self._go(State.VERIFYING)
        return [
            Action(
                "tool_call",
                tool="verify_identity",
                args={"email": slots["email"], "order_id": slots["order_id"]},
            )
        ]

    def _in_verifying(self, event: Event) -> list[Action]:
        if event.kind != "tool_result" or event.tool != "verify_identity":
            raise InvalidTransition(f"unexpected {event.kind}:{event.tool} in verifying")
        if event.result.get("ok"):
            self.context["verify_attempts"] = 0
            self._go(State.LOOKUP)
            return [
                Action("tool_call", tool="lookup_order", args={"order_id": self.context["slots"]["order_id"]})
            ]
        self.context["verify_attempts"] += 1
        if self.context["verify_attempts"] >= MAX_VERIFY_ATTEMPTS:
            self._go(State.ESCALATED)
            return [Action("handoff", "I could not verify those details. A teammate will take over.")]
        self.context["slots"].pop("order_id", None)
        self._go(State.IDENTIFYING)
        remaining = MAX_VERIFY_ATTEMPTS - self.context["verify_attempts"]
        return [
            Action(
                "reply",
                f"Those details did not match our records ({remaining} attempts left). "
                "What is the order number?",
            )
        ]

    def _in_lookup(self, event: Event) -> list[Action]:
        if event.kind != "tool_result" or event.tool != "lookup_order":
            raise InvalidTransition(f"unexpected {event.kind}:{event.tool} in lookup")
        order = event.result
        if order is None:
            self._go(State.ESCALATED)
            return [Action("handoff", "I cannot find that order. A teammate will take over.")]
        self.context["order"] = order
        if self.context["intent"] == "refund":
            self._go(State.RESOLVING)
            return [Action("tool_call", tool="decide_refund", args={"order_id": order["order_id"]})]
        self._go(State.TRIAGE)
        return [
            Action("reply", f"Order {order['order_id']} is {order['status'].replace('_', ' ')}."),
            Action("reply", "Anything else I can help with?"),
        ]

    def _in_resolving(self, event: Event) -> list[Action]:
        if event.kind != "tool_result":
            raise InvalidTransition(f"unexpected {event.kind} in resolving")
        if event.tool == "search_products":
            names = ", ".join(p["name"] for p in event.result) or "nothing in stock right now"
            self._go(State.TRIAGE)
            return [Action("reply", f"You might like: {names}."), Action("reply", "Anything else?")]
        if event.tool == "decide_refund":
            decision = event.result
            if decision["outcome"] == "approved":
                self.context["pending_refund"] = decision
                self._go(State.CONFIRMING)
                return [
                    Action(
                        "reply",
                        f"I can refund {_dollars(decision['amount_cents'])} to your original payment method. "
                        "Shall I go ahead? (yes/no)",
                    )
                ]
            if decision["outcome"] == "needs_review":
                self._go(State.ESCALATED)
                return [Action("handoff", "This refund needs a manager's approval. Handing you over.")]
            self._go(State.TRIAGE)
            why = "; ".join(decision.get("reasons", [])) or "it is outside our policy"
            return [Action("reply", f"I cannot refund that because {why}."), Action("reply", "Anything else?")]
        if event.tool == "issue_refund":
            self._go(State.TRIAGE)
            return [
                Action("reply", f"Done. {_dollars(event.result['amount_cents'])} is on its way back to you."),
                Action("reply", "Anything else?"),
            ]
        raise InvalidTransition(f"unexpected tool {event.tool} in resolving")

    def _in_confirming(self, event: Event) -> list[Action]:
        if event.kind != "user_message":
            raise InvalidTransition(f"unexpected {event.kind} in confirming")
        answer = is_affirmative(event.text)
        pending = self.context["pending_refund"]
        if answer is True:
            self.context["pending_refund"] = None
            self._go(State.RESOLVING)
            return [
                Action(
                    "tool_call",
                    tool="issue_refund",
                    args={"order_id": self.context["order"]["order_id"], "amount_cents": pending["amount_cents"]},
                )
            ]
        if answer is False:
            self.context["pending_refund"] = None
            self._go(State.TRIAGE)
            return [Action("reply", "No problem, nothing has been refunded."), Action("reply", "Anything else?")]
        return [Action("reply", "Please answer yes or no so I know whether to issue the refund.")]

    # -- helpers --------------------------------------------------------------

    def _merge_slots(self, found: dict[str, str]) -> None:
        """New values win; missing keys never erase what we already know."""
        for key, value in found.items():
            if value:
                self.context["slots"][key] = value


def _dollars(cents: int) -> str:
    return f"${cents // 100}.{cents % 100:02d}"


def _deep_copy(context: dict[str, Any]) -> dict[str, Any]:
    import copy

    return copy.deepcopy(context)
