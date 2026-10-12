TITLE = "The flaky orders API (retries, pagination, idempotency)"
MINUTES = 30
HINTS = [
    "with_retry decides what is retryable. Compare its check with is_retryable().",
    "Ticket 3: in list_orders, what happens to the page that has has_more == False?",
    "Ticket 4: anything computed inside the retried callable is recomputed on each attempt.",
]
DEMO = ["api"]
MUTATIONS = [
    dict(
        file="api_client.py",
        kind="error classification",
        why="Retrying every ApiError includes 4xx client errors; only timeouts, 429 and 5xx are retryable.",
        old="            if not is_retryable(error):\n                raise",
        new="            if not isinstance(error, ApiError):\n                raise",
    ),
    dict(
        file="api_client.py",
        kind="off by one (attempt cap)",
        why="`>` allows one more attempt than max_attempts.",
        old="            if attempt >= policy.max_attempts:\n                raise",
        new="            if attempt > policy.max_attempts:\n                raise",
    ),
    dict(
        file="api_client.py",
        kind="loop ordering (pagination)",
        why="Breaking before extend drops the final page.",
        old=(
            '            page = self._call("GET", path)\n'
            '            orders.extend(page["orders"])\n'
            '            if not page.get("has_more"):\n'
            "                break\n"
        ),
        new=(
            '            page = self._call("GET", path)\n'
            '            if not page.get("has_more"):\n'
            "                break\n"
            '            orders.extend(page["orders"])\n'
        ),
    ),
    dict(
        file="api_client.py",
        kind="idempotency key per attempt",
        why="Generating the key inside the retried lambda produces a new key per attempt; it must be fixed once per logical refund.",
        old=(
            "        key = idempotency_key or str(uuid.uuid4())\n"
            '        body = {"order_id": order_id, "amount_cents": amount_cents}\n'
            '        return self._call("POST", f"/orders/{order_id}/refunds", body, {"Idempotency-Key": key})'
        ),
        new=(
            '        body = {"order_id": order_id, "amount_cents": amount_cents}\n'
            "        return with_retry(\n"
            "            lambda: self._once(\n"
            '                "POST",\n'
            '                f"/orders/{order_id}/refunds",\n'
            "                body,\n"
            '                {"Idempotency-Key": idempotency_key or str(uuid.uuid4())},\n'
            "            ),\n"
            "            self.policy,\n"
            "            **self.retry_kwargs,\n"
            "        )"
        ),
    ),
    dict(
        file="api_client.py",
        kind="missing jitter",
        why="Without jitter every client retries on the same schedule.",
        old="    return capped * rng.uniform(0.5, 1.5)",
        new="    return capped",
    ),
]
