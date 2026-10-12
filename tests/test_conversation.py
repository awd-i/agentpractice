import pytest

from supportdesk.conversation import (
    MAX_VERIFY_ATTEMPTS,
    ConversationMachine,
    Event,
    InvalidTransition,
    State,
    classify_intent,
    extract_slots,
    is_affirmative,
)


def user(text):
    return Event("user_message", text=text)


def tool(name, result):
    return Event("tool_result", tool=name, result=result)


ORDER = {"order_id": "W1001", "status": "delivered", "items": [{"sku": "AP-TENT-02", "quantity": 1}]}


def kinds(actions):
    return [a.kind for a in actions]


def tools(actions):
    return [a.tool for a in actions if a.kind == "tool_call"]


def to_confirming():
    m = ConversationMachine()
    m.handle(user("I want a refund"))
    m.handle(user("alice@example.com, order #W1001"))
    m.handle(tool("verify_identity", {"ok": True}))
    m.handle(tool("lookup_order", ORDER))
    m.handle(tool("decide_refund", {"outcome": "approved", "amount_cents": 18000}))
    assert m.state is State.CONFIRMING
    return m


@pytest.mark.parametrize(
    "text, intent",
    [
        ("I want a refund on my order", "refund"),
        ("Where is my order?", "order_status"),
        ("can i return this and get my money back", "refund"),
        ("Can you recommend a tent?", "product"),
        ("let me talk to a human", "human"),
        ("ok thanks, that's all", "bye"),
        ("blorp", "unknown"),
    ],
)
def test_classify_intent(text, intent):
    assert classify_intent(text) == intent


def test_extract_slots_merges_email_and_order_id():
    assert extract_slots("alice@Example.com and #w1001 please") == {"email": "alice@example.com", "order_id": "W1001"}
    assert extract_slots("W1001") == {"order_id": "W1001"}
    assert extract_slots("no ids here") == {}
    assert extract_slots("bob42@mail.com") == {"email": "bob42@mail.com"}


@pytest.mark.parametrize("text, expected", [("yes", True), ("Yes please", True), ("nope", False), ("No, cancel", False), ("maybe", None)])
def test_is_affirmative(text, expected):
    assert is_affirmative(text) is expected


def test_greeting_then_triage_asks_for_identity():
    m = ConversationMachine()
    actions = m.handle(user("I need a refund"))
    assert m.state is State.IDENTIFYING
    assert actions[0].text.startswith("Welcome")
    assert "email and order id" in actions[-1].text


def test_identity_slots_accumulate_across_messages():
    m = ConversationMachine()
    m.handle(user("where is my order"))
    actions = m.handle(user("my email is alice@example.com"))
    assert m.state is State.IDENTIFYING
    assert "order id" in actions[0].text and "email" not in actions[0].text
    actions = m.handle(user("it's #W1001"))
    assert m.state is State.VERIFYING
    assert actions[0].args == {"email": "alice@example.com", "order_id": "W1001"}


def test_status_flow_returns_to_triage():
    m = ConversationMachine()
    m.handle(user("track my order alice@example.com W1001"))
    assert m.state is State.VERIFYING
    m.handle(tool("verify_identity", {"ok": True}))
    assert m.state is State.LOOKUP
    actions = m.handle(tool("lookup_order", {**ORDER, "status": "return_requested"}))
    assert m.state is State.TRIAGE
    assert actions[0].text == "Order W1001 is return requested."


def test_failed_verification_retries_then_escalates():
    m = ConversationMachine()
    m.handle(user("refund alice@example.com W1001"))
    for attempt in range(1, MAX_VERIFY_ATTEMPTS):
        actions = m.handle(tool("verify_identity", {"ok": False}))
        assert m.state is State.IDENTIFYING
        assert f"({MAX_VERIFY_ATTEMPTS - attempt} attempts left)" in actions[0].text
        assert m.context["slots"] == {"email": "alice@example.com"}
        m.handle(user("W1001"))
        assert m.state is State.VERIFYING
    actions = m.handle(tool("verify_identity", {"ok": False}))
    assert m.state is State.ESCALATED
    assert kinds(actions) == ["handoff"]


def test_successful_verification_resets_attempt_counter():
    m = ConversationMachine()
    m.handle(user("refund alice@example.com W1001"))
    m.handle(tool("verify_identity", {"ok": False}))
    m.handle(user("W1001"))
    m.handle(tool("verify_identity", {"ok": True}))
    assert m.context["verify_attempts"] == 0


def test_refund_flow_confirm_yes_issues_refund():
    m = to_confirming()
    actions = m.handle(user("yes"))
    assert m.state is State.RESOLVING
    assert tools(actions) == ["issue_refund"]
    assert actions[0].args == {"order_id": "W1001", "amount_cents": 18000}
    actions = m.handle(tool("issue_refund", {"amount_cents": 18000}))
    assert m.state is State.TRIAGE
    assert "$180.00" in actions[0].text


def test_refund_flow_confirm_no_cancels():
    m = to_confirming()
    actions = m.handle(user("no"))
    assert m.state is State.TRIAGE
    assert m.context["pending_refund"] is None
    assert "nothing has been refunded" in actions[0].text


def test_unclear_confirmation_stays_in_confirming():
    m = to_confirming()
    actions = m.handle(user("hmm"))
    assert m.state is State.CONFIRMING
    assert "yes or no" in actions[0].text
    assert m.context["pending_refund"] is not None


def test_timeout_while_confirming_cancels_the_refund_and_closes():
    m = to_confirming()
    actions = m.handle(Event("timeout"))
    assert m.state is State.CLOSED
    assert m.context["pending_refund"] is None
    assert "not issued" in actions[0].text


def test_timeout_elsewhere_just_closes():
    m = ConversationMachine()
    m.handle(user("hello"))
    actions = m.handle(Event("timeout"))
    assert m.state is State.CLOSED
    assert len(actions) == 1


def test_denied_refund_explains_and_returns_to_triage():
    m = ConversationMachine()
    m.handle(user("refund alice@example.com W1001"))
    m.handle(tool("verify_identity", {"ok": True}))
    m.handle(tool("lookup_order", ORDER))
    actions = m.handle(tool("decide_refund", {"outcome": "denied", "reasons": ["outside the 14 day window for basic"]}))
    assert m.state is State.TRIAGE
    assert "outside the 14 day window" in actions[0].text


def test_needs_review_escalates():
    m = ConversationMachine()
    m.handle(user("refund alice@example.com W1001"))
    m.handle(tool("verify_identity", {"ok": True}))
    m.handle(tool("lookup_order", ORDER))
    actions = m.handle(tool("decide_refund", {"outcome": "needs_review", "amount_cents": 54000}))
    assert m.state is State.ESCALATED
    assert kinds(actions) == ["handoff"]


def test_product_question_searches_and_returns_to_triage():
    m = ConversationMachine()
    actions = m.handle(user("can you recommend a tent"))
    assert m.state is State.RESOLVING
    assert tools(actions) == ["search_products"]
    actions = m.handle(tool("search_products", [{"name": "Ridgeline 2P Tent"}, {"name": "Ultralight Tarp"}]))
    assert m.state is State.TRIAGE
    assert actions[0].text == "You might like: Ridgeline 2P Tent, Ultralight Tarp."


def test_two_unclear_messages_are_tolerated_third_escalates():
    m = ConversationMachine()
    m.handle(user("hello there"))
    assert m.state is State.TRIAGE
    m.handle(user("blorp"))
    assert m.state is State.TRIAGE
    actions = m.handle(user("blorp again"))
    assert m.state is State.ESCALATED
    assert kinds(actions) == ["handoff"]


def test_human_request_escalates_from_identifying_too():
    m = ConversationMachine()
    m.handle(user("refund please"))
    actions = m.handle(user("just give me a person"))
    assert m.state is State.ESCALATED
    assert kinds(actions) == ["handoff"]


def test_terminal_states_reject_events():
    m = ConversationMachine()
    m.handle(user("bye"))
    assert m.state is State.CLOSED
    with pytest.raises(InvalidTransition):
        m.handle(user("hello?"))


def test_unexpected_tool_result_is_rejected_and_state_is_unchanged():
    m = ConversationMachine()
    m.handle(user("refund alice@example.com W1001"))
    before = (m.state, dict(m.context["slots"]), m.context["verify_attempts"])
    with pytest.raises(InvalidTransition):
        m.handle(tool("lookup_order", ORDER))
    assert (m.state, dict(m.context["slots"]), m.context["verify_attempts"]) == before


def test_failed_step_does_not_leak_partial_context():
    m = ConversationMachine()
    m.handle(user("track my order alice@example.com W1001"))
    m.handle(tool("verify_identity", {"ok": True}))
    with pytest.raises(KeyError):
        m.handle(tool("lookup_order", {"order_id": "W1001"}))  # missing status -> KeyError inside handler
    assert m.state is State.LOOKUP
    assert m.context["order"] is None


def test_reset_clears_everything():
    m = to_confirming()
    m.reset()
    assert m.state is State.GREETING
    assert m.context["slots"] == {} and m.context["pending_refund"] is None
    assert m.context["verify_attempts"] == 0 and m.context["clarifications"] == 0
    assert m.transcript == []


def test_transcript_records_every_action():
    m = to_confirming()
    assert len(m.transcript) == sum(1 for _ in m.transcript)
    assert m.transcript[0].text.startswith("Welcome")
    assert tools(m.transcript) == ["verify_identity", "lookup_order", "decide_refund"]
