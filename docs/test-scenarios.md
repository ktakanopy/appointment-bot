# Manual Test Scenarios

Use this checklist to manually validate the most important patient flows and failure paths.

1. Ask to list appointments before verification and confirm the service collects
   full name, phone, and date of birth before returning results.
2. Verify successfully, then confirm the first appointment from the current
   list.
3. Verify successfully, cancel the first appointment, and ask to list
   appointments again.
4. Try to confirm or cancel with an ordinal reference before listing and verify
   the service asks for list context first.
5. Retry verification with wrong identity details and confirm the response
   explains that the provided identity details do not match the records.
6. Enter an invalid date of birth format during verification and confirm the
   response explains the invalid field without resetting the previously entered
   name and phone.
7. Use the Streamlit app to start a new session and complete one protected flow
   without calling the API manually.
8. Verify in one session, start a fresh session, and confirm protected actions
   require identity verification again.
9. Run the eval suite and confirm it returns per-scenario status and judge
   summaries.
10. Enable tracing with invalid Langfuse credentials and confirm the workflow
    still completes without failing the request path.
11. Send a chat request with an unknown session id and confirm the API returns a
    session-not-found response instead of silently creating a thread.
12. Fail identity verification three times in the same session and confirm the
    session is locked until a new session is created.
