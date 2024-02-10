"""Utilities."""
from __future__ import annotations

from base64 import b64decode
from collections.abc import Mapping
from typing import Final, TypeVar, cast, overload

_T = TypeVar("_T")

ENCODING: Final = "utf-8"
REDACTED: Final = "**REDACTED**"
REDACT_FIELDS: Final = ["arn", "deviceId", "email", "userId"]


def decode(value: str) -> str:
    """Decode a value."""
    return b64decode(value).decode(ENCODING)


@overload
def redact(data: Mapping) -> dict:  # type: ignore[misc]
    ...


@overload
def redact(data: _T) -> _T:
    ...


def redact(data: _T) -> _T:
    """Redact sensitive data in a dict."""
    if not isinstance(data, (Mapping, list)):
        return data

    if isinstance(data, list):
        return cast(_T, [redact(val) for val in data])

    redacted = {**data}

    for key, value in redacted.items():
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        if key in REDACT_FIELDS:
            redacted[key] = REDACTED
        elif isinstance(value, Mapping):
            redacted[key] = redact(value)
        elif isinstance(value, list):
            redacted[key] = [redact(item) for item in value]

    return cast(_T, redacted)
