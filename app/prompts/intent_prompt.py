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
"""
