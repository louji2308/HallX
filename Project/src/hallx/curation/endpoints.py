"""Loopback endpoint parsing and identity normalisation."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True, slots=True)
class EndpointIdentity:
    host: str
    port: int


def endpoint_identity(value: str) -> EndpointIdentity | None:
    if not value or value != value.strip():
        return None
    try:
        parts = urlsplit(value)
        port = parts.port
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme != "http":
        return None
    if parts.username is not None or parts.password is not None:
        return None
    if parts.query or parts.fragment:
        return None
    if parts.path not in ("", "/"):
        return None
    if host is None or host not in _LOOPBACK_HOSTS:
        return None
    if port is None or not 1 <= port <= 65535:
        return None
    return EndpointIdentity(host="loopback", port=port)


def model_identity(value: str) -> str:
    return value.strip().casefold()
