"""Tool-calling agent loop driven by a scripted (offline) model.

Spec: docs/specs/agent.md
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

SYSTEM_PROMPT = (
    "You are Forest, the Alpine Supply Co. support agent. Only state order facts "
    "that came back from a tool. Hand off to a human when you cannot help."
)

MONEY_RE = re.compile(r"\$(\d+)\.(\d{2})")


class ToolError(Exception):
    pass


@dataclass(frozen=True)
class Tool:
    name: str
    fn: Callable[..., Any]
    required: tuple[str, ...] = ()
    types: dict[str, type] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict


@dataclass(frozen=True)
class ModelTurn:
    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


class ScriptedModel:
    """Replays a fixed list of turns; raises if the agent asks for more."""

    def __init__(self, turns: list[ModelTurn]):
        self._turns = list(turns)
        self.calls = 0
        self.seen_messages: list[list[dict]] = []

    def next(self, messages: list[dict]) -> ModelTurn:
        self.calls += 1
        self.seen_messages.append([dict(m) for m in messages])
        if not self._turns:
            raise RuntimeError("script exhausted")
        return self._turns.pop(0)


@dataclass
class AgentResult:
    text: str
    escalated: bool = False
    steps: int = 0
    tool_results: list[dict] = field(default_factory=list)


class AgentLoop:
    def __init__(
        self,
        model: ScriptedModel,
        tools: list[Tool],
        *,
        max_steps: int = 6,
        max_history: int = 12,
    ):
        self.model = model
        self.tools = {tool.name: tool for tool in tools}
        self.max_steps = max_steps
        self.max_history = max_history
        self.memory: dict[str, Any] = {"ordered_items": []}

    def run(self, history: list[dict], user_message: str) -> AgentResult:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": user_message}]
        result = AgentResult(text="")
        for step in range(1, self.max_steps + 1):
            result.steps = step
            messages = self._trim(messages)
            turn = self.model.next(messages)

            if turn.text is not None and not turn.tool_calls:
                result.text = self._ground(turn.text, result.tool_results)
                return result

            for call in turn.tool_calls:
                if call.name == "handoff":
                    result.text = call.args.get("message", "Connecting you with a teammate.")
                    result.escalated = True
                    return result
                observation = self._execute(call)
                result.tool_results.append({"tool": call.name, "args": call.args, "result": observation})
                self._remember(call.name, observation)
                messages.append({"role": "assistant", "content": f"call {call.name}({json.dumps(call.args, sort_keys=True)})"})
                messages.append({"role": "tool", "name": call.name, "content": json.dumps(observation, default=str)})

        result.text = "I was not able to finish that. Let me hand you to a teammate."
        result.escalated = True
        return result

    # -- pieces ---------------------------------------------------------------

    def _execute(self, call: ToolCall) -> Any:
        tool = self.tools.get(call.name)
        if tool is None:
            return {"error": f"unknown tool {call.name}"}
        missing = [name for name in tool.required if name not in call.args]
        if missing:
            return {"error": f"missing arguments: {', '.join(missing)}"}
        args = dict(call.args)
        for name, expected in tool.types.items():
            if name in args and not isinstance(args[name], expected):
                try:
                    args[name] = expected(args[name])
                except (TypeError, ValueError):
                    return {"error": f"argument {name} must be {expected.__name__}"}
        try:
            return tool.fn(**args)
        except ToolError as error:
            return {"error": str(error)}
        except Exception as error:  # noqa: BLE001 - tool failures become observations
            return {"error": f"{type(error).__name__}: {error}"}

    def _remember(self, tool_name: str, observation: Any) -> None:
        if tool_name != "lookup_order" or not isinstance(observation, dict):
            return
        items = observation.get("items") or []
        known = self.memory["ordered_items"]
        for item in items:
            sku = item.get("sku")
            if sku and sku not in known:
                known.append(sku)

    def _trim(self, messages: list[dict]) -> list[dict]:
        """Keep the system prompt plus the most recent max_history messages."""
        if len(messages) <= self.max_history + 1:
            return messages
        return [messages[0], *messages[-self.max_history :]]

    def _ground(self, text: str, tool_results: list[dict]) -> str:
        """Every dollar amount in the reply must have come from a tool result."""
        if not MONEY_RE.search(text):
            return text
        seen_cents = set(_collect_cents(r["result"] for r in tool_results))
        for dollars, cents in MONEY_RE.findall(text):
            if int(dollars) * 100 + int(cents) not in seen_cents:
                return "Let me double check that amount with a teammate before I quote it."
        return text


def _collect_cents(values) -> list[int]:
    found: list[int] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                if key.endswith("_cents") and isinstance(inner, int):
                    found.append(inner)
                else:
                    walk(inner)
        elif isinstance(value, (list, tuple)):
            for inner in value:
                walk(inner)

    for value in values:
        walk(value)
    return found
