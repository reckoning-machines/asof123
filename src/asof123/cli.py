"""asof123 CLI: a thin local wrapper over `resolve`, `make_snapshot`, and
`create_app`.

Subcommands:

    asof123 resolve   Build a AsOfRequest, resolve in-process, print the
                      AsOf as JSON.
    asof123 snapshot  Resolve and wrap the result in an AsOfSnapshot, print
                      the snapshot as JSON.
    asof123 serve     Run the FastAPI reference app via uvicorn (lazy
                      import; install asof123[serve] or asof123[api] plus
                      uvicorn).

No persistent config, no environment loading, no mutable registry, no
background work. Each invocation is a fresh in-process call.

JSON output uses `json.dumps(..., sort_keys=True, indent=2)` so two
identical invocations produce byte-equal output. Datetime inputs to
`--as-of-utc` and `--knowledge-cutoff-utc` are parsed strictly: they
must be ISO 8601, must carry a timezone, and must be UTC (offset
+00:00). A naive datetime, a non-UTC offset, or a malformed string is a
hard error at argparse time.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Optional

from pydantic import ValidationError

from .calendars import XNYSCalendar
from .enums import Perspective
from .errors import ErrorReasonCode, ErrorResponse
from .policy import SourcePolicy
from .providers import FileProvider
from .requests import AsOfRequest
from .resolver import ResolverError, resolve
from .snapshot import make_snapshot


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise argparse.ArgumentTypeError("datetime must be a non-empty string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid ISO 8601 datetime: {value!r}: {exc}"
        ) from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            f"datetime {value!r} must be timezone-aware; naive datetimes are not allowed"
        )
    if dt.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError(
            f"datetime {value!r} must be UTC (offset +00:00); got {dt.utcoffset()}"
        )
    return dt


def _parse_source_file(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            f"--source-file must be name=path, got {value!r}"
        )
    name, _, path = value.partition("=")
    if not name or not path:
        raise argparse.ArgumentTypeError(
            f"--source-file must be name=path with non-empty parts, got {value!r}"
        )
    return name, path


def _parse_positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"value must be a positive integer, got {value!r}"
        ) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(
            f"value must be a positive integer, got {value!r}"
        )
    return parsed


def _parse_max_age_source(value: str) -> tuple[str, int]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            f"--max-age-source must be name=seconds, got {value!r}"
        )
    name, _, seconds = value.partition("=")
    if not name or not seconds:
        raise argparse.ArgumentTypeError(
            f"--max-age-source must be name=seconds with non-empty parts, got {value!r}"
        )
    return name, _parse_positive_int(seconds)


def _add_resolve_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--perspective",
        default=Perspective.LIVE.value,
        choices=[m.value for m in Perspective],
        help=(
            "Temporal perspective; defaults to LIVE. One of: "
            + ", ".join(m.value for m in Perspective)
        ),
    )
    p.add_argument("--market", default="XNYS")
    p.add_argument("--market-timezone", default="America/New_York")
    p.add_argument("--as-of-utc", type=_parse_utc, default=None)
    p.add_argument("--knowledge-cutoff-utc", type=_parse_utc, default=None)
    p.add_argument(
        "--source-file",
        type=_parse_source_file,
        action="append",
        default=None,
        help=(
            "Add a FileProvider in the form name=path. May be repeated. "
            "Each provider reads its SourceStatus from the named JSON file."
        ),
    )
    p.add_argument(
        "--required-source",
        action="append",
        default=None,
        help=(
            "Require a source by name. May be repeated. Missing required "
            "sources become explicit MISSING SourceStatus entries."
        ),
    )
    p.add_argument(
        "--max-age-seconds",
        type=_parse_positive_int,
        default=None,
        help="Default max age in seconds for sources with last_update_utc.",
    )
    p.add_argument(
        "--max-age-source",
        type=_parse_max_age_source,
        action="append",
        default=None,
        help=(
            "Per-source max age in the form name=seconds. May be repeated. "
            "Overrides --max-age-seconds for that source."
        ),
    )


def _build_request(args: argparse.Namespace) -> AsOfRequest:
    return AsOfRequest(
        perspective=Perspective(args.perspective),
        market=args.market,
        market_timezone=args.market_timezone,
        as_of_utc=args.as_of_utc,
        knowledge_cutoff_utc=args.knowledge_cutoff_utc,
    )


def _build_providers(args: argparse.Namespace) -> list[FileProvider]:
    if not args.source_file:
        return []
    return [FileProvider(name, path) for name, path in args.source_file]


def _build_policy(args: argparse.Namespace) -> SourcePolicy | None:
    required_sources = frozenset(args.required_source or [])
    max_age_by_source: dict[str, int] = {}
    for name, seconds in args.max_age_source or []:
        if name in max_age_by_source:
            raise ValueError(f"Duplicate --max-age-source for {name!r}")
        max_age_by_source[name] = seconds
    if (
        not required_sources
        and args.max_age_seconds is None
        and not max_age_by_source
    ):
        return None
    return SourcePolicy(
        required_sources=required_sources,
        max_age_seconds=args.max_age_seconds,
        max_age_seconds_by_source=max_age_by_source,
    )


def _print_json(payload: object, stream) -> None:
    stream.write(json.dumps(payload, sort_keys=True, indent=2))
    stream.write("\n")


def _print_error(
    stream,
    *,
    error: str,
    reason_code: ErrorReasonCode,
    explanation: str,
    details: object = None,
) -> None:
    payload = ErrorResponse(
        error=error,
        reason_code=reason_code,
        explanation=explanation,
        details=details,
    )
    _print_json(payload.model_dump(mode="json"), stream)


def _cmd_resolve(args: argparse.Namespace, stdout, stderr) -> int:
    try:
        request = _build_request(args)
    except ValidationError as exc:
        _print_error(
            stderr,
            error="VALIDATION_ERROR",
            reason_code=ErrorReasonCode.INVALID_REQUEST,
            explanation="Invalid resolve request",
            details=exc.errors(include_context=False),
        )
        return 2
    try:
        providers = _build_providers(args)
        policy = _build_policy(args)
    except (ValueError, ValidationError) as exc:
        _print_error(
            stderr,
            error="VALIDATION_ERROR",
            reason_code=ErrorReasonCode.INVALID_PROVIDER,
            explanation=str(exc),
        )
        return 2

    calendars = {"XNYS": XNYSCalendar()}
    try:
        asof = resolve(request, calendars, providers, policy=policy)
    except ResolverError as exc:
        _print_error(
            stderr,
            error="RESOLVER_ERROR",
            reason_code=exc.reason_code,
            explanation=exc.explanation,
        )
        return 2

    _print_json(asof.model_dump(mode="json"), stdout)
    return 0


def _cmd_snapshot(args: argparse.Namespace, stdout, stderr) -> int:
    try:
        request = _build_request(args)
    except ValidationError as exc:
        _print_error(
            stderr,
            error="VALIDATION_ERROR",
            reason_code=ErrorReasonCode.INVALID_REQUEST,
            explanation="Invalid resolve request",
            details=exc.errors(include_context=False),
        )
        return 2
    try:
        providers = _build_providers(args)
        policy = _build_policy(args)
    except (ValueError, ValidationError) as exc:
        _print_error(
            stderr,
            error="VALIDATION_ERROR",
            reason_code=ErrorReasonCode.INVALID_PROVIDER,
            explanation=str(exc),
        )
        return 2

    calendars = {"XNYS": XNYSCalendar()}
    try:
        asof = resolve(request, calendars, providers, policy=policy)
    except ResolverError as exc:
        _print_error(
            stderr,
            error="RESOLVER_ERROR",
            reason_code=exc.reason_code,
            explanation=exc.explanation,
        )
        return 2

    try:
        snapshot = make_snapshot(asof, args.snapshot_id)
    except ValidationError as exc:
        _print_error(
            stderr,
            error="VALIDATION_ERROR",
            reason_code=ErrorReasonCode.INVALID_SNAPSHOT,
            explanation="Invalid snapshot request",
            details=exc.errors(include_context=False),
        )
        return 2

    _print_json(snapshot.model_dump(mode="json"), stdout)
    return 0


def _cmd_serve(args: argparse.Namespace, stdout, stderr) -> int:
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        _print_error(
            stderr,
            error="VALIDATION_ERROR",
            reason_code=ErrorReasonCode.NOT_IMPLEMENTED,
            explanation=(
                "uvicorn is not installed; install with "
                "'pip install asof123[serve]' or add uvicorn manually"
            ),
        )
        return 2

    from .api import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asof123")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve_p = sub.add_parser(
        "resolve",
        help="Resolve an AsOf and print it as JSON",
    )
    _add_resolve_args(resolve_p)

    snapshot_p = sub.add_parser(
        "snapshot",
        help=(
            "Resolve an AsOf, wrap it in an AsOfSnapshot, "
            "and print the snapshot as JSON"
        ),
    )
    _add_resolve_args(snapshot_p)
    snapshot_p.add_argument("--snapshot-id", required=True)

    serve_p = sub.add_parser(
        "serve",
        help="Run the FastAPI reference app via uvicorn",
    )
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    stdout = sys.stdout
    stderr = sys.stderr

    if args.command == "resolve":
        return _cmd_resolve(args, stdout, stderr)
    if args.command == "snapshot":
        return _cmd_snapshot(args, stdout, stderr)
    if args.command == "serve":
        return _cmd_serve(args, stdout, stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
