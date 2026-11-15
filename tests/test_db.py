def test_persona_plan_render_approval_flow(tmp_db, valid_spec):
    pid = tmp_db.insert_persona("aria", valid_spec, "sha-persona")
    assert tmp_db.get_persona("aria")["id"] == pid

    plan = {"name": "p", "persona": "aria", "items": [{}]}
    plid = tmp_db.insert_plan(pid, "p", plan, "sha-plan")
    tmp_db.set_plan_status(plid, "rendered")
    assert tmp_db.get_plan(plid)["status"] == "rendered"

    rid = tmp_db.insert_render(plid, 0, "out.png", "sha-render")
    tmp_db.set_render_status(rid, "rendered", "pass")
    tmp_db.insert_approval(rid, "sha-render", "operator")
    assert tmp_db.approved_sha(rid) == "sha-render"
    tmp_db.set_render_status(rid, "exported")
    tmp_db.insert_post(rid, "instagram", None, None, "exported")
    assert tmp_db.get_render(rid)["status"] == "exported"


def test_events_are_append_only(tmp_db):
    tmp_db.event("custom", a=1)
    tmp_db.event("custom", a=2)
    with tmp_db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE kind='custom'").fetchall()
    assert len(rows) == 2


def test_render_uniqueness_per_item(tmp_db, valid_spec):
    pid = tmp_db.insert_persona("aria", valid_spec, "sha")
    plid = tmp_db.insert_plan(pid, "p", {"items": []}, "sha-plan")
    tmp_db.insert_render(plid, 0, "a.png", "s1")
    import sqlite3
    try:
        tmp_db.insert_render(plid, 0, "b.png", "s2")
        assert False, "expected unique constraint"
    except sqlite3.IntegrityError:
        pass
