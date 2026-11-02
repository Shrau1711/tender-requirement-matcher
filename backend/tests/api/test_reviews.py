import io

from openpyxl import load_workbook
from test_api import client, folders, upload  # noqa: F401

from app.reporting.review_key import row_key


def started(c):
    return upload(c).json()["id"]


def first_key(c, run_id):
    maker = c.get(f"/runs/{run_id}/report").json()["makers"][0]
    item, row = maker["items"][0], maker["items"][0]["rows"][0]
    return row_key(maker["manufacturer"], item["item"], row["attribute"], row["wanted"], row["tender_page"])


def test_the_row_key_is_plain_json_the_frontend_can_build_too():
    assert row_key("Acme", "Pump", "head", "20 m", 3) == '["Acme","Pump","head","20 m",3]'


def test_a_decision_is_saved_changed_and_cleared(folders):  # noqa: F811
    c = client(folders)
    run_id = started(c)
    key = first_key(c, run_id)
    assert c.get(f"/runs/{run_id}/reviews").json() == []
    saved = c.put(f"/runs/{run_id}/reviews", json={"items": [{"key": key, "decision": "confirmed", "note": "checked p4"}]}).json()
    assert [(r["decision"], r["note"], r["status"]) for r in saved] == [("confirmed", "checked p4", None)]
    changed = c.put(f"/runs/{run_id}/reviews", json={"items": [{"key": key, "decision": "changed", "status": "fully matched"}]}).json()
    assert [(r["decision"], r["status"]) for r in changed] == [("changed", "fully matched")]
    assert c.put(f"/runs/{run_id}/reviews", json={"items": [{"key": key, "decision": None}]}).json() == []


def test_a_change_must_say_what_the_status_should_be_and_unknown_runs_have_no_reviews(folders):  # noqa: F811
    c = client(folders)
    run_id = started(c)
    assert c.put(f"/runs/{run_id}/reviews", json={"items": [{"key": "k", "decision": "changed"}]}).status_code == 422
    assert c.put(f"/runs/{run_id}/reviews", json={"items": [{"key": "k", "decision": "confirmed", "status": "bogus"}]}).status_code == 422
    assert c.get("/runs/nope/reviews").status_code == 404


def test_deleting_a_run_deletes_its_decisions(folders):  # noqa: F811
    c = client(folders)
    run_id = started(c)
    c.put(f"/runs/{run_id}/reviews", json={"items": [{"key": first_key(c, run_id), "decision": "confirmed"}]})
    c.delete(f"/runs/{run_id}")
    assert c.app.state.reviews.all(run_id) == []


def test_the_excel_report_has_a_sheet_per_manufacturer_and_the_decisions(folders):  # noqa: F811
    c = client(folders)
    run_id = started(c)
    c.put(f"/runs/{run_id}/reviews", json={"items": [{"key": first_key(c, run_id), "decision": "changed", "status": "partially matched", "note": "see p2"}]})
    got = c.get(f"/runs/{run_id}/report.xlsx")
    assert got.status_code == 200 and "spreadsheetml" in got.headers["content-type"]
    wb = load_workbook(io.BytesIO(got.content))
    assert wb.sheetnames[0] == "Summary" and wb.sheetnames[-1] == "To confirm" and len(wb.sheetnames) >= 3
    sheet = wb[wb.sheetnames[1]]
    assert sheet["M2"].value == "Changed: partially matched" and sheet["N2"].value == "see p2"


def test_a_run_can_be_renamed_and_the_interface_can_read_the_limits(folders):  # noqa: F811
    c = client(folders)
    run_id = started(c)
    assert c.patch(f"/runs/{run_id}", json={"name": "  Pump tender  "}).json()["tender"] == "Pump tender"
    assert c.patch(f"/runs/{run_id}", json={"name": ""}).status_code == 422
    assert set(c.get("/config").json()) == {"max_model_calls", "max_upload_mb"}


def test_a_running_job_can_report_what_it_is_doing(folders):  # noqa: F811
    from app.pipeline.runner import execute

    c = client(folders)
    run_id = c.app.state.store.create("t", "pumps").id
    seen = []

    def talking(run_id, tender_dir, category_dir, name, progress):
        progress("Searching")
        seen.append(c.app.state.store.get(run_id).progress)
        return "{}", "calls"

    execute(c.app.state.store, run_id, None, None, "t", talking)
    assert seen == ["Searching"] and c.app.state.store.get(run_id).progress is None
