import pytest
from test_budget import ONE, Plain, Saved, planned

from app.db.runs import RunStore
from app.services.approval import Approvals, Declined, ask_person
from app.services.estimate import make_estimate


def test_the_plan_knows_how_many_new_questions_it_will_ask_and_what_they_cost():
    result = planned(Plain(), budget=10 * ONE)
    assert result.questions == 3 and result.tokens > 0
    assert planned(Saved(), budget=10 * ONE).questions == 0 and planned(Saved(), budget=10 * ONE).tokens == 0


def test_an_estimate_gives_money_and_a_range_of_minutes():
    estimate = make_estimate(requirements=12, questions=80, tokens=400_000, notes=["cut"])
    assert estimate.rupees == 40 and 1 <= estimate.minutes_low < estimate.minutes_high and estimate.notes == ["cut"]


def test_nothing_new_to_ask_costs_nothing():
    assert make_estimate(12, 0, 0, []).rupees == 0


def waiting_run(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite")
    run = store.create("t", "valves")
    approvals = Approvals()
    approvals.require(run.id)
    return store, run.id, approvals


def test_a_run_shows_its_estimate_while_it_waits_and_goes_on_after_a_yes(tmp_path):
    store, run_id, approvals = waiting_run(tmp_path)
    approvals.answer(run_id, True)
    ask_person(store, run_id, make_estimate(3, 5, 1000, []), approvals, seconds=1)
    assert store.get(run_id).status == "running" and store.get(run_id).estimate.questions == 5


def test_a_no_stops_the_run(tmp_path):
    store, run_id, approvals = waiting_run(tmp_path)
    approvals.answer(run_id, False)
    with pytest.raises(Declined):
        ask_person(store, run_id, make_estimate(3, 5, 1000, []), approvals, seconds=1)
    assert store.get(run_id).status == "awaiting"  # execute() records the cancellation


def test_no_answer_in_time_counts_as_no(tmp_path):
    store, run_id, approvals = waiting_run(tmp_path)
    with pytest.raises(Declined):
        ask_person(store, run_id, make_estimate(3, 5, 1000, []), approvals, seconds=0.01)
    assert not approvals.required(run_id)


def test_a_restart_fails_runs_that_were_waiting_for_an_answer(tmp_path):
    store, run_id, _ = waiting_run(tmp_path)
    store.await_approval(run_id, make_estimate(1, 1, 1, []))
    store.fail_unfinished("restarted")
    assert store.get(run_id).status == "failed"

