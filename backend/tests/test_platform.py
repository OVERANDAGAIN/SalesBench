from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import os
import subprocess
import sys
from threading import Event
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, inspect, select, text

from app.main import create_app
from app.persistence import ActionReceipt, BatchReceipt, JournalEntry, MarketSession, OutboxNotice, Publication, Resolution, SemanticEvent
from app.service import CommitUnknown, MarketService, ServiceError
from salesbench_engine.actions import CreateListing, Procure, Purchase, SendPrivate, UpdateListing, Wait
from salesbench_engine import Engine
from salesbench_engine.runner.codec import canonical, digest

from helpers import create_market, prepare_buyers, queue_purchases, request_for, submit_wave


def test_empty_schema_migration_and_model_schema_match(store):
    tables = set(inspect(store["engine"]).get_table_names())
    assert tables == {"market_sessions", "actor_bindings", "actor_projections", "publications", "batch_receipts", "action_receipts",
                      "journal_entries", "resolutions", "semantic_events", "outbox_notices", "alembic_version",
                      "metric_snapshots", "leaderboard_snapshots"}
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with store["engine"].begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")  # Re-running upgrade is safe.
        command.check(cfg)
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "sb_metrics_001"


def test_duplicate_request_persists_across_service_instances_and_only_one_purchase(store):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    sid, tokens = created["session_id"], created["actor_tokens"]
    requests = queue_purchases(service, created)
    fresh = MarketService(store["sessions"])
    with ThreadPoolExecutor(max_workers=6) as pool:
        replies = list(pool.map(lambda _: fresh.submit(sid, tokens["buyer"], requests["buyer"]), range(12)))
    assert all(r["replayed"] and r["status"] == "pending" for r in replies)
    assert fresh.run_ready(sid)["runtime"]["published_version"] == 3
    assert fresh.submit(sid, tokens["buyer"], requests["buyer"])["replayed"]
    state = fresh.recover(sid).economic_state()
    assert len(state.orders) == 1
    assert sum(a.balance_cents for a in state.accounts) == 3000
    with store["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(ActionReceipt).where(ActionReceipt.action["type"].astext == "purchase")) == 2
        assert db.scalar(select(func.count()).select_from(SemanticEvent).where(SemanticEvent.payload["kind"].astext == "purchased")) == 1
        assert db.scalar(select(func.count()).select_from(Resolution).where(Resolution.purpose == "purchase")) == 1
    conflicting = deepcopy(requests["buyer"])
    conflicting["actions"][0]["quantity"] = 2
    with pytest.raises(ServiceError, match="ACTION_ID_CONFLICT"):
        fresh.submit(sid, tokens["buyer"], conflicting)


def test_stale_observation_rejected_durably_before_new_opportunity(store):
    service = store["service"]
    created = create_market(service)
    sid, tokens = created["session_id"], created["actor_tokens"]
    old = service.observe(sid, tokens["seller"])
    prepare_buyers(service, created)
    stale = request_for(old, (Wait(),), "stale-request")
    receipt = service.submit(sid, tokens["seller"], stale)
    assert receipt["code"] == "STALE_OBSERVATION"
    assert receipt["status"] == "rejected"
    assert service.submit(sid, tokens["seller"], stale)["replayed"]
    assert service.receipt(sid, tokens["seller"], "stale-request")["code"] == "STALE_OBSERVATION"
    assert service.recover(sid).economic_state().orders == ()


@pytest.mark.parametrize("price,code", [(250, "PRICE_CHANGED"), (300, "STALE_LISTING")])
def test_listing_price_and_aba_version_are_decided_by_engine(store, price, code):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created, seller_actions=lambda actor, obs: (
        CreateListing("seller/cup", "cup", 300, "Cup"), UpdateListing("seller/cup", unit_price_cents=400),
        UpdateListing("seller/cup", unit_price_cents=300)))
    requests = submit_wave(service, created, lambda actor, obs: (
        Purchase("seller/cup", 1, price, 1) if actor == "buyer" else Purchase("seller/cup", 1, 300, 3),))
    service.run_ready(created["session_id"])
    receipt = service.receipt(created["session_id"], created["actor_tokens"]["buyer"], requests["buyer"]["request_id"])
    assert receipt["status"] == "failed"
    assert receipt["outcomes"][0]["result"]["code"] == code
    state = service.recover(created["session_id"]).economic_state()
    assert [(o.buyer_id, o.offer_revision) for o in state.orders] == [("other-buyer", 3)]


def test_private_observation_receipt_and_session_binding_are_isolated_over_api(store):
    service = store["service"]
    created = create_market(service, two_sellers=True)
    sid, tokens = created["session_id"], created["actor_tokens"]
    prepare_buyers(service, created, seller_actions=lambda actor, obs: (
        CreateListing(actor + "/cup", "cup", 300, "Cup"), SendPrivate("buyer", "private-" + actor)))
    app = create_app(market_service=service, admin_token="admin-test", auto_run=False)
    with TestClient(app) as first, TestClient(app) as second:
        first.headers["Authorization"] = "Bearer " + tokens["buyer"]
        second.headers["Authorization"] = "Bearer " + tokens["other-buyer"]
        mine = first.get(f"/api/v1/sessions/{sid}/observation").json()
        theirs = second.get(f"/api/v1/sessions/{sid}/observation").json()
        assert mine["state"]["public"] == theirs["state"]["public"]
        assert len(mine["state"]["inbox"]["messages"]) == 2
        assert theirs["state"]["inbox"]["messages"] == []
        assert theirs["state"]["own"]["offers"] == []
        assert theirs["state"]["own"]["inventory"] == []
        assert "private-seller" not in canonical(theirs)
        purchase = request_for(mine, (Purchase("seller/cup", 1, 300, 1),), "private-receipt")
        assert first.post(f"/api/v1/sessions/{sid}/actions", json=purchase).status_code == 202
        assert second.get(f"/api/v1/sessions/{sid}/receipts/private-receipt").status_code == 404
        forbidden = {**purchase, "actor_id": "other-buyer"}
        assert first.post(f"/api/v1/sessions/{sid}/actions", json=forbidden).status_code == 422
        assert first.post(f"/api/v1/sessions/{sid}/run").status_code == 403
        other_session = create_market(service)
        assert first.get(f"/api/v1/sessions/{other_session['session_id']}/observation").status_code == 403
    seller = service.observe(sid, tokens["seller"])
    other_seller = service.observe(sid, tokens["other-seller"])
    assert all(i["seller_id"] == "seller" for i in seller["state"]["own"]["inventory"])
    assert all(i["seller_id"] == "other-seller" for i in other_seller["state"]["own"]["inventory"])
    assert all(m["author_id"] == "other-seller" for m in other_seller["state"]["inbox"]["messages"])
    transcript = canonical(store["service"].recover(sid).journal.records)
    assert all(value not in transcript for value in tokens.values())


def test_second_request_for_same_opportunity_cannot_replace_batch(store):
    service = store["service"]
    created = create_market(service)
    token, sid = created["actor_tokens"]["seller"], created["session_id"]
    obs = service.observe(sid, token)
    first = request_for(obs, (Procure("cups", 1, 100),), "first")
    service.submit(sid, token, first)
    second = request_for(obs, (Procure("cups", 2, 100),), "second")
    assert service.submit(sid, token, second)["code"] == "OPPORTUNITY_ALREADY_SUBMITTED"
    service.run_ready(sid)
    assert service.recover(sid).economic_state().procurements[0].quantity == 1


def test_partial_wave_is_durable_but_never_executes_early(store):
    service = store["service"]
    created = create_market(service, two_sellers=True)
    sid, tokens = created["session_id"], created["actor_tokens"]
    req = request_for(service.observe(sid, tokens["seller"]), (Procure("cups", 1, 100),))
    service.submit(sid, tokens["seller"], req)
    assert service.run_ready(sid) == {"progressed": False}
    resumed = MarketService(store["sessions"])
    assert resumed.recover(sid).economic_state().procurements == ()
    assert resumed.receipt(sid, tokens["seller"], req["request_id"])["status"] == "pending"
    other = request_for(resumed.observe(sid, tokens["other-seller"]), (Procure("cups", 1, 100),))
    resumed.submit(sid, tokens["other-seller"], other)
    resumed.run_ready(sid)
    assert len(resumed.recover(sid).economic_state().procurements) == 2


@pytest.mark.parametrize("point", ["before_commit", "after_commit"])
def test_submit_commit_unknown_retry_uses_same_durable_request(store, point):
    created = create_market(store["service"])
    sid, token = created["session_id"], created["actor_tokens"]["seller"]
    request = request_for(store["service"].observe(sid, token), (Procure("cups", 1, 100),), "unknown")

    def fault(operation, current):
        if operation == "submit" and current == point:
            raise ConnectionError("Lost acknowledgement")

    broken = MarketService(store["sessions"], fault_hook=fault)
    with pytest.raises(CommitUnknown):
        broken.submit(sid, token, request)
    fresh = MarketService(store["sessions"])
    receipt = fresh.submit(sid, token, request)
    assert receipt["replayed"] == (point == "after_commit")
    fresh.run_ready(sid)
    assert len(fresh.recover(sid).economic_state().procurements) == 1


@pytest.mark.parametrize("point", ["before_commit", "after_commit"])
def test_boundary_commit_unknown_never_reexecutes_committed_purchase(store, point):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    requests = queue_purchases(service, created)
    sid = created["session_id"]

    def fault(operation, current):
        if operation == "boundary" and current == point:
            raise ConnectionError("Commit acknowledgement lost")

    broken = MarketService(store["sessions"], fault_hook=fault)
    with pytest.raises(CommitUnknown):
        broken.run_ready(sid)
    fresh = MarketService(store["sessions"])
    observed = fresh.observe(sid, created["actor_tokens"]["buyer"])
    assert observed["published_version"] == (2 if point == "before_commit" else 3)
    fresh.run_ready(sid)
    state = fresh.recover(sid).economic_state()
    assert len(state.orders) == 1
    duplicate = fresh.submit(sid, created["actor_tokens"]["buyer"], requests["buyer"])
    assert duplicate["replayed"] and duplicate["status"] != "pending"
    notices = fresh.notifications(sid, created["actor_tokens"]["buyer"], 2)["notices"]
    assert notices[0] == {"session_id": sid, "published_version": 3, "kind": "observation_invalidated"}


def test_fencing_rejects_old_candidate_even_if_it_computed_first(store):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    queue_purchases(service, created)
    sid = created["session_id"]
    first = service.compute(service.claim(sid))
    newer_service = MarketService(store["sessions"])
    second = newer_service.compute(newer_service.claim(sid))
    assert second.claim.fence > first.claim.fence
    with pytest.raises(ServiceError, match="WRITER_FENCED"):
        service.commit_candidate(first)
    newer_service.commit_candidate(second)
    with pytest.raises(ServiceError, match="WRITER_FENCED"):
        newer_service.commit_candidate(second)
    assert len(service.recover(sid).economic_state().orders) == 1


def test_readers_see_only_complete_committed_publication_during_commit(store):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    queue_purchases(service, created)
    sid, token = created["session_id"], created["actor_tokens"]["buyer"]
    entered, release = Event(), Event()

    def fault(operation, point):
        if operation == "boundary" and point == "before_commit":
            entered.set()
            assert release.wait(10)

    writer = MarketService(store["sessions"], fault_hook=fault)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(writer.run_ready, sid)
        assert entered.wait(10)
        try:
            observation = service.observe(sid, token)
            assert observation["published_version"] == observation["runtime"]["published_version"] == 2
            assert observation["state"]["own"]["orders"] == []
        finally:
            release.set()
        future.result(timeout=10)
    observation = service.observe(sid, token)
    assert observation["published_version"] == observation["runtime"]["published_version"] == 3
    assert service.recover(sid).published_version == 3


def test_transcript_corruption_and_wrong_code_fail_closed(store):
    service = store["service"]
    created = create_market(service)
    sid = created["session_id"]
    with store["sessions"].begin() as db:
        row = db.get(JournalEntry, (sid, 1))
        row.payload = {**row.payload, "version": 99}
    with pytest.raises(ServiceError, match="TRANSCRIPT_INTEGRITY_ERROR"):
        service.recover(sid)
    second = create_market(service)
    with store["sessions"].begin() as db:
        db.get(MarketSession, second["session_id"]).source_digest = "0" * 64
    with pytest.raises(ServiceError, match="RECOVERY_CODE_MISMATCH"):
        service.claim(second["session_id"])


def test_batch_failure_skipped_and_invalid_batch_survive_recovery(store):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    requests = submit_wave(service, created, lambda actor, obs: (
        (SendPrivate("other-buyer", "Forbidden"), Purchase("seller/cup", 1, 300, 1)) if actor == "buyer" else (Wait(), Wait())))
    service.run_ready(created["session_id"])
    for actor in ("buyer", "other-buyer"):
        receipt = service.receipt(created["session_id"], created["actor_tokens"][actor], requests[actor]["request_id"])
        assert receipt["status"] == "failed"
        assert [o["status"] for o in receipt["outcomes"]] == (["business_failed", "skipped"] if actor == "buyer" else ["invalid_batch"])
    assert service.recover(created["session_id"]).economic_state().orders == ()


@pytest.mark.parametrize("point", ["before_commit", "after_commit"])
def test_real_process_exit_before_or_after_commit_recovers_without_double_sale(store, point):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    requests = queue_purchases(service, created)
    env = os.environ.copy()
    env["SALESBENCH_DATABASE_URL"] = store["url"]
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("crash_worker.py")), created["session_id"], point],
                            env=env, capture_output=True, text=True, timeout=30,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert result.returncode == 72, result.stderr
    restarted = MarketService(store["sessions"])
    state = restarted.recover(created["session_id"]).economic_state()
    assert len(state.orders) == (0 if point == "before_commit" else 1)
    restarted.run_ready(created["session_id"])
    assert len(restarted.recover(created["session_id"]).economic_state().orders) == 1
    response = restarted.submit(created["session_id"], created["actor_tokens"]["buyer"], requests["buyer"])
    assert response["replayed"]


@pytest.mark.parametrize("point", ["before_commit", "after_commit"])
def test_round_close_commit_unknown_advances_exactly_once(store, point):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    queue_purchases(service, created)
    sid = created["session_id"]
    service.run_ready(sid)

    def fault(operation, current):
        if operation == "boundary" and current == point:
            raise ConnectionError("Lost close acknowledgement")

    with pytest.raises(CommitUnknown):
        MarketService(store["sessions"], fault_hook=fault).run_ready(sid)
    fresh = MarketService(store["sessions"])
    fresh.run_ready(sid)
    recovered = fresh.recover(sid)
    assert recovered.economic_state().time.step == 1
    assert recovered.published_version == 4
    assert len([e for e in recovered.economic_state().events if e.kind == "time_advanced"]) == 1


def test_engine_fault_retains_auditable_prefix_but_never_publishes_partial_wave(store):
    service = store["service"]
    created = create_market(service, two_sellers=True)
    sid = created["session_id"]
    submit_wave(service, created, lambda actor, obs: (Procure("cups", 1, 100),))
    service.run_ready(sid)
    requests = submit_wave(service, created, lambda actor, obs: (CreateListing(actor + "/cup", "cup", 300, "Cup"),))
    execute = Engine.execute
    count = 0

    def fault(engine, actor, action):
        nonlocal count
        if isinstance(action, CreateListing):
            count += 1
            if count == 2:
                raise RuntimeError("Injected Engine implementation failure")
        return execute(engine, actor, action)

    with patch.object(Engine, "execute", fault):
        result = service.run_ready(sid)
    assert result["runtime"]["status"] == "failed"
    assert result["runtime"]["published_version"] == 1
    recovered = service.recover(sid)
    assert len(recovered.economic_state().listings) == 1
    assert recovered.observe("buyer").public.listings == ()
    for actor, request in requests.items():
        receipt = service.receipt(sid, created["actor_tokens"][actor], request["request_id"])
        assert receipt["status"] == "aborted" and receipt["outcomes"] == []
    assert service.observe(sid, created["actor_tokens"]["buyer"])["state"]["public"]["listings"] == []
    assert service.run_ready(sid) == {"progressed": False}


def test_application_boundary_rejects_bad_envelopes_like_http(store):
    service = store["service"]
    created = create_market(service)
    sid, token = created["session_id"], created["actor_tokens"]["seller"]
    request = request_for(service.observe(sid, token), (Wait(),))
    bad_requests = [{**request, "observation_version": False}, {**request, "actor_id": "buyer"},
                    {**request, "actions": [{"type": "send_public", "text": "bad\x00text", "seller_id": "seller"}]},
                    {**request, "actions": [{"type": "purchase", "quantity": float("nan")}]}]
    for invalid in bad_requests:
        with pytest.raises(ServiceError, match="INVALID_REQUEST_ENVELOPE"):
            service.submit(sid, token, invalid)
    with store["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(BatchReceipt)) == 0


def test_creation_retry_and_binding_rotation_do_not_create_or_expose_extra_market(store):
    from helpers import setup_market
    from salesbench_engine.runner.codec import data

    service = store["service"]
    created = create_market(service)
    sid = created["session_id"]
    repeated = service.create(sid, data(setup_market()), {"max_rounds": 1, "ticks_per_round": 1})
    assert repeated["replayed"] and repeated["actor_tokens"] is None
    with pytest.raises(ServiceError, match="SESSION_ID_CONFLICT"):
        service.create(sid, data(setup_market()), {"max_rounds": 2, "ticks_per_round": 1})
    old = created["actor_tokens"]["buyer"]
    new = service.rotate_binding(sid, "buyer")["actor_token"]
    with pytest.raises(ServiceError, match="INVALID_ACTOR_BINDING"):
        service.observe(sid, old)
    assert service.observe(sid, new)["actor_id"] == "buyer"
    assert service.observe(sid, created["actor_tokens"]["seller"])["actor_id"] == "seller"


def test_unrecordable_runner_bug_keeps_last_boundary_and_does_not_stop_other_sessions(store):
    from salesbench_engine.runner.scheduler import Runner

    service = store["service"]
    created = create_market(service)
    sid = created["session_id"]
    submit_wave(service, created, lambda actor, obs: (Wait(),))
    original = Runner._wave
    first = True

    async def bug(runner, wave):
        nonlocal first
        if first:
            first = False
            raise RuntimeError("implementation fault")
        await original(runner, wave)

    with patch.object(Runner, "_wave", bug):
        with pytest.raises(ServiceError, match="RECOVERY_TRACE_MISMATCH"):
            service.run_ready(sid)
    assert service.recover(sid).published_version == 0
    second = create_market(service)["session_id"]
    calls = []

    def execute(session_id):
        calls.append(session_id)
        if session_id == sid:
            raise RuntimeError("private payload must not be logged")

    with patch.object(service, "run_ready", side_effect=execute):
        service.work_pending()
    assert set(calls) == {sid, second}
    service.run_ready(sid)
    assert service.recover(sid).published_version == 1
