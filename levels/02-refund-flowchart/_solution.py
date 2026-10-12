TITLE = "The refund flowchart (tiers and branches)"
MINUTES = 30
HINTS = [
    "Walk the flowchart in docs/specs/refund_policy.md with one concrete case per ticket and note where the code diverges.",
    "Ticket 2: how is the tier compared? Tiers are an enum. What happens when you compare their string values?",
    "Ticket 4: integer division truncates. The spec asks for half up rounding, which is what the +5000 was for.",
]
DEMO = ["policy"]
MUTATIONS = [
    dict(
        file="refund_policy.py",
        kind="boundary (inclusive window)",
        why="The window is inclusive of the last day, so only ages strictly greater than the window are outside it.",
        old="    if age > window:",
        new="    if age >= window:",
    ),
    dict(
        file="refund_policy.py",
        kind="branch ordering / guard",
        why="The final sale guard must exempt defective items. Without `and not defective` defective final sale items are denied.",
        old="    if item.final_sale and not defective:",
        new="    if item.final_sale:",
    ),
    dict(
        file="refund_policy.py",
        kind="tier comparison",
        why="Tiers compared as strings: 'silver' >= 'premium' is True alphabetically, so silver got premium's shipping refund.",
        old="    if whole_order and (defective or customer.tier == Tier.PREMIUM):",
        new='    if whole_order and (defective or customer.tier.value >= "premium"):',
    ),
    dict(
        file="refund_policy.py",
        kind="rounding",
        why="Dropping the +5000 turns half up rounding into truncation; 10% of 1005 became 100 instead of 101.",
        old="    return (amount_cents * bps + 5_000) // 10_000",
        new="    return amount_cents * bps // 10_000",
    ),
    dict(
        file="refund_policy.py",
        kind="boundary (threshold)",
        why="Manager review is for amounts strictly over $500; `>=` sends exactly $500 to a manager.",
        old="    if customer.tier == Tier.BASIC and amount > MANAGER_REVIEW_THRESHOLD_CENTS:",
        new="    if customer.tier == Tier.BASIC and amount >= MANAGER_REVIEW_THRESHOLD_CENTS:",
    ),
]
