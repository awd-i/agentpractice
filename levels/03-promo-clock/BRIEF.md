# Level 03: the promo clock

Module: `workspace/supportdesk/promotions.py`. Spec: `docs/specs/promotions.md`.

Marketing is unhappy:

1. "The EARLY code (8am to 10am Pacific) is being accepted at 2:30 in the morning
   and rejected at 9:30am. Our servers run in UTC."
2. "SUMMER ended June 30 but it was still accepted on July 1 at midnight."
3. "A customer entered SAVE10 and then FLAT5. FLAT5 was rejected because only one
   discount is allowed, fine, but when they tried FLAT5 alone on their next order
   it said already redeemed."
4. "A $3.00 cart with FLAT5 ($5 off) produced a negative order total."
5. "Premium members are being told VIP20 requires silver tier."

Fix the code so the tickets are resolved. Do not change the tests.
