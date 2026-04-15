from __future__ import annotations


class ApplicationError(Exception):
    pass


class SessionNotFoundError(ApplicationError):
    pass


class DependencyUnavailableError(ApplicationError):
    pass
