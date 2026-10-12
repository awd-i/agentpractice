TITLE = "The conversation state machine"
MINUTES = 40
HINTS = [
    "Reproduce each ticket with `python dojo.py demo refund-chat` / `verify-fail` / `timeout` before touching code.",
    "Tickets 1 and 5 are both about context handling, not transitions. Read _merge_slots and handle().",
    "Tickets 3 and 6 are the same bug class: a counter compared with the wrong operator.",
]
DEMO = ["refund-chat", "verify-fail", "timeout", "status-chat"]
MUTATIONS = [
    dict(
        file="conversation.py",
        kind="state contamination (slot merge)",
        why="Slots are replaced wholesale, so a message that carries only the order id erases the email we already had.",
        old=(
            "        for key, value in found.items():\n"
            "            if value:\n"
            '                self.context["slots"][key] = value\n'
        ),
        new='        self.context["slots"] = dict(found)\n',
    ),
    dict(
        file="conversation.py",
        kind="counter not reset",
        why="verify_attempts must reset on success; otherwise failures accumulate across the whole session.",
        old=(
            '        if event.result.get("ok"):\n'
            '            self.context["verify_attempts"] = 0\n'
            "            self._go(State.LOOKUP)\n"
        ),
        new='        if event.result.get("ok"):\n            self._go(State.LOOKUP)\n',
    ),
    dict(
        file="conversation.py",
        kind="off by one (>= vs >)",
        why="Escalation should happen when the attempt count reaches MAX_VERIFY_ATTEMPTS, not when it exceeds it.",
        old='        if self.context["verify_attempts"] >= MAX_VERIFY_ATTEMPTS:',
        new='        if self.context["verify_attempts"] > MAX_VERIFY_ATTEMPTS:',
    ),
    dict(
        file="conversation.py",
        kind="missing cleanup on timeout",
        why="Timing out in CONFIRMING must clear the pending refund; the state moved on but the context kept the money.",
        old=(
            "        if self.state == State.CONFIRMING:\n"
            '            self.context["pending_refund"] = None\n'
            "            actions.append("
        ),
        new="        if self.state == State.CONFIRMING:\n            actions.append(",
    ),
    dict(
        file="conversation.py",
        kind="partial rollback",
        why="handle() promises all or nothing. Restoring the state but not the context leaves half a step behind.",
        old="            self.state = before_state\n            self.context = before_context\n            raise",
        new="            self.state = before_state\n            raise",
    ),
    dict(
        file="conversation.py",
        kind="off by one (> vs >=)",
        why="MAX_CLARIFICATIONS unclear messages are tolerated; only the one after that escalates.",
        old='        if self.context["clarifications"] > MAX_CLARIFICATIONS:',
        new='        if self.context["clarifications"] >= MAX_CLARIFICATIONS:',
    ),
]
