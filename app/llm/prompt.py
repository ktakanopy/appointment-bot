INTENT_PROMPT = """
Return strict JSON with keys requested_operation, full_name, phone, dob, selected_index.
Use only these requested_operation values:
- verify_identity
- list_appointments
- confirm_appointment
- cancel_appointment
- help
- unknown
Do not decide authorization or mutate appointment state.
Leave unknown fields as null.
Recent messages may be provided in state.messages. Use them only to resolve references in the current user message.
Do not invent a new request from history alone.

For selected_index:
- Only set it when the user refers to a specific appointment from the most recently displayed list.
- Return the 1-based position of the appointment in that list.
- Use state.messages to find the displayed list and resolve the reference.
- If the reference is ambiguous, unclear, or no list has been shown, return null.
- Do not guess. Prefer null over a wrong index.

Examples:
- "I want to see my appointments" -> {"requested_operation":"list_appointments","full_name":null,"phone":null,"dob":null,"selected_index":null}
- "confirm the first one" -> {"requested_operation":"confirm_appointment","full_name":null,"phone":null,"dob":null,"selected_index":1}
- "cancel 2" -> {"requested_operation":"cancel_appointment","full_name":null,"phone":null,"dob":null,"selected_index":2}
- "cancel the Friday one" (list shows appointment 1 on Monday, appointment 2 on Friday) -> {"requested_operation":"cancel_appointment","full_name":null,"phone":null,"dob":null,"selected_index":2}
- "confirm the one with Dr. Lima" (list shows appointment 2 with Dr. Lima) -> {"requested_operation":"confirm_appointment","full_name":null,"phone":null,"dob":null,"selected_index":2}
- "cancel the 3 PM one" (list shows appointment 1 at 14:00, appointment 2 at 15:00) -> {"requested_operation":"cancel_appointment","full_name":null,"phone":null,"dob":null,"selected_index":2}
- "cancel my appointment" (multiple appointments, unclear which) -> {"requested_operation":"cancel_appointment","full_name":null,"phone":null,"dob":null,"selected_index":null}
- "confirm it" (no list shown yet) -> {"requested_operation":"confirm_appointment","full_name":null,"phone":null,"dob":null,"selected_index":null}
- "my name is Ana Silva" -> {"requested_operation":"unknown","full_name":"Ana Silva","phone":null,"dob":null,"selected_index":null}
- "11999998888" -> {"requested_operation":"unknown","full_name":null,"phone":"11999998888","dob":null,"selected_index":null}
- "1990-05-10" -> {"requested_operation":"unknown","full_name":null,"phone":null,"dob":"1990-05-10","selected_index":null}
"""
