TITLE = "The agent loop (termination, observations, memory, grounding)"
MINUTES = 40
HINTS = [
    "Ticket 1: how many values does the range in run() produce?",
    "Ticket 6: _ground collects cents from tool_results. Which part of each result is it reading?",
    "Ticket 5: `break` leaves the inner loop; the outer loop keeps running.",
]
DEMO = ["agent"]
MUTATIONS = [
    dict(
        file="agent.py",
        kind="off by one (loop bound)",
        why="range(max_steps + 1) yields max_steps + 1 iterations.",
        old="        for step in range(1, self.max_steps + 1):",
        new="        for step in range(self.max_steps + 1):",
    ),
    dict(
        file="agent.py",
        kind="exception handling",
        why="Only ToolError was caught, so any other exception escaped the loop instead of becoming an observation.",
        old=(
            "        except ToolError as error:\n"
            '            return {"error": str(error)}\n'
            "        except Exception as error:  # noqa: BLE001 - tool failures become observations\n"
            '            return {"error": f"{type(error).__name__}: {error}"}\n'
        ),
        new='        except ToolError as error:\n            return {"error": str(error)}\n',
    ),
    dict(
        file="agent.py",
        kind="history trimming drops the system prompt",
        why="Trimming must pin messages[0]; slicing from the tail alone discards the system prompt.",
        old="        return [messages[0], *messages[-self.max_history :]]",
        new="        return messages[-self.max_history :]",
    ),
    dict(
        file="agent.py",
        kind="memory replaced instead of merged",
        why="ordered_items is overwritten with the latest lookup; it should be a merged, deduplicated list.",
        old=(
            '        known = self.memory["ordered_items"]\n'
            "        for item in items:\n"
            '            sku = item.get("sku")\n'
            "            if sku and sku not in known:\n"
            "                known.append(sku)\n"
        ),
        new='        self.memory["ordered_items"] = [item.get("sku") for item in items if item.get("sku")]\n',
    ),
    dict(
        file="agent.py",
        kind="wrong loop exit",
        why="break only leaves the tool-call loop; the agent then asks the model for another turn instead of returning the handoff.",
        old=(
            '                    result.text = call.args.get("message", "Connecting you with a teammate.")\n'
            "                    result.escalated = True\n"
            "                    return result\n"
        ),
        new=(
            '                    result.text = call.args.get("message", "Connecting you with a teammate.")\n'
            "                    result.escalated = True\n"
            "                    break\n"
        ),
    ),
    dict(
        file="agent.py",
        kind="grounding reads the wrong field",
        why="Amounts must be collected from tool results, not from the arguments the model passed in.",
        old='        seen_cents = set(_collect_cents(r["result"] for r in tool_results))',
        new='        seen_cents = set(_collect_cents(r["args"] for r in tool_results))',
    ),
]
