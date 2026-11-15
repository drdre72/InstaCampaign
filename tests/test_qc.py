from pathlib import Path

from src.instacampaign.qc import media_gate, run_qc, sfw_gate


def _png(tmp_path: Path) -> Path:
    from PIL import Image
    p = tmp_path / "gen.png"
    Image.new("RGB", (832, 1216), (128, 64, 200)).save(p)
    return p


def test_media_gate_accepts_image(tmp_path):
    assert media_gate(_png(tmp_path))["status"] == "pass"


def test_media_gate_rejects_garbage(tmp_path):
    p = tmp_path / "bad.png"
    p.write_bytes(b"not an image")
    assert media_gate(p)["status"] == "fail"


def test_media_gate_rejects_unknown_ext(tmp_path):
    p = tmp_path / "x.gif"
    p.write_bytes(b"x")
    assert media_gate(p)["status"] == "fail"


def test_sfw_gate_fails_closed_without_classifier(tmp_path, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "opennsfw2":
            raise ImportError("absent in test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    gate = sfw_gate(_png(tmp_path))
    assert gate["status"] == "needs_manual"


def test_run_qc_writes_artifact(tmp_path, valid_spec):
    qc = run_qc(_png(tmp_path), valid_spec,
              out_path=tmp_path / "qc.json")
    assert qc["status"] in ("pass", "needs_manual", "fail")
    assert (tmp_path / "qc.json").exists()
    assert {g["gate"] for g in qc["gates"]} == {"media", "sfw", "face"}
