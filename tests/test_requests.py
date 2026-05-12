"""Tests for the ResolveRequest model.

Covers per-Perspective cross-field rules (which datetime fields are
required, forbidden, or optional), the shared UTC / IANA / uppercase-market
validators, and the knowledge_cutoff_utc <= as_of_utc invariant.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from asof123.enums import Perspective
from asof123.requests import ResolveRequest


UTC_NOW = datetime(2026, 5, 12, 13, 45, 0, tzinfo=timezone.utc)
UTC_PAST = datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc)


# Happy paths


def test_live_request_without_utc_fields():
    req = ResolveRequest(
        perspective=Perspective.LIVE,
        market="XNYS",
        market_timezone="America/New_York",
    )
    assert req.perspective is Perspective.LIVE
    assert req.as_of_utc is None
    assert req.knowledge_cutoff_utc is None


def test_replay_request_with_both_utc_fields():
    req = ResolveRequest(
        perspective=Perspective.REPLAY,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=UTC_PAST,
        knowledge_cutoff_utc=UTC_PAST,
    )
    assert req.as_of_utc == UTC_PAST
    assert req.knowledge_cutoff_utc == UTC_PAST


def test_historical_request_with_both_utc_fields():
    req = ResolveRequest(
        perspective=Perspective.HISTORICAL,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=UTC_PAST,
        knowledge_cutoff_utc=UTC_PAST,
    )
    assert req.perspective is Perspective.HISTORICAL


def test_preview_request_with_only_knowledge_cutoff():
    req = ResolveRequest(
        perspective=Perspective.PREVIEW,
        market="XNYS",
        market_timezone="America/New_York",
        knowledge_cutoff_utc=UTC_PAST,
    )
    assert req.as_of_utc is None
    assert req.knowledge_cutoff_utc == UTC_PAST


def test_pre_trade_intent_request_with_only_knowledge_cutoff():
    req = ResolveRequest(
        perspective=Perspective.PRE_TRADE_INTENT,
        market="XNYS",
        market_timezone="America/New_York",
        knowledge_cutoff_utc=UTC_PAST,
    )
    assert req.perspective is Perspective.PRE_TRADE_INTENT


def test_executed_request_with_both_utc_fields():
    req = ResolveRequest(
        perspective=Perspective.EXECUTED,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=UTC_NOW,
        knowledge_cutoff_utc=UTC_NOW,
    )
    assert req.perspective is Perspective.EXECUTED


def test_canonical_request_with_only_knowledge_cutoff():
    req = ResolveRequest(
        perspective=Perspective.CANONICAL,
        market="XNYS",
        market_timezone="America/New_York",
        knowledge_cutoff_utc=UTC_NOW,
    )
    assert req.perspective is Perspective.CANONICAL
    assert req.as_of_utc is None


# Failures: per-Perspective cross-field rules


def test_live_with_as_of_rejected():
    with pytest.raises(ValidationError, match="LIVE"):
        ResolveRequest(
            perspective=Perspective.LIVE,
            market="XNYS",
            market_timezone="America/New_York",
            as_of_utc=UTC_NOW,
        )


def test_live_with_knowledge_cutoff_rejected():
    with pytest.raises(ValidationError, match="LIVE"):
        ResolveRequest(
            perspective=Perspective.LIVE,
            market="XNYS",
            market_timezone="America/New_York",
            knowledge_cutoff_utc=UTC_NOW,
        )


def test_replay_without_as_of_rejected():
    with pytest.raises(ValidationError, match="REPLAY"):
        ResolveRequest(
            perspective=Perspective.REPLAY,
            market="XNYS",
            market_timezone="America/New_York",
            knowledge_cutoff_utc=UTC_PAST,
        )


def test_replay_without_knowledge_cutoff_rejected():
    with pytest.raises(ValidationError, match="REPLAY"):
        ResolveRequest(
            perspective=Perspective.REPLAY,
            market="XNYS",
            market_timezone="America/New_York",
            as_of_utc=UTC_PAST,
        )


def test_historical_missing_fields_rejected():
    with pytest.raises(ValidationError, match="HISTORICAL"):
        ResolveRequest(
            perspective=Perspective.HISTORICAL,
            market="XNYS",
            market_timezone="America/New_York",
        )


def test_canonical_with_as_of_rejected():
    with pytest.raises(ValidationError, match="CANONICAL"):
        ResolveRequest(
            perspective=Perspective.CANONICAL,
            market="XNYS",
            market_timezone="America/New_York",
            as_of_utc=UTC_NOW,
        )


# Failures: shared field validators


def test_naive_datetime_rejected():
    naive = datetime(2026, 5, 12, 13, 45, 0)
    with pytest.raises(ValidationError):
        ResolveRequest(
            perspective=Perspective.REPLAY,
            market="XNYS",
            market_timezone="America/New_York",
            as_of_utc=naive,
            knowledge_cutoff_utc=UTC_PAST,
        )


def test_non_utc_datetime_rejected():
    plus_two = datetime(2026, 5, 12, tzinfo=timezone(timedelta(hours=2)))
    with pytest.raises(ValidationError):
        ResolveRequest(
            perspective=Perspective.REPLAY,
            market="XNYS",
            market_timezone="America/New_York",
            as_of_utc=plus_two,
            knowledge_cutoff_utc=UTC_PAST,
        )


def test_est_abbreviation_rejected():
    with pytest.raises(ValidationError):
        ResolveRequest(
            perspective=Perspective.LIVE,
            market="XNYS",
            market_timezone="EST",
        )


def test_lowercase_market_rejected():
    with pytest.raises(ValidationError):
        ResolveRequest(
            perspective=Perspective.LIVE,
            market="xnys",
            market_timezone="America/New_York",
        )


# Failures: knowledge_cutoff > as_of and extra fields


def test_knowledge_cutoff_after_as_of_rejected():
    later = UTC_PAST + timedelta(days=1)
    with pytest.raises(ValidationError, match="knowledge_cutoff_utc"):
        ResolveRequest(
            perspective=Perspective.REPLAY,
            market="XNYS",
            market_timezone="America/New_York",
            as_of_utc=UTC_PAST,
            knowledge_cutoff_utc=later,
        )


def test_knowledge_cutoff_equal_to_as_of_accepted():
    req = ResolveRequest(
        perspective=Perspective.REPLAY,
        market="XNYS",
        market_timezone="America/New_York",
        as_of_utc=UTC_PAST,
        knowledge_cutoff_utc=UTC_PAST,
    )
    assert req.knowledge_cutoff_utc == req.as_of_utc


def test_extra_field_rejected():
    with pytest.raises(ValidationError):
        ResolveRequest(
            perspective=Perspective.LIVE,
            market="XNYS",
            market_timezone="America/New_York",
            unexpected_field="oops",
        )
