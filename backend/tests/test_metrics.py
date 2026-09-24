from collections import Counter, defaultdict
from copy import deepcopy
import csv
import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, select

from app.main import create_app
from app.metric_exports import export_metrics
from app.metrics import derive, seller_metrics
from app.persistence import LeaderboardSnapshot, MarketSession, MetricSnapshot
from app.service import CommitUnknown, MarketService, ServiceError
from salesbench_engine import Engine
from salesbench_engine.actions import Procure, Purchase, SendPrivate, SendPublic, UpdateListing, Wait
from salesbench_engine.runner.codec import data
from helpers import create_market, prepare_buyers, request_for, setup_market, submit_wave


def board(service, created, actor="buyer"):
    return service.observe(created["session_id"], created["actor_tokens"][actor])["leaderboard"]


def test_profit_tick_close_previous_rank_negative_and_pending_isolation(store):
    service = store["service"]
    created = create_market(service, two_sellers=True, ticks=2)
    sid = created["session_id"]
    initial = board(service, created)
    assert [(r["seller_id"], r["dev_profit_cents"], r["previous_rank"]) for r in initial["rows"]] == [
        ("other-seller", 0, None), ("seller", 0, None)]
    prepare_buyers(service, created)
    assert board(service, created) == initial  # Procurement/Seller publish no new ranking.
    host = service.metrics(sid)
    assert {s["dev_profit_cents"] for s in host["sellers"]} == {-100}
    assert {s["current_cash_cents"] for s in host["sellers"]} == {900}
    request = request_for(service.observe(sid, created["actor_tokens"]["buyer"]), (Purchase("seller/cup", 1, 300, 1),))
    service.submit(sid, created["actor_tokens"]["buyer"], request)
    assert board(service, created) == initial
    assert service.metrics(sid) == host  # Pending requests are not metric facts.
    other = service.observe(sid, created["actor_tokens"]["other-buyer"])
    service.submit(sid, created["actor_tokens"]["other-buyer"], request_for(other, (Wait(),)))
    service.run_ready(sid)
    ranked = board(service, created)
    assert ranked["source_publication_version"] == 3
    assert [(r["seller_id"], r["dev_profit_cents"], r["current_rank"], r["previous_rank"]) for r in ranked["rows"]] == [
        ("seller", 200, 1, 2), ("other-seller", -100, 2, 1)]
    assert board(service, created, "seller") == ranked == board(service, created, "other-seller")
    host = service.metrics(sid)
    seller = next(s for s in host["sellers"] if s["seller_id"] == "seller")
    assert seller["cumulative_sales_revenue_cents"] == 300 and seller["cumulative_procurement_spend_cents"] == 100
    assert seller["dev_profit_cents"] == seller["current_cash_cents"] - seller["initial_cash_cents"] == 200
    assert seller["units_procured"] == seller["units_sold"] == seller["orders_count"] == 1
    assert seller["current_inventory_units"] == 0
    submit_wave(service, created, lambda actor, obs: (UpdateListing("seller/cup", unit_price_cents=400),
                UpdateListing("seller/cup", unit_price_cents=400), UpdateListing("seller/cup", description="new")) if actor == "seller" else (Wait(),))
    service.run_ready(sid)
    assert board(service, created) == ranked
    host = service.metrics(sid)
    assert next(s for s in host["sellers"] if s["seller_id"] == "seller")["price_change_count"] == 1
    assert [p["unit_price_cents"] for p in host["price_trajectory"] if p["seller_id"] == "seller"] == [300, 400]
    assert service.leaderboard(sid, publication_version=1)["leaderboard"] == initial
    assert service.leaderboard(sid, publication_version=3)["leaderboard"] == ranked
    assert [m["leaderboard_source_version"] for m in host["publication_leaderboards"]] == [0, 0, 0, 3, 3]


def test_profit_cash_delta_invariant_records_both_values_without_selecting_one():
    setup = data(setup_market())
    facts = {"accounts": deepcopy(setup["accounts"]), "orders": [], "procurements": [], "inventory": [], "listings": []}
    next(a for a in facts["accounts"] if a["actor_id"] == "seller")["balance_cents"] -= 1
    rows, errors = seller_metrics(setup, facts, defaultdict(Counter))
    assert rows[0]["dev_profit_cents"] is None
    assert errors == [{"code": "PROFIT_CASH_DELTA_MISMATCH", "seller_id": "seller",
                       "revenue_minus_procurement_cents": 0, "cash_delta_cents": -1}]


def test_consistency_error_is_durable_and_participants_fail_closed(store):
    service = store["service"]
    created = create_market(service)
    sid = created["session_id"]
    with store["sessions"].begin() as db:
        db.execute(delete(MetricSnapshot).where(MetricSnapshot.session_id == sid))
        db.execute(delete(LeaderboardSnapshot).where(LeaderboardSnapshot.session_id == sid))
    original = seller_metrics

    def inconsistent(setup, facts, counters):
        altered = deepcopy(facts)
        next(a for a in altered["accounts"] if a["actor_id"] == "seller")["balance_cents"] -= 1
        return original(setup, altered, counters)

    with patch("app.metrics.seller_metrics", inconsistent):
        report = service.metrics(sid)
    assert report["consistency_errors"][0]["code"] == "PROFIT_CASH_DELTA_MISMATCH"
    assert report["leaderboard"] is None
    with pytest.raises(ServiceError, match="METRICS_INCONSISTENT"):
        board(service, created)


def test_messages_failed_purchase_skipped_and_price_trajectory_are_trace_facts(store):
    service = store["service"]
    created = create_market(service)
    sid = created["session_id"]
    prepare_buyers(service, created)
    submit_wave(service, created, lambda actor, obs: (SendPrivate("other-buyer", "not a seller"), Purchase("seller/cup", 1, 300, 1))
                if actor == "buyer" else (SendPublic("seller", "public test"), SendPrivate("seller", "private body must not export"), Purchase("seller/cup", 1, 999, 1)))
    service.run_ready(sid)
    report = service.metrics(sid)
    assert report["summary"]["failed_actions"] == 2 and report["summary"]["skipped_actions"] == 1
    assert report["summary"]["public_message_count"] == report["summary"]["private_message_count"] == 1
    assert [b["failed_purchase_count"] for b in report["buyers"]] == [0, 1]
    assert "private body must not export" not in json.dumps(report)
    assert report["summary"]["technical_failure_count"] == 0


def test_round_close_refresh_is_a_separate_policy_without_protocol_changes(store):
    service = store["service"]
    created = service.create("round-policy", data(setup_market()), {"max_rounds": 1, "ticks_per_round": 1}, {"refresh": "round_close"})
    initial = board(service, created)
    prepare_buyers(service, created)
    submit_wave(service, created, lambda actor, obs: (Wait(),))
    service.run_ready(created["session_id"])
    assert board(service, created) == initial
    service.run_ready(created["session_id"])
    latest = board(service, created)
    assert latest["source_publication_version"] == 4 and latest["rows"][0]["dev_profit_cents"] == -100
    assert service.recover(created["session_id"]).economic_state().time.step == 1


@pytest.mark.parametrize("point", ["before_commit", "after_commit"])
def test_metric_commit_unknown_and_missing_post_economic_commit_repair(store, point):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    submit_wave(service, created, lambda actor, obs: (Purchase("seller/cup", 1, 300, 1),))
    sid = created["session_id"]
    def fault(operation, current):
        if operation == "metrics" and current == point:
            raise OSError("simulated lost metric commit acknowledgement")
    with pytest.raises(CommitUnknown):
        MarketService(store["sessions"], fault_hook=fault).run_ready(sid)
    fresh = MarketService(store["sessions"])
    recovered = board(fresh, created)
    assert recovered["source_publication_version"] == 3
    assert recovered["rows"][0]["dev_profit_cents"] == 200
    assert len(fresh.recover(sid).economic_state().orders) == 1
    assert fresh.metrics(sid) == service.metrics(sid)


def test_replay_and_historical_metrics_match_all_materialized_snapshots(store):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    submit_wave(service, created, lambda actor, obs: (Wait(),))
    service.run_ready(created["session_id"]); service.run_ready(created["session_id"])
    sid = created["session_id"]
    with store["sessions"]() as db:
        row = db.get(MarketSession, sid)
        records = service._load_records(db, row)
        recovered = service._restore_verified(records, (row.published_version, row.state_digest))
        assert recovered.economic_state().time.step == 1
        expected, boards = derive(sid, records, row.metrics_policy, row.runtime)
        assert derive(sid, deepcopy(records), row.metrics_policy, row.runtime) == (expected, boards)
        actual = list(db.scalars(select(MetricSnapshot).where(MetricSnapshot.session_id == sid).order_by(MetricSnapshot.transcript_count)))
        assert [r.payload for r in actual] == [r["payload"] for r in expected]
        assert [r.payload for r in db.scalars(select(LeaderboardSnapshot).where(LeaderboardSnapshot.session_id == sid).order_by(LeaderboardSnapshot.source_publication_version))] == boards
    assert service.metrics(sid)["summary"]["status"] == "completed"


def test_admin_only_metrics_and_public_snapshot_allowlist(store):
    service = store["service"]
    created = create_market(service, two_sellers=True)
    prepare_buyers(service, created)
    sid, actor = created["session_id"], created["actor_tokens"]["buyer"]
    with TestClient(create_app(market_service=service, admin_token="test-admin", auto_run=False)) as client:
        for endpoint in ("metrics", "leaderboard"):
            path = f"/api/v1/admin/sessions/{sid}/{endpoint}"
            assert client.get(path).status_code == 401
            assert client.get(path, headers={"Authorization": "Bearer " + actor}).status_code == 403
            assert client.get(path, headers={"Authorization": "Bearer test-admin"}).status_code == 200
        assert "Trusted researcher" in client.get("/openapi.json").text
        response = client.get(f"/api/v1/sessions/{sid}/observation", headers={"Authorization": "Bearer " + actor}).json()
    assert set(response["leaderboard"]["rows"][0]) == {"seller_id", "display_name", "current_rank", "previous_rank", "dev_profit_cents"}
    assert "current_cash_cents" not in json.dumps(response)
    assert "cumulative_procurement_spend_cents" not in json.dumps(response)
    assert "calculator_digest" not in json.dumps(response)


def test_json_csv_export_preserves_negative_money_and_omits_private_payloads(store, tmp_path):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    report = service.metrics(created["session_id"])
    export_metrics(report, tmp_path / "json", "json")
    assert json.loads((tmp_path / "json/metrics.json").read_text(encoding="utf-8")) == report
    export_metrics(report, tmp_path / "csv", "csv")
    with (tmp_path / "csv/sellers.csv").open(encoding="utf-8-sig", newline="") as file:
        assert list(csv.DictReader(file))[0]["dev_profit_cents"] == "-100"
    content = "".join(p.read_text(encoding="utf-8-sig") for p in tmp_path.rglob("*.*"))
    assert all(token not in content for token in created["actor_tokens"].values())
    assert "raw_output" not in content and "private body" not in content
    with pytest.raises(FileExistsError):
        export_metrics(report, tmp_path / "csv", "csv")


def test_old_or_unknown_policy_never_silently_invents_historical_ranking(store):
    service = store["service"]
    created = create_market(service)
    sid = created["session_id"]
    with store["sessions"].begin() as db:
        row = db.get(MarketSession, sid)
        row.metrics_policy = {**row.metrics_policy, "policy_id": "unknown_future_policy"}
    with pytest.raises(ServiceError, match="METRICS_POLICY_MISMATCH"):
        service.metrics(sid)
    with store["sessions"].begin() as db:
        db.get(MarketSession, sid).metrics_policy = None
    assert board(service, created) is None
    with pytest.raises(ServiceError, match="METRICS_NOT_ENABLED"):
        service.metrics(sid)
    assert service.recover(sid).published_version == 0


def test_technical_failure_counts_committed_audit_prefix_without_public_ranking_change(store):
    service = store["service"]
    created = create_market(service, two_sellers=True)
    initial = board(service, created)
    submit_wave(service, created, lambda actor, obs: (Procure("cups", 1, 100),))
    original = Engine.execute
    attempts = 0
    def fail_second(engine, actor, action):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise RuntimeError("test action fault")
        return original(engine, actor, action)
    with patch.object(Engine, "execute", fail_second):
        service.run_ready(created["session_id"])
    report = service.metrics(created["session_id"])
    assert report["economic_visibility"] == "committed_failure_prefix"
    assert report["summary"]["technical_failure_count"] == 1
    assert report["summary"]["succeeded_actions"] == 1
    assert report["summary"]["failed_actions"] == 0  # Technical failure isn't business rejection.
    assert board(service, created) == initial


def test_cached_metrics_cannot_hide_corrupt_economic_metadata(store):
    service = store["service"]
    created = create_market(service)
    with store["sessions"].begin() as db:
        db.get(MarketSession, created["session_id"]).state_digest = "0" * 64
    with pytest.raises(ServiceError, match="METRICS_SOURCE_MISMATCH"):
        service.metrics(created["session_id"])
    with pytest.raises(ServiceError, match="RECOVERY_STATE_MISMATCH"):
        service.recover(created["session_id"])


def test_observe_repairs_commit_between_ensure_and_projection_read(store):
    service = store["service"]
    created = create_market(service)
    prepare_buyers(service, created)
    sid = created["session_id"]
    submit_wave(service, created, lambda actor, obs: (Purchase("seller/cup", 1, 300, 1),))
    candidate = service.compute(service.claim(sid))
    original = service._observe_committed
    raced = False
    def commit_before_read(session_id, token):
        nonlocal raced
        if not raced:
            raced = True
            # Economic COMMIT succeeded; writer exits before materializing metrics.
            with patch.object(service, "_ensure_metrics"):
                service.commit_candidate(candidate)
        return original(session_id, token)
    with patch.object(service, "_observe_committed", commit_before_read):
        observed = service.observe(sid, created["actor_tokens"]["buyer"])
    assert observed["published_version"] == observed["leaderboard"]["source_publication_version"] == 3
    assert observed["leaderboard"]["rows"][0]["dev_profit_cents"] == 200
    assert len(service.recover(sid).economic_state().orders) == 1
