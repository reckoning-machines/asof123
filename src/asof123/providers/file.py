"""FileProvider: reads a `SourceStatus` from a local JSON file.

The file is read on every `report` call. There is no caching, no retry,
no background watching, no async, and no network IO. The JSON shape
maps directly into the fields of `SourceStatus`.

Fail-closed behavior: missing file, unreadable file, empty file,
invalid JSON, non-object payload, mismatched provider name, or a
payload that does not validate as a `SourceStatus` all raise
`ProviderReportError`. The resolver layer translates that into a
`SourceStatus` with `SourceFreshness.FAILED`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Union

from pydantic import ValidationError

from ..models import SourceStatus
from ._protocol import ProviderReportError


class FileProvider:
    """A SourceProvider that reads a fresh `SourceStatus` from disk on each call.

    The file must contain a single JSON object whose keys map directly
    to `SourceStatus` fields. If `provider` is omitted in the payload,
    the FileProvider's own `name` is used. If `provider` is present and
    disagrees with `name`, the call fails closed with
    `ProviderReportError`.
    """

    name: str

    def __init__(self, name: str, path: Union[str, Path]) -> None:
        if not name:
            raise ValueError("FileProvider name must be non-empty")
        self.name = name
        self._path = Path(path)

    def report(self, now_utc: datetime) -> SourceStatus:
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError as exc:
            raise ProviderReportError(
                f"FileProvider {self.name!r}: file not found at {self._path}"
            ) from exc
        except OSError as exc:
            raise ProviderReportError(
                f"FileProvider {self.name!r}: cannot read {self._path}: {exc}"
            ) from exc

        if not raw.strip():
            raise ProviderReportError(
                f"FileProvider {self.name!r}: empty file at {self._path}"
            )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderReportError(
                f"FileProvider {self.name!r}: invalid JSON at {self._path}: "
                f"{exc.msg}"
            ) from exc

        if not isinstance(payload, dict):
            raise ProviderReportError(
                f"FileProvider {self.name!r}: JSON payload at {self._path} "
                f"must be an object, got {type(payload).__name__}"
            )

        if payload.get("provider") is None:
            payload["provider"] = self.name
        elif payload["provider"] != self.name:
            raise ProviderReportError(
                f"FileProvider {self.name!r}: payload provider="
                f"{payload['provider']!r} does not match"
            )

        try:
            return SourceStatus(**payload)
        except ValidationError as exc:
            raise ProviderReportError(
                f"FileProvider {self.name!r}: invalid SourceStatus payload "
                f"at {self._path}: {exc.errors()}"
            ) from exc
