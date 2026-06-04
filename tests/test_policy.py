"""Tests for SourcePolicy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

import asof123
from asof123.enums import Perspective, SourceFreshness
from asof123.models import SourceStatus
from asof123.policy import SourcePolicy, apply_source_policy


NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)
PAST = datetime(2026, 2, 10, 21, 0, 0, tzinfo=timezone.utc)


def test_source_policy_defaults_are_empty():
    policy = SourcePolicy()
    assert policy.required_sources == frozenset()
    assert policy.max_age_seconds is None
    assert policy.max_age_seconds_by_source == {}
    assert policy.max_age_for("quotes") is None


def test_source_policy_is_exported_from_package_surface():
    assert asof123.SourcePolicy is SourcePolicy
    assert asof123.apply_source_policy is apply_source_policy


def test_source_policy_accepts_required_sources_and_age_overrides():
    policy = SourcePolicy(
        required_sources={"quotes", "actions"},
        max_age_seconds=300,
        max_age_seconds_by_source={"actions": 900},
    )
    assert policy.required_sources == frozenset({"quotes", "actions"})
    assert policy.max_age_for("quotes") == 300
    assert policy.max_age_for("actions") == 900


def test_source_policy_deduplicates_required_sources_intentionally():
    policy = SourcePolicy(required_sources=["quotes", "quotes", "actions"])
    assert policy.required_sources == frozenset({"quotes", "actions"})


def test_source_policy_max_age_overrides_are_immutable():
    policy = SourcePolicy(max_age_seconds_by_source={"quotes": 60})
    with pytest.raises(TypeError):
        policy.max_age_seconds_by_source["quotes"] = 120
    with pytest.raises(TypeError):
        policy.max_age_seconds_by_source.update({"actions": 300})


def test_source_policy_default_max_age_overrides_are_immutable():
    policy = SourcePolicy()
    with pytest.raises(TypeError):
        policy.max_age_seconds_by_source["quotes"] = 60


def test_source_policy_rejects_empty_required_source_name():
    with pytest.raises(ValidationError):
        SourcePolicy(required_sources={""})


def test_source_policy_rejects_string_required_sources():
    with pytest.raises(ValidationError):
        SourcePolicy(required_sources="quotes")


def test_source_policy_rejects_non_positive_max_age():
    with pytest.raises(ValidationError):
        SourcePolicy(max_age_seconds=0)
    with pytest.raises(ValidationError):
        SourcePolicy(max_age_seconds_by_source={"quotes": -1})


def test_source_policy_rejects_empty_age_override_key():
    with pytest.raises(ValidationError):
        SourcePolicy(max_age_seconds_by_source={"": 10})


def test_apply_source_policy_adds_missing_required_source():
    result = apply_source_policy(
        perspective=Perspective.PRE_TRADE_INTENT,
        knowledge_cutoff_utc=NOW,
        now_utc=NOW,
        sources={},
        policy=SourcePolicy(required_sources={"quotes"}),
    )

    assert result["quotes"].provider == "quotes"
    assert result["quotes"].freshness is SourceFreshness.MISSING
    assert result["quotes"].reason_code == "REQUIRED_SOURCE_MISSING"


def test_apply_source_policy_marks_replay_source_after_cutoff_not_published():
    source = SourceStatus(
        provider="warehouse",
        freshness=SourceFreshness.FRESH,
        timestamp_utc=PAST + timedelta(hours=1),
        timestamp_name="warehouse_loaded_at",
    )

    result = apply_source_policy(
        perspective=Perspective.REPLAY,
        knowledge_cutoff_utc=PAST,
        now_utc=PAST,
        sources={"warehouse": source},
        policy=SourcePolicy(required_sources={"warehouse"}),
    )

    status = result["warehouse"]
    assert status.freshness is SourceFreshness.NOT_PUBLISHED
    assert status.reason_code == "SOURCE_NOT_ADMISSIBLE"
    assert status.metadata["policy"]["previous_freshness"] == "FRESH"
    assert "timestamp_utc" in (status.explanation or "")
    assert status.timestamp_name == "warehouse_loaded_at"


def test_apply_source_policy_marks_old_source_stale():
    source = SourceStatus(
        provider="quotes",
        freshness=SourceFreshness.FRESH,
        timestamp_utc=NOW - timedelta(minutes=5),
        timestamp_name="vendor_updated_at",
    )

    result = apply_source_policy(
        perspective=Perspective.PRE_TRADE_INTENT,
        knowledge_cutoff_utc=NOW,
        now_utc=NOW,
        sources={"quotes": source},
        policy=SourcePolicy(max_age_seconds=60),
    )

    assert result["quotes"].freshness is SourceFreshness.STALE
    assert result["quotes"].reason_code == "SOURCE_STALE"
    assert result["quotes"].timestamp_name == "vendor_updated_at"


def test_apply_source_policy_preserves_provider_diagnostics_in_metadata():
    source = SourceStatus(
        provider="quotes",
        freshness=SourceFreshness.FRESH,
        last_update_utc=NOW - timedelta(minutes=5),
        reason_code="PROVIDER_LAG",
        explanation="Provider lagged.",
        metadata={"partition": "slow"},
    )

    result = apply_source_policy(
        perspective=Perspective.PRE_TRADE_INTENT,
        knowledge_cutoff_utc=NOW,
        now_utc=NOW,
        sources={"quotes": source},
        policy=SourcePolicy(max_age_seconds=60),
    )

    status = result["quotes"]
    assert status.metadata["partition"] == "slow"
    assert status.metadata["policy"]["previous_reason_code"] == "PROVIDER_LAG"
    assert status.metadata["policy"]["previous_explanation"] == "Provider lagged."
    assert status.metadata["policy"]["reason_code"] == "SOURCE_STALE"


def test_apply_source_policy_is_deterministic_and_does_not_mutate_inputs():
    source = SourceStatus(
        provider="quotes",
        freshness=SourceFreshness.FRESH,
        last_update_utc=NOW - timedelta(minutes=5),
        metadata={"a": {"b": 1}},
    )
    sources = {"quotes": source}
    before = source.model_dump(mode="json")
    policy = SourcePolicy(
        required_sources={"quotes", "actions"},
        max_age_seconds=60,
    )

    first = apply_source_policy(
        perspective=Perspective.PRE_TRADE_INTENT,
        knowledge_cutoff_utc=NOW,
        now_utc=NOW,
        sources=sources,
        policy=policy,
    )
    second = apply_source_policy(
        perspective=Perspective.PRE_TRADE_INTENT,
        knowledge_cutoff_utc=NOW,
        now_utc=NOW,
        sources=sources,
        policy=policy,
    )

    assert first == second
    assert source.model_dump(mode="json") == before
    assert set(sources) == {"quotes"}
    assert set(first) == {"quotes", "actions"}
