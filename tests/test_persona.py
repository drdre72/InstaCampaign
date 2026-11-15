import pytest

from src.instacampaign.persona import PersonaError, spec_sha, validate


def test_valid_spec_normalizes(valid_spec):
    out = validate(valid_spec)
    assert out["name"] == "aria"
    assert out["content"]["rating"] == "pg13"
    assert isinstance(spec_sha(out), str)


def test_missing_key_rejected(valid_spec):
    del valid_spec["identity"]
    with pytest.raises(PersonaError, match="identity"):
        validate(valid_spec)


def test_disclosure_required(valid_spec):
    valid_spec["disclosure"] = ""
    with pytest.raises(PersonaError, match="disclosure"):
        validate(valid_spec)


def test_disclosure_must_mean_ai(valid_spec):
    valid_spec["disclosure"] = "just a girl who loves the gym"
    with pytest.raises(PersonaError, match="disclosure"):
        validate(valid_spec)


def test_explicit_rating_rejected(valid_spec):
    valid_spec["content"]["rating"] = "explicit"
    with pytest.raises(PersonaError, match="rating"):
        validate(valid_spec)


def test_banned_minimum_enforced(valid_spec):
    valid_spec["content"]["banned"] = ["nudity"]
    with pytest.raises(PersonaError, match="banned"):
        validate(valid_spec)


def test_banned_term_in_theme_rejected(valid_spec):
    valid_spec["content"]["themes"].append("tasteful nudity shoot")
    with pytest.raises(PersonaError, match="banned"):
        validate(valid_spec)


def test_cadence_bounds(valid_spec):
    valid_spec["posting"]["cadence_per_week"] = 0
    with pytest.raises(PersonaError, match="cadence"):
        validate(valid_spec)
    valid_spec["posting"]["cadence_per_week"] = 99
    with pytest.raises(PersonaError, match="cadence"):
        validate(valid_spec)
