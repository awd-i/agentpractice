TITLE = "Strings and loops (warm up)"
MINUTES = 20
HINTS = [
    "Each ticket maps to exactly one function in catalog.py. Start by reading the function's docstring, it states the contract.",
    "For ticket 2, print the `scored` list before and after the sort and compare with the docstring.",
    "For ticket 3, call chunk([1,2,3,4,5], 2) in a REPL. Where does the loop stop?",
]
DEMO = ["search", "catalog"]
MUTATIONS = [
    dict(
        file="catalog.py",
        kind="string normalisation",
        why="The prefix letter is no longer upper cased, so '#w1001' normalises to 'w1001' and never matches 'W1001'.",
        old='    return f"{prefix.upper()}{int(digits)}"',
        new='    return f"{prefix}{int(digits)}"',
    ),
    dict(
        file="catalog.py",
        kind="string normalisation",
        why="Underscores were dropped from the separator class, so 'ap_tent_02' keeps its underscores and never matches.",
        old='    cleaned = re.sub(r"[\\s_]+", "-", (raw or "").strip())',
        new='    cleaned = re.sub(r"[\\s]+", "-", (raw or "").strip())',
    ),
    dict(
        file="catalog.py",
        kind="sort order",
        why=(
            "Scores are stored negated so an ascending sort puts the best first. "
            "Sorting descending inverts the ranking and drops the position tie break."
        ),
        old="    scored.sort(key=lambda entry: (entry[0], entry[1]))\n    return [product for _, _, product in scored[:limit]]",
        new="    scored.sort(key=lambda entry: entry[0], reverse=True)\n    return [product for _, _, product in scored[:limit]]",
    ),
    dict(
        file="catalog.py",
        kind="loop bound (off by one)",
        why="The range stops `size` short of the end, so the trailing partial chunk is never produced.",
        old="    return [items[i : i + size] for i in range(0, len(items), size)]",
        new="    return [items[i : i + size] for i in range(0, len(items) - size + 1, size)]",
    ),
    dict(
        file="catalog.py",
        kind="off by one",
        why="The mask keeps the first and last character, so the star run must be len - 2, not len - 1.",
        old='        masked = local[0] + "*" * (len(local) - 2) + local[-1]',
        new='        masked = local[0] + "*" * (len(local) - 1) + local[-1]',
    ),
]
