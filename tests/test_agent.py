from supportdesk.agent import SYSTEM_PROMPT, AgentLoop, ModelTurn, ScriptedModel, Tool, ToolCall, ToolError

ORDER = {"order_id": "W1001", "status": "delivered", "items": [{"sku": "AP-TENT-02"}], "total_cents": 21500}
ORDER2 = {"order_id": "W1002", "status": "shipped", "items": [{"sku": "AP-SOCK-M"}, {"sku": "AP-TENT-02"}], "total_cents": 1800}


def lookup_order(order_id: str):
    if order_id == "W1001":
        return ORDER
    if order_id == "W1002":
        return ORDER2
    raise ToolError(f"order {order_id} not found")


def decide_refund(order_id: str, quantity: int):
    assert isinstance(quantity, int)
    return {"outcome": "approved", "amount_cents": 18000}


def explode():
    raise RuntimeError("database on fire")


TOOLS = [
    Tool("lookup_order", lookup_order, required=("order_id",), types={"order_id": str}),
    Tool("decide_refund", decide_refund, required=("order_id", "quantity"), types={"quantity": int}),
    Tool("explode", explode),
]


def agent(turns, **kwargs):
    return AgentLoop(ScriptedModel(turns), TOOLS, **kwargs)


def test_tool_call_then_answer():
    loop = agent([
        ModelTurn(tool_calls=(ToolCall("lookup_order", {"order_id": "W1001"}),)),
        ModelTurn(text="Order W1001 is delivered."),
    ])
    result = loop.run([], "where is W1001?")
    assert result.text == "Order W1001 is delivered."
    assert result.steps == 2 and result.escalated is False
    assert result.tool_results[0]["result"] == ORDER


def test_tool_messages_are_fed_back_to_the_model():
    model = ScriptedModel([
        ModelTurn(tool_calls=(ToolCall("lookup_order", {"order_id": "W1001"}),)),
        ModelTurn(text="ok"),
    ])
    AgentLoop(model, TOOLS).run([], "hi")
    second_call_messages = model.seen_messages[1]
    assert second_call_messages[0]["content"] == SYSTEM_PROMPT
    assert second_call_messages[-1]["role"] == "tool"
    assert "delivered" in second_call_messages[-1]["content"]


def test_tool_errors_become_observations_not_crashes():
    loop = agent([
        ModelTurn(tool_calls=(ToolCall("lookup_order", {"order_id": "W9"}),)),
        ModelTurn(tool_calls=(ToolCall("explode", {}),)),
        ModelTurn(tool_calls=(ToolCall("nonexistent", {}),)),
        ModelTurn(tool_calls=(ToolCall("lookup_order", {}),)),
        ModelTurn(text="Sorry, I could not find that order."),
    ])
    result = loop.run([], "where is W9?")
    errors = [r["result"]["error"] for r in result.tool_results]
    assert errors[0] == "order W9 not found"
    assert errors[1] == "RuntimeError: database on fire"
    assert errors[2] == "unknown tool nonexistent"
    assert errors[3] == "missing arguments: order_id"
    assert result.text.startswith("Sorry")


def test_argument_types_are_coerced_or_rejected():
    loop = agent([
        ModelTurn(tool_calls=(ToolCall("decide_refund", {"order_id": "W1001", "quantity": "2"}),)),
        ModelTurn(tool_calls=(ToolCall("decide_refund", {"order_id": "W1001", "quantity": "two"}),)),
        ModelTurn(text="done"),
    ])
    result = loop.run([], "refund two")
    assert result.tool_results[0]["result"]["outcome"] == "approved"
    assert result.tool_results[1]["result"] == {"error": "argument quantity must be int"}


def test_loop_stops_after_exactly_max_steps_and_escalates():
    model = ScriptedModel([ModelTurn(tool_calls=(ToolCall("lookup_order", {"order_id": "W1001"}),))] * 10)
    result = AgentLoop(model, TOOLS, max_steps=3).run([], "loop")
    assert result.escalated is True
    assert result.steps == 3
    assert model.calls == 3


def test_handoff_tool_ends_the_loop_immediately():
    model = ScriptedModel([
        ModelTurn(tool_calls=(ToolCall("handoff", {"message": "Passing you to Sam."}), ToolCall("explode", {}))),
        ModelTurn(text="should not be reached"),
    ])
    result = AgentLoop(model, TOOLS).run([], "human please")
    assert (result.text, result.escalated) == ("Passing you to Sam.", True)
    assert result.tool_results == []
    assert model.calls == 1


def test_history_is_trimmed_but_system_prompt_survives():
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(30)]
    model = ScriptedModel([ModelTurn(text="ok")])
    AgentLoop(model, TOOLS, max_history=6).run(history, "latest")
    sent = model.seen_messages[0]
    assert len(sent) == 7
    assert sent[0]["content"] == SYSTEM_PROMPT
    assert sent[-1]["content"] == "latest"
    assert sent[1]["content"] == "m25"


def test_short_history_is_not_trimmed():
    model = ScriptedModel([ModelTurn(text="ok")])
    AgentLoop(model, TOOLS, max_history=6).run([{"role": "user", "content": "a"}], "b")
    assert [m["content"] for m in model.seen_messages[0]] == [SYSTEM_PROMPT, "a", "b"]


def test_quoted_amounts_must_come_from_tool_results():
    loop = agent([
        ModelTurn(tool_calls=(ToolCall("decide_refund", {"order_id": "W1001", "quantity": 1}),)),
        ModelTurn(text="I can refund $180.00 today."),
    ])
    assert loop.run([], "refund").text == "I can refund $180.00 today."
    loop = agent([
        ModelTurn(tool_calls=(ToolCall("decide_refund", {"order_id": "W1001", "quantity": 1}),)),
        ModelTurn(text="I can refund $215.00 today."),
    ])
    assert loop.run([], "refund").text.startswith("Let me double check")
    loop = agent([ModelTurn(text="Our tents start at $99.00.")])
    assert loop.run([], "price?").text.startswith("Let me double check")


def test_memory_of_ordered_items_merges_across_lookups():
    loop = agent([
        ModelTurn(tool_calls=(ToolCall("lookup_order", {"order_id": "W1001"}),)),
        ModelTurn(tool_calls=(ToolCall("lookup_order", {"order_id": "W1002"}),)),
        ModelTurn(text="ok"),
    ])
    loop.run([], "my orders")
    assert loop.memory["ordered_items"] == ["AP-TENT-02", "AP-SOCK-M"]
