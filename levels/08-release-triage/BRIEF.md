# Level 08: release triage (cross cutting)

Modules: all of `workspace/supportdesk/`. Specs: `docs/specs/`.

This level is the closest to the official Sierra format: a medium sized codebase you
have not seen, a release that touched everything, and a pile of tickets. You do not
know which module each ticket lives in. Six bugs, six modules, sixty minutes.

1. "Recommendations for the 2P tent list the 2P tent itself first."
2. "A customer got a refund approved on an order that is still in transit."
3. "SAVE10 needs a $50 subtotal. A $50.00 cart is being rejected."
4. "Order W3310 (total $100) has refunded_cents = $190. Two refunds of $90 and $100
   were both accepted."
5. "After a failed identity check the bot asks for the email again, even though the
   customer already gave it. It should only ask for the order number."
6. "The retry budget is 2.5 seconds, but the client slept past it: a call slept until
   t=2.6s and only then gave up."

Fix the code so the tickets are resolved. Do not change the tests.
