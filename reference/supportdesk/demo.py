"""Scenario runner: reproduce the tickets by hand.

    python -m supportdesk.demo               list scenarios
    python -m supportdesk.demo refund-chat   run one
"""
from __future__ import annotations

import random
import sys
from datetime import UTC, datetime, time, timedelta

from . import agent as agent_mod
from .api_client import ApiError, ApiTimeout, FakeTransport, OrdersAPI, Response, RetryPolicy
from .catalog import chunk, mask_email, normalize_order_id, normalize_sku, search_products, similar_products
from .conversation import ConversationMachine, Event
from .models import Customer, Order, OrderItem, Product, RefundRequest, Tier, format_cents
from .orders import IllegalTransition, OrderLifecycle
from .promotions import PACIFIC, Cart, Promotion, PromotionStore, apply_promotions
from .refund_policy import decide_refund

CATALOG = [
    Product("AP-TENT-02", "Ridgeline 2P Tent", 20000, ("tent", "camping", "shelter"), in_stock=4),
    Product("AP-TENT-04", "Ridgeline 4P Tent", 32000, ("tent", "camping", "shelter", "family"), in_stock=0),
    Product("AP-BAG-20", "Summit 20F Sleeping Bag", 15000, ("sleeping", "camping", "bag"), in_stock=7),
    Product("AP-STOVE-1", "Ember Canister Stove", 6000, ("stove", "camping", "cooking"), in_stock=2),
    Product("AP-SOCK-M", "Merino Trail Socks", 1800, ("socks", "hiking", "apparel"), in_stock=50),
    Product("AP-TARP-1", "Ultralight Tarp", 9000, ("tarp", "shelter", "camping"), in_stock=1),
]
DELIVERED = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
ORDER = Order(
    order_id="W1001",
    customer_id="C1",
    items=[OrderItem("AP-TENT-02", 1, 20000)],
    shipping_cents=1500,
    placed_at=DELIVERED - timedelta(days=4),
    delivered_at=DELIVERED,
    status="delivered",
)


def say(label: str, value) -> None:
    print(f"  {label:<34} {value}")


def chat(machine: ConversationMachine, event: Event) -> None:
    desc = event.text if event.kind == "user_message" else f"<{event.kind} {event.tool} {event.result}>"
    try:
        actions = machine.handle(event)
    except Exception as error:  # noqa: BLE001
        print(f"> {desc}\n  !! {type(error).__name__}: {error}   [state={machine.state.value}]")
        return
    print(f"> {desc}")
    for a in actions:
        if a.kind == "tool_call":
            print(f"  [tool] {a.tool}({a.args})")
        elif a.kind == "handoff":
            print(f"  [handoff] {a.text}")
        else:
            print(f"  bot: {a.text}")
    print(f"  [state={machine.state.value} slots={machine.context['slots']} pending={machine.context['pending_refund'] is not None}]")


def scenario_catalog() -> None:
    for raw in ("#w1001", "W01001", " w1001 "):
        try:
            say(f"normalize_order_id({raw!r})", normalize_order_id(raw))
        except ValueError as error:
            say(f"normalize_order_id({raw!r})", f"ValueError: {error}")
    say("normalize_sku('ap_tent_02')", normalize_sku("ap_tent_02"))
    say("chunk([1,2,3,4,5], 2)", chunk([1, 2, 3, 4, 5], 2))
    say("mask_email('alice.jones@example.com')", mask_email("alice.jones@example.com"))


def scenario_search() -> None:
    say("search 'camping tent'", [p.name for p in search_products(CATALOG, "camping tent")])
    say("similar to AP-TENT-02", [p.sku for p in similar_products(CATALOG, "AP-TENT-02")])


def scenario_policy() -> None:
    print(f"  {'tier':<8} {'day':>4} {'reason':<12} {'final':<6} {'outcome':<12} {'amount':>9} {'fee':>7} {'ship':>6}")
    cases = [
        (Tier.BASIC, 14, "changed_mind", False),
        (Tier.BASIC, 15, "changed_mind", False),
        (Tier.SILVER, 20, "changed_mind", False),
        (Tier.PREMIUM, 45, "changed_mind", False),
        (Tier.BASIC, 80, "defective", True),
        (Tier.PREMIUM, 3, "changed_mind", True),
        (Tier.BASIC, 3, "defective", False),
    ]
    for tier, day, reason, final in cases:
        items = [OrderItem("AP-TENT-02", 1, 20000, final_sale=final)]
        order = Order("W1001", "C1", items, 1500, DELIVERED - timedelta(days=4), DELIVERED, "delivered")
        cust = Customer("C1", "alice@example.com", "Alice", tier)
        req = RefundRequest("W1001", "AP-TENT-02", 1, reason, DELIVERED + timedelta(days=day))
        d = decide_refund(order, cust, req)
        print(
            f"  {tier.value:<8} {day:>4} {reason:<12} {str(final):<6} {d.outcome:<12} "
            f"{format_cents(d.amount_cents):>9} {format_cents(d.restocking_fee_cents):>7} {format_cents(d.shipping_refund_cents):>6}"
        )
    items = [OrderItem("AP-SOCK-M", 1, 1005)]
    order = Order("W1", "C1", items, 0, DELIVERED, DELIVERED, "delivered")
    for tier in (Tier.BASIC, Tier.SILVER):
        req = RefundRequest("W1", "AP-SOCK-M", 1, "changed_mind", DELIVERED)
        d = decide_refund(order, Customer("C1", "a@b.c", "A", tier), req)
        say(f"fee on $10.05 for {tier.value}", format_cents(d.restocking_fee_cents))
    big = Order("W1", "C1", [OrderItem("AP-TENT-02", 1, 50000)], 0, DELIVERED, DELIVERED, "delivered")
    d = decide_refund(big, Customer("C1", "a@b.c", "A", Tier.BASIC), RefundRequest("W1", "AP-TENT-02", 1, "defective", DELIVERED))
    say("basic, exactly $500 defective", d.outcome)
    shipped = Order("W1", "C1", [OrderItem("AP-TENT-02", 1, 20000)], 0, DELIVERED, None, "shipped")
    d = decide_refund(shipped, Customer("C1", "a@b.c", "A", Tier.BASIC), RefundRequest("W1", "AP-TENT-02", 1, "changed_mind", DELIVERED))
    say("shipped order", d.outcome)


def scenario_promo() -> None:
    store = PromotionStore(
        [
            Promotion("SAVE10", "percent", 10, min_subtotal_cents=5000),
            Promotion("FREESHIP", "free_shipping"),
            Promotion("VIP20", "percent", 20, min_tier=Tier.SILVER, max_discount_cents=3000),
            Promotion("FLAT5", "fixed", 500, single_use=True),
            Promotion("EARLY", "percent", 10, daily_window=(time(8, 0), time(10, 0))),
            Promotion("SUMMER", "percent", 15, starts=datetime(2026, 6, 1, tzinfo=PACIFIC), ends=datetime(2026, 7, 1, tzinfo=PACIFIC)),
        ]
    )
    now = datetime(2026, 6, 15, 16, 30, tzinfo=UTC)  # 09:30 Pacific

    def run(label, codes, **kw):
        cart = Cart(kw.pop("subtotal", 10000), 800, kw.pop("tier", Tier.BASIC), kw.pop("customer", "C1"), codes)
        r = apply_promotions(cart, kw.pop("now", now), store)
        say(label, f"applied={r.applied} rejected={r.rejected} total={format_cents(r.total_cents)}")

    run("EARLY at 16:30 UTC (09:30 PT)", ["EARLY"])
    run("EARLY at 09:30 UTC (02:30 PT)", ["EARLY"], now=datetime(2026, 6, 15, 9, 30, tzinfo=UTC))
    run("SUMMER at Jul 1 00:00 PT", ["SUMMER"], now=datetime(2026, 7, 1, 0, 0, tzinfo=PACIFIC))
    run("SAVE10 on $50.00", ["SAVE10"], subtotal=5000)
    run("SAVE10 then FLAT5", ["SAVE10", "FLAT5"])
    run("FLAT5 alone afterwards", ["FLAT5"])
    run("FLAT5 on a $3.00 cart", ["FLAT5"], subtotal=300, customer="C2")
    run("VIP20 as premium", ["VIP20"], tier=Tier.PREMIUM)


def scenario_lifecycle() -> None:
    t0 = datetime(2026, 5, 1, tzinfo=UTC)

    def attempt(label, fn):
        try:
            say(label, fn())
        except (IllegalTransition, ValueError) as error:
            say(label, f"{type(error).__name__}: {error}")

    life = OrderLifecycle("W2201", 10000)
    life.replay([("pay", t0), ("fulfill", t0), ("ship", t0)])
    attempt("cancel a shipped order", lambda: life.apply("cancel", t0).value)
    attempt("can('refund') while shipped", lambda: life.can("refund"))
    paid = OrderLifecycle("W1", 10000)
    paid.apply("pay", t0)
    paid.apply("cancel", t0)
    say("cancel after pay -> refunded_cents", paid.refunded_cents)
    unpaid = OrderLifecycle("W2", 10000)
    unpaid.apply("cancel", t0)
    say("cancel before pay -> refunded_cents", unpaid.refunded_cents)
    d = OrderLifecycle("W3310", 10000)
    d.replay([("pay", t0), ("fulfill", t0), ("ship", t0), ("deliver", t0)])
    attempt("refund r-77 $90", lambda: d.refund("r-77", 9000, t0).value)
    attempt("refund r-77 $90 again (retry)", lambda: d.refund("r-77", 9000, t0).value)
    attempt("refund r-78 $100", lambda: d.refund("r-78", 10000, t0).value)
    attempt("refund r-79 remaining", lambda: d.refund("r-79", d.remaining_cents, t0).value if d.remaining_cents else "nothing left")
    say("refunded / state", f"{format_cents(d.refunded_cents)} / {d.state.value}")


def scenario_api() -> None:
    class Clock:
        now = 0.0

        def __call__(self):
            return self.now

        def sleep(self, s):
            print(f"    sleep {s:.2f}s")
            self.now += s

    clock = Clock()
    transport = FakeTransport()
    policy = RetryPolicy(max_attempts=4, base_delay=0.1, max_delay=1.0, budget_seconds=2.5)
    api = OrdersAPI(transport, policy, sleep=clock.sleep, clock=clock, rng=random.Random(1))
    transport.script("GET", "/orders/W9", Response(404, "missing"))
    try:
        api.get_order("W9")
    except ApiError as error:
        say("GET /orders/W9", f"{error} after {len(transport.calls)} request(s)")
    transport.calls.clear()
    transport.script("GET", "/orders/W8", Response(503), Response(503), Response(503), Response(503), Response(503))
    try:
        api.get_order("W8")
    except ApiError as error:
        say("GET /orders/W8 (always 503)", f"{error} after {len(transport.calls)} request(s)")
    transport.calls.clear()
    page1 = Response(200, {"orders": [{"id": 1}, {"id": 2}], "has_more": True, "next_cursor": "p2"})
    transport.script("GET", "/customers/C1/orders", page1)
    transport.script("GET", "/customers/C1/orders?cursor=p2", Response(200, {"orders": [{"id": 3}], "has_more": False}))
    say("list_orders ids", [o["id"] for o in api.list_orders("C1")])
    transport.calls.clear()
    transport.script("POST", "/orders/W1/refunds", Response(503), ApiTimeout(), Response(200, {"refund_id": "r1", "amount_cents": 1800}))
    api.issue_refund("W1", 1800)
    say("idempotency keys seen", sorted({c[3]["Idempotency-Key"][:8] for c in transport.calls}))
    clock2 = Clock()
    transport2 = FakeTransport()
    transport2.script("GET", "/orders/W7", *[Response(500)] * 10)
    tight = RetryPolicy(max_attempts=10, base_delay=1.0, max_delay=1.0, budget_seconds=2.5)
    api2 = OrdersAPI(transport2, tight, sleep=clock2.sleep, clock=clock2, rng=random.Random(0))
    try:
        api2.get_order("W7")
    except ApiError:
        say("budget 2.5s -> gave up at", f"t={clock2.now:.2f}s after {len(transport2.calls)} request(s)")


def scenario_agent() -> None:
    order = {"order_id": "W1001", "status": "delivered", "items": [{"sku": "AP-TENT-02"}], "total_cents": 21500}
    order2 = {"order_id": "W1002", "status": "shipped", "items": [{"sku": "AP-SOCK-M"}], "total_cents": 1800}
    tools = [
        agent_mod.Tool("lookup_order", lambda order_id: order if order_id == "W1001" else order2, required=("order_id",)),
        agent_mod.Tool("decide_refund", lambda order_id: {"outcome": "approved", "amount_cents": 18000}, required=("order_id",)),
        agent_mod.Tool("explode", lambda: 1 / 0),
    ]
    T = agent_mod.ToolCall
    turns = [
        agent_mod.ModelTurn(tool_calls=(T("lookup_order", {"order_id": "W1001"}),)),
        agent_mod.ModelTurn(tool_calls=(T("lookup_order", {"order_id": "W1002"}),)),
        agent_mod.ModelTurn(tool_calls=(T("decide_refund", {"order_id": "W1001"}),)),
        agent_mod.ModelTurn(text="I can refund $180.00 for the tent."),
    ]
    loop = agent_mod.AgentLoop(agent_mod.ScriptedModel(turns), tools)
    result = loop.run([], "refund my tent")
    say("reply", result.text)
    say("memory ordered_items", loop.memory["ordered_items"])
    model = agent_mod.ScriptedModel([agent_mod.ModelTurn(tool_calls=(T("lookup_order", {"order_id": "W1001"}),))] * 10)
    result = agent_mod.AgentLoop(model, tools, max_steps=3).run([], "loop")
    say("max_steps=3 -> model calls", f"{model.calls} (escalated={result.escalated})")
    boom = agent_mod.ScriptedModel([agent_mod.ModelTurn(tool_calls=(T("explode", {}),)), agent_mod.ModelTurn(text="recovered")])
    try:
        result = agent_mod.AgentLoop(boom, tools).run([], "boom")
        say("tool raised ZeroDivisionError", result.text)
    except Exception as error:  # noqa: BLE001
        say("tool raised ZeroDivisionError", f"loop crashed: {type(error).__name__}")
    handoff_turn = agent_mod.ModelTurn(tool_calls=(T("handoff", {"message": "Passing you to Sam."}), T("explode", {})))
    model = agent_mod.ScriptedModel([handoff_turn, agent_mod.ModelTurn(text="kept going")])
    result = agent_mod.AgentLoop(model, tools).run([], "human")
    say("handoff + other tool", f"{result.text!r} escalated={result.escalated} model calls={model.calls}")
    history = [{"role": "user", "content": f"m{i}"} for i in range(30)]
    model = agent_mod.ScriptedModel([agent_mod.ModelTurn(text="ok")])
    agent_mod.AgentLoop(model, tools, max_history=6).run(history, "latest")
    say("first message after trim", model.seen_messages[0][0]["content"][:40])


def scenario_refund_chat() -> None:
    m = ConversationMachine()
    chat(m, Event("user_message", text="I want a refund"))
    chat(m, Event("user_message", text="my email is alice@example.com"))
    chat(m, Event("user_message", text="order #W1001"))
    chat(m, Event("tool_result", tool="verify_identity", result={"ok": True}))
    chat(m, Event("tool_result", tool="lookup_order", result={"order_id": "W1001", "status": "delivered"}))
    chat(m, Event("tool_result", tool="decide_refund", result={"outcome": "approved", "amount_cents": 18000}))
    chat(m, Event("user_message", text="yes"))
    chat(m, Event("tool_result", tool="issue_refund", result={"amount_cents": 18000}))
    chat(m, Event("user_message", text="blorp"))
    chat(m, Event("user_message", text="blorp"))
    chat(m, Event("user_message", text="blorp"))


def scenario_verify_fail() -> None:
    m = ConversationMachine()
    chat(m, Event("user_message", text="where is my order? alice@example.com W1001"))
    chat(m, Event("tool_result", tool="verify_identity", result={"ok": False}))
    chat(m, Event("user_message", text="W1002"))
    chat(m, Event("tool_result", tool="verify_identity", result={"ok": True}))
    chat(m, Event("tool_result", tool="lookup_order", result={"order_id": "W1002", "status": "shipped"}))
    chat(m, Event("user_message", text="now a refund on W1003"))
    for _ in range(4):
        if m.state.value in ("escalated", "closed"):
            break
        chat(m, Event("tool_result", tool="verify_identity", result={"ok": False}))
        if m.state.value == "identifying":
            chat(m, Event("user_message", text="W1003"))


def scenario_timeout() -> None:
    m = ConversationMachine()
    chat(m, Event("user_message", text="refund alice@example.com W1001"))
    chat(m, Event("tool_result", tool="verify_identity", result={"ok": True}))
    chat(m, Event("tool_result", tool="lookup_order", result={"order_id": "W1001", "status": "delivered"}))
    chat(m, Event("tool_result", tool="decide_refund", result={"outcome": "approved", "amount_cents": 18000}))
    chat(m, Event("timeout"))
    print(f"  context after timeout: pending_refund={m.context['pending_refund']}")


def scenario_status_chat() -> None:
    m = ConversationMachine()
    chat(m, Event("user_message", text="where is my order alice@example.com W1001"))
    chat(m, Event("tool_result", tool="verify_identity", result={"ok": True}))
    chat(m, Event("tool_result", tool="lookup_order", result={"order_id": "W1001"}))  # malformed: no status
    print(f"  context after crash: order={m.context['order']} state={m.state.value}")


SCENARIOS = {
    "catalog": scenario_catalog,
    "search": scenario_search,
    "policy": scenario_policy,
    "promo": scenario_promo,
    "lifecycle": scenario_lifecycle,
    "api": scenario_api,
    "agent": scenario_agent,
    "refund-chat": scenario_refund_chat,
    "verify-fail": scenario_verify_fail,
    "timeout": scenario_timeout,
    "status-chat": scenario_status_chat,
}


def main(argv: list[str]) -> int:
    names = argv or []
    if not names or any(n not in SCENARIOS for n in names):
        print("scenarios: " + ", ".join(SCENARIOS))
        return 0 if not names else 2
    for name in names:
        print(f"== {name}")
        SCENARIOS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
