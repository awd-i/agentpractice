TITLE = "The order lifecycle (transition table, idempotency, terminal states)"
MINUTES = 30
HINTS = [
    "Draw the transition table from the diagram in the spec and diff it against TRANSITIONS.",
    "Ticket 4: when a refund brings remaining to zero, is the state check done before or after the amount is "
    "recorded?",
    "Ticket 3: idempotency means the same refund_id twice is a no-op. Where is the guard?",
]
DEMO = ["lifecycle"]
MUTATIONS = [
    dict(
        file="orders.py",
        kind="transition table (extra edge)",
        why="A SHIPPED -> CANCELLED edge was added to the table; shipped orders cannot be cancelled.",
        old="    (OrderState.FULFILLING, \"cancel\"): OrderState.CANCELLED,\n}",
        new=(
            '    (OrderState.FULFILLING, "cancel"): OrderState.CANCELLED,\n'
            '    (OrderState.SHIPPED, "cancel"): OrderState.CANCELLED,\n'
            "}"
        ),
    ),
    dict(
        file="orders.py",
        kind="wrong state in guard",
        why="The auto refund on cancel keys off the previous state. PLACED is before payment; PAID is the state that holds money.",
        old='        if event == "cancel" and previous == OrderState.PAID:',
        new='        if event == "cancel" and previous == OrderState.PLACED:',
    ),
    dict(
        file="orders.py",
        kind="idempotency",
        why="The duplicate refund_id guard was removed, so webhook retries are recorded twice.",
        old="        if refund_id in self.refund_ids:\n            return self.state\n        if self.state not in REFUNDABLE_FROM:",
        new="        if self.state not in REFUNDABLE_FROM:",
    ),
    dict(
        file="orders.py",
        kind="ordering (check before update)",
        why=(
            "remaining_cents is checked before the refund is added, so the order only becomes REFUNDED "
            "on the refund after the one that emptied it."
        ),
        old=(
            "        self.refunded_cents += amount_cents\n"
            "        self.refund_ids.add(refund_id)\n"
            "        if self.remaining_cents == 0:\n"
            "            self.state = OrderState.REFUNDED\n"
        ),
        new=(
            "        if self.remaining_cents == 0:\n"
            "            self.state = OrderState.REFUNDED\n"
            "        self.refunded_cents += amount_cents\n"
            "        self.refund_ids.add(refund_id)\n"
        ),
    ),
    dict(
        file="orders.py",
        kind="guard drift (two code paths disagree)",
        why="can('refund') dropped the state check, so it disagrees with refund(), which still enforces REFUNDABLE_FROM.",
        old="            return self.state in REFUNDABLE_FROM and self.remaining_cents > 0",
        new="            return self.remaining_cents > 0",
    ),
]
