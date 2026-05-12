"""SourceProvider protocol and concrete provider implementations.

Public surface:

- `SourceProvider`, `ProviderReportError`: the protocol every provider
  satisfies and the domain exception providers raise when they prefer to
  fail closed.
- `StaticProvider`: returns a fixed SourceStatus on every report.
- `FileProvider`: reads a local JSON file and converts it to a
  SourceStatus on every report.

No FastAPI, CLI, persistence, scheduling, async, network, or database
behavior. The static and file providers are sufficient for unit tests,
local demos, and replay-safe fixtures.
"""

from ._protocol import ProviderReportError, SourceProvider
from .file import FileProvider
from .static import StaticProvider

__all__ = [
    "SourceProvider",
    "ProviderReportError",
    "StaticProvider",
    "FileProvider",
]
