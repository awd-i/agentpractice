from datetime import UTC, datetime, timedelta

import pytest

from supportdesk.orders import IllegalTransition, OrderLifecycle, OrderState, latest_transition

T0 = datetime(2026, 5, 1, tzinfo=UTC)


def t(days):
    return T0 + timedelta(days=days)


def delivered():
    life = OrderLifecycle("W1", 10000)
    life.replay([("pay", t(0)), ("fulfill", t(1)), ("ship", t(2)), ("deliver", t(4))])
    return life


def test_happy_path_to_delivered():
    life = delivered()
    assert life.state is OrderState.DELIVERED
    assert [h.event for h in life.history] == ["pay", "fulfill", "ship", "deliver"]
    assert latest_transition(life, "ship").at == t(2)


SHIPPED_EVENTS = [("pay", 0), ("fulfill", 1), ("ship", 2)]


@pytest.mark.parametrize("state_events", [SHIPPED_EVENTS, [*SHIPPED_EVENTS, ("deliver", 3)]])
def test_cannot_cancel_once_shipped(state_events):
    life = OrderLifecycle("W1", 10000)
    life.replay([(e, t(d)) for e, d in state_events])
    with pytest.raises(IllegalTransition):
        life.apply("cancel", t(5))
    assert life.state in (OrderState.SHIPPED, OrderState.DELIVERED)


def test_cancel_before_payment_refunds_nothing():
    life = OrderLifecycle("W1", 10000)
    life.apply("cancel", t(0))
    assert (life.state, life.refunded_cents) == (OrderState.CANCELLED, 0)


def test_cancel_after_payment_refunds_everything():
    life = OrderLifecycle("W1", 10000)
    life.apply("pay", t(0))
    life.apply("cancel", t(1))
    assert (life.state, life.refunded_cents, life.remaining_cents) == (OrderState.CANCELLED, 10000, 0)
    assert life.history[-1].note == "auto refund on cancel"


def test_terminal_states_reject_everything():
    life = OrderLifecycle("W1", 10000)
    life.apply("cancel", t(0))
    with pytest.raises(IllegalTransition):
        life.apply("pay", t(1))
    with pytest.raises(IllegalTransition):
        life.refund("r1", 100, t(1))


def test_skipping_a_step_is_illegal():
    life = OrderLifecycle("W1", 10000)
    with pytest.raises(IllegalTransition):
        life.apply("ship", t(0))
    assert life.state is OrderState.PLACED
    assert life.history == []


def test_partial_refund_keeps_order_delivered_until_fully_refunded():
    life = delivered()
    assert life.refund("r1", 4000, t(5)) is OrderState.DELIVERED
    assert life.remaining_cents == 6000
    assert life.refund("r2", 6000, t(6)) is OrderState.REFUNDED
    assert life.remaining_cents == 0


def test_refund_is_idempotent_per_refund_id():
    life = delivered()
    life.refund("r1", 4000, t(5))
    life.refund("r1", 4000, t(5))
    assert life.refunded_cents == 4000
    assert len([h for h in life.history if h.event == "refund"]) == 1


def test_refund_cannot_exceed_remaining():
    life = delivered()
    life.refund("r1", 9000, t(5))
    with pytest.raises(ValueError):
        life.refund("r2", 1001, t(6))
    assert life.refunded_cents == 9000
    with pytest.raises(ValueError):
        life.refund("r3", 0, t(6))


def test_refund_only_from_delivered_or_returned():
    life = OrderLifecycle("W1", 10000)
    life.replay([("pay", t(0)), ("fulfill", t(1)), ("ship", t(2))])
    with pytest.raises(IllegalTransition):
        life.refund("r1", 100, t(3))
    assert life.can("refund") is False
    life.apply("deliver", t(4))
    assert life.can("refund") is True
    life.apply("request_return", t(5))
    assert life.can("refund") is False
    life.apply("receive_return", t(8))
    assert life.refund("r1", 10000, t(9)) is OrderState.REFUNDED


def test_return_can_be_cancelled_back_to_delivered():
    life = delivered()
    life.apply("request_return", t(5))
    assert life.apply("cancel_return", t(6)) is OrderState.DELIVERED
    assert life.history[-1].from_state is OrderState.RETURN_REQUESTED


def test_can_reports_legal_events():
    life = OrderLifecycle("W1", 10000)
    assert life.can("pay") and life.can("cancel")
    assert not life.can("ship") and not life.can("refund")
