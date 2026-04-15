INTENT_PROMPT = """
Return strict JSON with keys requested_action, full_name, phone, dob, appointment_reference.
Use only these requested_action values:
- verify_identity
- list_appointments
- confirm_appointment
- cancel_appointment
- help
- unknown
Do not decide authorization or mutate appointment state.
Leave unknown fields as null.
If the message asks to confirm or cancel an appointment by number, treat the number as patient-facing and 1-indexed.
Examples:
- "I want to see my appointments" -> {"requested_action":"list_appointments","full_name":null,"phone":null,"dob":null,"appointment_reference":null}
- "confirm the first one" -> {"requested_action":"confirm_appointment","full_name":null,"phone":null,"dob":null,"appointment_reference":"1"}
- "my name is Ana Silva" -> {"requested_action":"unknown","full_name":"Ana Silva","phone":null,"dob":null,"appointment_reference":null}
- "11999998888" -> {"requested_action":"unknown","full_name":null,"phone":"11999998888","dob":null,"appointment_reference":null}
- "1990-05-10" -> {"requested_action":"unknown","full_name":null,"phone":null,"dob":"1990-05-10","appointment_reference":null}
"""
