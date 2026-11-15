import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def valid_spec() -> dict:
    return {
        "name": "aria",
        "display_name": "Aria Vale",
        "bio": "AI-generated virtual model. fitness & lifestyle.",
        "disclosure": "AI-generated virtual model",
        "identity": {
            "reference_dir": "assets/personas/aria/reference",
            "style_prompt": "photo of a 26-year-old woman, auburn hair",
            "negative_prompt": "deformed, watermark",
        },
        "content": {
            "rating": "pg13",
            "themes": ["gym session, leggings and crop top",
                        "morning coffee at a cafe"],
            "banned": ["nudity", "explicit", "gore"],
        },
        "posting": {"cadence_per_week": 4, "platforms": ["instagram"]},
    }


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("IC_DB", str(tmp_path / "test.db"))
    from src.instacampaign import db
    db.init_db()
    return db
