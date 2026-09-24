"""Local developer tools only. No participant endpoint or alternate economic rules."""

from collections import Counter
from pathlib import Path
import json
from uuid import uuid4

from sqlalchemy import func, select

from salesbench_engine.models import Account, Buyer, Experiment, MarketSetup, Product, Seller, Supplier, SupplierOffer
from salesbench_engine.runner.codec import data

from .persistence import ActionReceipt, ActorBinding, BatchReceipt, JournalEntry, Publication
from .service import ServiceError


def create_manual(service, directory: Path):
    sid = "manual-" + uuid4().hex
    setup = MarketSetup(Experiment("manual-market", 7), (Supplier("supplier", "实验供应商"),),
                        (Seller("seller-a", "Seller A"), Seller("seller-b", "Seller B")),
                        (Buyer("buyer-1", "Buyer 1"), Buyer("buyer-2", "Buyer 2")),
                        (Product("cup", "陶瓷杯"), Product("bag", "帆布袋")),
                        (SupplierOffer("cups", "supplier", "cup", 100, 40), SupplierOffer("bags", "supplier", "bag", 200, 40)),
                        (Account("supplier", 0), Account("seller-a", 5000), Account("seller-b", 5000),
                         Account("buyer-1", 2000), Account("buyer-2", 2000)))
    # Create a new directory first. Never overwrite credentials or reuse a session ID.
    target = directory / sid
    target.mkdir(parents=True, exist_ok=False)
    created = service.create(sid, data(setup), {"max_rounds": 2, "ticks_per_round": 3})
    for actor, token in created["actor_tokens"].items():
        with (target / f"{actor}.json").open("x", encoding="utf-8") as file:
            json.dump({"session_id": sid, "actor_token": token}, file)
    return {"session_id": sid, "binding_directory": str(target.resolve()),
            "actors": list(created["actor_tokens"]), "published_version": 0,
            "note": "Import each private JSON file in its actor browser tab; tokens are not printed."}


def inspect_market(service, sid):
    """Host-only, read-only committed summary. Omit tokens, hashes and message text."""
    with service.sessions() as db:
        row = service._locked(db, sid)
        if row.source_digest != service.code_digest:
            raise ServiceError("RECOVERY_CODE_MISMATCH", 503)
        records = service._load_records(db, row)
        expected = (row.published_version, row.state_digest)
        bindings = db.execute(select(ActorBinding.actor_id, ActorBinding.role).where(ActorBinding.session_id == sid)).all()
        receipts = list(db.scalars(select(BatchReceipt).where(BatchReceipt.session_id == sid).order_by(BatchReceipt.created_at)))
        pub = db.get(Publication, (sid, row.published_version))
        # Published journal projections suffice for listings/orders. No SQL economics.
        latest = next(r for r in reversed(records) if r["kind"] == "published")
        report = {"session_id": sid, "runtime": row.runtime, "current_publication": pub.version,
                "actor_bindings": [{"actor_id": a, "role": role} for a, role in bindings],
                "receipts": [{"actor_id": r.actor_id, "request_id": r.request_id, "status": r.status,
                              "published_version": r.receipt["published_version"], "outcome_codes": [
                                  o.get("result", {}).get("code") if o.get("result") else o.get("reason")
                                  for o in r.receipt["outcomes"]]} for r in receipts],
                "listings": pub.public["listings"],
                "resolution": [{"context": r["context"], "purpose": r["purpose"], "order": r["order"]}
                               for r in records if r["kind"] == "resolution"],
                "journal": {"count": len(records), "kinds": dict(Counter(r["kind"] for r in records)),
                            "source_digest": row.source_digest, "state_digest": row.state_digest},
                "publication_context": latest["context"]}
        report["table_counts"] = {model.__tablename__: db.scalar(select(func.count()).select_from(model).where(model.session_id == sid))
                                  for model in (ActorBinding, BatchReceipt, ActionReceipt, Publication, JournalEntry)}
    runner = service._restore_verified(records, expected)
    state = runner.economic_state()
    report.update(orders=data(state.orders), accounts=data(state.accounts), inventory=data(state.inventory),
                  owned_listings=data(state.listings))
    return report
