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
