# Manual test scenarios

Use this checklist if you want to walk the product manually instead of relying
only on the automated tests.

1. Ask to list appointments before verification and confirm the bot collects full name, phone, and date of birth before showing results.
2. Verify successfully, then confirm the first appointment from the current list.
3. Verify successfully, cancel the first appointment, and ask for the list again.
4. Try to confirm or cancel with an ordinal reference before listing and confirm the bot asks for list context first.
5. Retry verification with wrong identity details and confirm the response explains that the identity did not match the records.
6. Enter an invalid date of birth during verification and confirm the bot explains the problem without wiping the previously collected name and phone.
7. Use the Streamlit app to complete one protected flow end to end.
8. Verify in one session, start a fresh session, and confirm protected actions require verification again.
9. Run the eval suite and confirm it prints per-scenario status and judge summaries.
10. Enable tracing with invalid Langfuse credentials and confirm the request still succeeds.
11. Send a chat request with an unknown session id and confirm the API returns a session-not-found response.
12. Fail identity verification three times in the same session and confirm the session locks until a new session is created.
