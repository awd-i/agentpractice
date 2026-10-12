TITLE = "Release triage (one bug per module, no map)"
MINUTES = 60
HINTS = [
    "Spend the first five minutes mapping each ticket to a module and a function before fixing anything.",
    "Tickets 2 and 4 are both missing or weakened guards. Find the guard the spec calls for and compare.",
    "Ticket 6: the budget check has to account for the sleep that is about to happen, not just the time already spent.",
]
DEMO = ["search", "policy", "promo", "lifecycle", "verify-fail", "api"]
MUTATIONS = [
    dict(
        file="catalog.py",
        kind="missing exclusion",
        why="The anchor product was no longer excluded from its own recommendations.",
        old="        if product.sku == anchor.sku or product.in_stock <= 0:",
        new="        if product.in_stock <= 0:",
    ),
    dict(
        file="refund_policy.py",
        kind="weakened guard",
        why="Only delivered (or returning) orders are refundable; checking just for cancelled lets shipped orders through.",
        old='    if order.status not in ("delivered", "return_requested", "returned"):',
        new='    if order.status == "cancelled":',
    ),
    dict(
        file="promotions.py",
        kind="boundary",
        why="Minimum subtotal is inclusive; `<=` rejects a cart that is exactly at the minimum.",
        old="    if cart.subtotal_cents < promo.min_subtotal_cents:",
        new="    if cart.subtotal_cents <= promo.min_subtotal_cents:",
    ),
    dict(
        file="orders.py",
        kind="wrong bound",
        why="Each refund must be checked against what remains, not the original total.",
        old="        if amount_cents > self.remaining_cents:",
        new="        if amount_cents > self.total_cents:",
    ),
    dict(
        file="conversation.py",
        kind="over-eager reset",
        why="A failed verification should only drop the order id; clearing all slots throws away the email too.",
        old='        self.context["slots"].pop("order_id", None)',
        new='        self.context["slots"].clear()',
    ),
    dict(
        file="api_client.py",
        kind="budget check ignores the upcoming sleep",
        why="The check must include the delay about to be slept, otherwise the client sleeps past the budget.",
        old="            if clock() - started + delay > policy.budget_seconds:",
        new="            if clock() - started > policy.budget_seconds:",
    ),
]
