# Level 01: strings and loops (warm up)

Module: `workspace/supportdesk/catalog.py`. Spec: `docs/specs/catalog.md`.

Tickets from the support team this morning:

1. "A customer typed `#w1001` into the chat and the bot said it could not find the order.
   Typing `#W1001` worked. Order ids are supposed to be case insensitive."
2. "Searching the catalog for `camping tent` shows the tarp first and the tent last.
   It used to show the most relevant item first."
3. "The storefront paginates recommendations 2 per row. With 5 results the fifth
   product never shows up."
4. "Masked emails in the transcript export look off. `alice.jones@example.com`
   came out one character too long."
5. "The warehouse import uses SKUs like `ap_tent_02`. Those used to resolve, now they do not."

Fix the code so the tickets are resolved. Do not change the tests.
