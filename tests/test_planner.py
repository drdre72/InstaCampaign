import pytest

from src.instacampaign.planner import (PlanError, build_plan, plan_sha256,
                                       validate_plan)


def test_deterministic_same_seed(valid_spec):
    a = build_plan(valid_spec, "2026-W47", seed=7)
    b = build_plan(valid_spec, "2026-W47", seed=7)
    assert a == b
    assert plan_sha256(a) == plan_sha256(b)


def test_different_seed_changes_plan(valid_spec):
    a = build_plan(valid_spec, "2026-W47", seed=7)
    b = build_plan(valid_spec, "2026-W47", seed=8)
    assert a != b


def test_cadence_from_spec(valid_spec):
    plan = build_plan(valid_spec, "2026-W47", seed=7)
    assert len(plan["items"]) == 4


def test_items_carry_disclosure(valid_spec):
    plan = build_plan(valid_spec, "2026-W47", seed=7)
    for item in plan["items"]:
        assert "#AIGenerated" in item["caption"]


def test_validate_rejects_drifted_spec(valid_spec):
    plan = build_plan(valid_spec, "2026-W47", seed=7)
    valid_spec["display_name"] = "Someone Else"
    with pytest.raises(PlanError, match="spec changed"):
        validate_plan(plan, valid_spec)


def test_validate_rejects_banned_injection(valid_spec):
    plan = build_plan(valid_spec, "2026-W47", seed=7)
    plan["items"][0]["prompt"] += ", explicit pose"
    with pytest.raises(PlanError, match="banned"):
        validate_plan(plan, valid_spec)


def test_no_items_rejected(valid_spec):
    plan = build_plan(valid_spec, "2026-W47", seed=7)
    plan["items"] = []
    with pytest.raises(PlanError, match="no items"):
        validate_plan(plan, valid_spec)
