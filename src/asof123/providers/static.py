"""StaticProvider: returns a fixed `SourceStatus` on every call.

Useful for tests, demos, and any caller that needs a deterministic
fixture-style `SourceProvider` with no IO.
"""

from __future__ import annotations

from datetime import datetime

from ..models import SourceStatus


class StaticProvider:
    """A SourceProvider that returns the same SourceStatus on every call.

    The status is captured at construction time. `report(now_utc)`
    ignores the input clock, performs no IO, does not retry, and does
    not mutate the stored status.

    If the supplied `SourceStatus` has no `provider`, the constructor
    fills it in with the StaticProvider's own `name`. If
    `status.provider` is set and differs from `name`, the constructor
    raises `ValueError`; this catches misregistration where a fixture
    is wired to the wrong provider key.
    """

    name: str

    def __init__(self, name: str, status: SourceStatus) -> None:
        if not name:
            raise ValueError("StaticProvider name must be non-empty")
        if status.provider is None:
            status = status.model_copy(update={"provider": name})
        elif status.provider != name:
            raise ValueError(
                f"StaticProvider name={name!r} does not match "
                f"status.provider={status.provider!r}"
            )
        self.name = name
        self._status = status

    def report(self, now_utc: datetime) -> SourceStatus:
        return self._status
