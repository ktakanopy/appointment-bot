from __future__ import annotations

import pytest

from app.models import DateOfBirth, FullName, Phone


def test_phone_normalizes_digits():
    assert Phone("(11) 99999-8888").digits == "11999998888"


def test_phone_rejects_short_values():
    with pytest.raises(ValueError):
        Phone("123")


def test_date_of_birth_normalizes_supported_formats():
    assert DateOfBirth("10/05/1990").value == "1990-05-10"
    assert DateOfBirth("1990-05-10").value == "1990-05-10"


def test_date_of_birth_rejects_invalid_values():
    with pytest.raises(ValueError):
        DateOfBirth("1994-28-09")


def test_full_name_normalizes_spacing_and_case():
    assert FullName("  ana   silva  ").value == "Ana Silva"


def test_full_name_requires_first_and_last_name():
    with pytest.raises(ValueError):
        FullName("Ana")
