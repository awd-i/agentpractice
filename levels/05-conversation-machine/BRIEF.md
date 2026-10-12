# Level 05: the conversation state machine

Module: `workspace/supportdesk/conversation.py`. Spec and diagram: `docs/specs/conversation.md`.

This is the closest thing to the reported Sierra question ("finding bugs in a state
machine"). Six tickets from chat QA:

1. "Customer gave their email in one message and the order id in the next. The bot
   then asked for the email again."
2. "After one failed identity check and then a successful one, the next failed check
   on a different order escalated immediately. The counter is not resetting."
3. "The spec says three failed verifications, then hand off. The bot allows four and
   even prints `0 attempts left`."
4. "A customer went silent on the refund confirmation. We closed the chat, but the
   pending refund was still attached to the session and got picked up by the nightly
   job." (Check `context['pending_refund']` after a timeout.)
5. "A lookup tool returned a malformed order and the handler crashed. The session was
   left with the half-applied order in context even though the state rolled back."
6. "Two unclear messages are supposed to be tolerated. The bot hands off after the second."

Fix the code so the tickets are resolved. Do not change the tests.
