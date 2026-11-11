"""Exception types shared by the clients."""


class CuCommonsError(Exception):
    """Base class for every error raised by cu-commons."""


class ConfigError(CuCommonsError):
    """A required setting is missing."""


class AuthError(CuCommonsError):
    """Credentials were rejected (expired, revoked or wrong)."""


class ApiError(CuCommonsError):
    """An upstream API returned an error after retries."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NoDataError(CuCommonsError):
    """Nothing to process (e.g. no activity today). Usually not a failure."""
