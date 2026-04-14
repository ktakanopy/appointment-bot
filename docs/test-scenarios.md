# Manual Test Scenarios

1. Ask to list appointments before verification and confirm the service collects
   full name, phone, and date of birth before returning results.
2. Verify successfully, then confirm the first appointment from the current
   list.
3. Verify successfully, cancel the first appointment, and ask to list
   appointments again.
4. Try to confirm or cancel with an ordinal reference before listing and verify
   the service asks for list context first.
5. Retry verification with wrong identity details and confirm the response stays
   generic.
6. Use the Streamlit app to start a new session and complete one protected flow
   without calling the API manually.
7. Verify in one session, note the returned remembered-identity id, start a new
   session with it, and confirm appointments are available without re-entering
   identity details.
8. Revoke a remembered identity and confirm the next session falls back to
   normal verification.
9. Run the eval suite and confirm it returns per-scenario status and judge
   summaries.
10. Enable tracing with invalid Langfuse credentials and confirm the workflow
    still completes without failing the request path.
11. Send a chat request with an unknown session id and confirm the API returns a
    session-not-found response instead of silently creating a thread.
12. Fail identity verification three times in the same session and confirm the
    session is locked until a new session is created.
