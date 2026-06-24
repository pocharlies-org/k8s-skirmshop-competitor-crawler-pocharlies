"""Transport boundary for the cart-probe (mock-only, no live HTTP).

F4 never issues real HTTP from this package. Probers depend only on the
:class:`ProbeTransport` Protocol and the :class:`ProbeResponse` value object, so
tests inject a scripted fake transport. A live transport (requests/httpx) can
later implement the same Protocol without touching prober logic.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, Optional, Protocol, runtime_checkable


class TransportError(Exception):
    """Raised by a transport when a request cannot complete (timeout/IO)."""


@dataclasses.dataclass(frozen=True)
class ProbeResponse:
    """Normalised response from a single cart operation.

    ``json_body`` is the decoded JSON body (``None`` when there is none) and
    ``is_challenge`` flags an anti-bot challenge interstitial.
    """

    status_code: int
    json_body: Optional[Dict[str, Any]] = None
    is_challenge: bool = False

    def json(self) -> Dict[str, Any]:
        """Return the decoded JSON body, or an empty dict when there is none."""
        return dict(self.json_body) if self.json_body is not None else {}


@runtime_checkable
class ProbeTransport(Protocol):
    """Minimal request transport for the cart-probe.

    Implementations raise :class:`TransportError` on IO failure and return a
    :class:`ProbeResponse` otherwise.
    """

    def request(
        self, method: str, url: str, json: Optional[Dict[str, Any]] = None
    ) -> ProbeResponse: ...


__all__ = [
    "TransportError",
    "ProbeResponse",
    "ProbeTransport",
]
