from app.graph import parsing
from app.models import ConversationOperation, DateOfBirth, Phone


def test_normalize_helpers_parse_supported_identity_fields():
    assert Phone("(11) 99999-8888").digits == "11999998888"
    assert DateOfBirth("10/05/1990").value == "1990-05-10"
    assert parsing.extract_full_name("ana silva") == "Ana Silva"
    assert parsing.extract_full_name("my phone number is 11999998888") is None
    assert parsing.extract_full_name("I want to see my appointments, I'm Ana Silva") == "Ana Silva"


def test_extract_requested_action_prefers_protected_keywords():
    assert (
        parsing.extract_requested_operation("Please cancel my appointment", {})
        == ConversationOperation.CANCEL_APPOINTMENT
    )
    assert (
        parsing.extract_requested_operation("Show my appointments", {})
        == ConversationOperation.LIST_APPOINTMENTS
    )
    assert parsing.extract_requested_operation("What can you do?", {}) == ConversationOperation.HELP
