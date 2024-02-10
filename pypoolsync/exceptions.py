"""Exceptions."""


class PoolsyncApiException(Exception):
    """General Poolsync API exception."""


class PoolsyncAuthenticationError(PoolsyncApiException):
    """To indicate there is an issue authenticating."""
