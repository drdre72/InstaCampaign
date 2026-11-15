import pytest

from src.instacampaign.comfy import ComfyClient, ComfyError, fill_workflow

RAW = (
    '{"3": {"inputs": {"seed": {{SEED}}, "steps": 28}, "class_type": "KSampler"},'
    ' "6": {"inputs": {"text": "{{PROMPT}}"}, "class_type": "CLIPTextEncode"},'
    ' "7": {"inputs": {"text": "{{NEGATIVE}}"}, "class_type": "CLIPTextEncode"},'
    ' "9": {"inputs": {"filename_prefix": "{{PREFIX}}"},'
    ' "class_type": "SaveImage"}}'
)


def test_fill_workflow_substitutes():
    wf = fill_workflow(RAW, prompt='a "quoted" prompt', seed=42,
                     prefix="run-00", negative="bad")
    assert wf["3"]["inputs"]["seed"] == 42
    assert wf["6"]["inputs"]["text"] == 'a "quoted" prompt'
    assert wf["7"]["inputs"]["text"] == "bad"
    assert wf["9"]["inputs"]["filename_prefix"] == "run-00"


def test_fill_workflow_newline_safe():
    wf = fill_workflow(RAW, prompt="line1\nline2", seed=1, prefix="p")
    assert wf["6"]["inputs"]["text"] == "line1\nline2"


def test_fill_workflow_bad_template():
    with pytest.raises(ComfyError):
        fill_workflow("{not json {{SEED}}", prompt="x", seed=1, prefix="p")


def test_submit_posts_prompt(monkeypatch):
    client = ComfyClient(base="http://127.0.0.1:9", timeout_s=1)
    seen = {}

    def fake(method, path, body=None):
        seen["method"], seen["path"], seen["body"] = method, path, body
        return {"prompt_id": "abc"}

    monkeypatch.setattr(client, "_req", fake)
    assert client.submit({"n": {}}) == "abc"
    assert seen["method"] == "POST" and seen["path"] == "/prompt"
    assert seen["body"] == {"prompt": {"n": {}}}


def test_wait_returns_when_done(monkeypatch):
    client = ComfyClient(base="http://127.0.0.1:9", timeout_s=5)
    calls = []

    def fake_hist(pid):
        calls.append(pid)
        return {pid: {"outputs": {}}} if len(calls) >= 2 else {}

    monkeypatch.setattr(client, "history", fake_hist)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert client.wait("abc", poll_s=0) == {"outputs": {}}


def test_collect_errors_on_empty(monkeypatch):
    client = ComfyClient(base="http://127.0.0.1:9", timeout_s=5)
    monkeypatch.setattr(client, "wait", lambda pid: {"outputs": {"n": {}}})
    with pytest.raises(ComfyError, match="no images"):
        client.collect("abc")
