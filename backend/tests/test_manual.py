import json
import pytest

from app.manual import create_manual, inspect_market
from app.persistence import MarketSession
from app.service import ServiceError
from salesbench_engine.actions import Wait
from salesbench_engine.runner.codec import canonical
from helpers import create_market, prepare_buyers, queue_purchases, submit_wave


def test_own_receipts_support_rebinding_without_private_cross_actor_data(store):
    service = store["service"]
    created = create_market(service)
    requests = submit_wave(service, created, lambda actor, observation: (Wait(),))
    sid, tokens = created["session_id"], created["actor_tokens"]
    own = service.receipts(sid, tokens["seller"])["receipts"]
    assert len(own) == 1 and own[0]["status"] == "pending"
    assert own[0]["request_id"] == requests["seller"]["request_id"]
    assert service.receipts(sid, tokens["buyer"])["receipts"] == []
    new = service.rotate_binding(sid, "seller")["actor_token"]
    assert service.receipts(sid, new) == {"receipts": own}
    service.run_ready(sid)
    assert service.receipts(sid, new)["receipts"][0]["status"] == "succeeded"


def test_manual_creation_private_files_and_read_only_inspection(store, tmp_path):
    service = store["service"]
    created = create_manual(service, tmp_path)
    paths = list(tmp_path.rglob("*.json"))
    assert len(paths) == 4
    bindings = [json.loads(path.read_text()) for path in paths]
    assert all(b["session_id"] == created["session_id"] for b in bindings)
    assert all(b["actor_token"] not in canonical(created) for b in bindings)
    report = inspect_market(service, created["session_id"])
    assert report["current_publication"] == 0
    assert len(report["actor_bindings"]) == 4
    assert report["orders"] == [] and report["receipts"] == []
    assert all(b["actor_token"] not in canonical(report) for b in bindings)
    market = create_market(service)
    prepare_buyers(service, market)
    queue_purchases(service, market)
    service.run_ready(market["session_id"])
    first = inspect_market(service, market["session_id"])
    second = inspect_market(service, market["session_id"])
    assert first == second
    assert len(first["orders"]) == 1 and first["current_publication"] == 3
    assert len(first["resolution"]) > 0 and first["journal"]["count"] > 2


@pytest.mark.parametrize("field,code", [("source_digest", "RECOVERY_CODE_MISMATCH"),
                                       ("state_digest", "RECOVERY_STATE_MISMATCH")])
def test_inspect_and_recover_reject_inconsistent_committed_metadata(store, field, code):
    service = store["service"]
    sid = create_market(service)["session_id"]
    # Corruption is injected only into this test's isolated PostgreSQL schema.
    with store["sessions"].begin() as db:
        setattr(db.get(MarketSession, sid), field, "0" * 64)
    for audit in (service.recover, lambda value: inspect_market(service, value)):
        with pytest.raises(ServiceError) as error:
            audit(sid)
        assert error.value.code == code
