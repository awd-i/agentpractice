TITLE = "The promo clock (time windows and ordering)"
MINUTES = 30
HINTS = [
    "Ticket 1: there are two ways to put a timezone on a datetime. One converts, the other just relabels.",
    "Ticket 3: when exactly is a code marked redeemed? Compare with the two places a code can be rejected.",
    "Ticket 5: the tier check should be an ordering, not an equality. TIER_RANK exists for that.",
]
DEMO = ["promo"]
MUTATIONS = [
    dict(
        file="promotions.py",
        kind="timezone conversion",
        why="replace(tzinfo=) relabels the clock time without converting it, so 16:30 UTC was treated as 16:30 Pacific.",
        old="    local = now.astimezone(PACIFIC)",
        new="    local = now.replace(tzinfo=PACIFIC)",
    ),
    dict(
        file="promotions.py",
        kind="boundary (exclusive end)",
        why="The end of a date range is exclusive. `>` lets the exact end instant through.",
        old="    if promo.ends is not None and local >= promo.ends.astimezone(PACIFIC):",
        new="    if promo.ends is not None and local > promo.ends.astimezone(PACIFIC):",
    ),
    dict(
        file="promotions.py",
        kind="side effect ordering",
        why="Marking the code redeemed right after the eligibility check burns it even when the one-code-per-kind rule rejects it later.",
        old=(
            "        reason = check_eligibility(promo, cart, now, store)\n"
            "        if reason is not None:\n"
            "            result.rejected[raw] = reason\n"
            "            continue\n"
            '        if promo.kind == "free_shipping":'
        ),
        new=(
            "        reason = check_eligibility(promo, cart, now, store)\n"
            "        if reason is not None:\n"
            "            result.rejected[raw] = reason\n"
            "            continue\n"
            "        if promo.single_use:\n"
            "            store.mark_redeemed(cart.customer_id, promo.code)\n"
            '        if promo.kind == "free_shipping":'
        ),
    ),
    dict(
        file="promotions.py",
        kind="missing clamp",
        why="The discount must never exceed the subtotal; max(discount, 0) clamps the wrong side.",
        old="        discount = min(discount, cart.subtotal_cents)",
        new="        discount = max(discount, 0)",
    ),
    dict(
        file="promotions.py",
        kind="tier comparison",
        why="`min_tier` is a floor, not an exact match. Premium is above silver and must pass.",
        old="    if promo.min_tier is not None and TIER_RANK[cart.tier] < TIER_RANK[promo.min_tier]:",
        new="    if promo.min_tier is not None and cart.tier != promo.min_tier:",
    ),
]
