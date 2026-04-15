RESPONSE_PROMPT = """
Return strict JSON with key response_text.
Keep the wording concise and patient-facing.
Do not invent new actions, permissions, or workflow outcomes.
Keep the same operational meaning as the provided fallback text.
Do not add medical advice, extra policy, or details not already present in the fallback text.
If the fallback text asks for identity information, keep the request direct and step-by-step.
"""
