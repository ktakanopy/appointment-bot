from __future__ import annotations


class DomainError(Exception):
    pass


class AppointmentNotConfirmableError(DomainError):
    pass


class AppointmentNotCancelableError(DomainError):
    pass


class AppointmentNotOwnedError(DomainError):
    pass


class AppointmentNotFoundError(DomainError):
    pass
