"""Local administrative commands. Output never includes database/bearer secrets."""

import argparse
from pathlib import Path
import json
import os
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from salesbench_engine.actions import CreateListing, Procure, Purchase, SendPrivate, UpdateListing, Wait
from salesbench_engine.runner.codec import action_data, data, digest
from salesbench_engine.runner.demo import demo_setup

from .persistence import database
from .service import MarketService


def initialize_local_database(url):
    parsed = make_url(url)
    if parsed.host != "127.0.0.1" or parsed.database != "salesbench_platform":
        raise ValueError("Local bootstrap only creates salesbench_platform on 127.0.0.1")
    target = parsed.database
    admin_url = parsed.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,)).fetchone()
        if exists:
            print(json.dumps({"database": target, "status": "already_exists"}))
            return
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
    print(json.dumps({"database": target, "status": "created"}))


def demo_batch(observation):
    opportunity = observation["opportunity"]
    actor = observation["actor_id"]
    context = opportunity["context"]
    if context["wave"] == "ROUND_PROCUREMENT":
        return (Procure("cups", 1 if actor == "seller-1" else 2, 100),)
    if context["wave"] == "SELLER_STRATEGY":
        if context["round"] == 1 and context["tick"] == 1:
            return (CreateListing(actor + "/cup", "cup", 300, "TEST cup"),)
        if context["tick"] == 2:
            return (UpdateListing(actor + "/cup", unit_price_cents=350, description="Updated TEST cup"),
                    SendPrivate("buyer-1", "Next Wave reply"))
        return (Wait(),)
    if context["tick"] == 1:
        listing = next(v["listing"] for v in observation["state"]["public"]["listings"] if v["listing"]["id"] == "seller-1/cup")
        return (SendPrivate("seller-1", "One cup please"),
                Purchase(listing["id"], 1, listing["unit_price_cents"], listing["offer_revision"]))
    return (Wait(),)


def demo(service):
    session_id = "demo-" + uuid4().hex
    created = service.create(session_id, data(demo_setup()), {})
    tokens = created["actor_tokens"]
    commits = []
    for _ in range(100):
        for actor, token in tokens.items():
            obs = service.observe(session_id, token)
            if obs["opportunity"] is None:
                continue
            request = {"request_id": "batch-" + obs["opportunity"]["opportunity_id"],
                       "opportunity_id": obs["opportunity"]["opportunity_id"],
                       "observation_version": obs["published_version"], "actions": [action_data(a) for a in demo_batch(obs)]}
            service.submit(session_id, token, request)
        progress = service.run_ready(session_id)
        if progress["progressed"]:
            commits.append(progress["runtime"]["published_version"])
        runtime = service.runtime(session_id, next(iter(tokens.values())))
        if runtime["status"] in ("completed", "failed"):
            break
    restored = service.recover(session_id)
    state = restored.economic_state()
    return {"session_id": session_id, "runtime": runtime, "committed_versions": commits,
            "orders": [{"buyer_id": o.buyer_id, "total_cents": o.total_cents, "offer_revision": o.offer_revision} for o in state.orders],
            "state_digest": digest(state), "recovery_verified": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=("init-db", "demo", "recover", "create-manual", "inspect", "metrics"))
    parser.add_argument("--session-id")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    url = os.environ["SALESBENCH_DATABASE_URL"]
    if args.task == "init-db":
        initialize_local_database(url)
        return
    engine, sessions = database(url)
    try:
        service = MarketService(sessions)
        if args.task == "create-manual":
            from .manual import create_manual
            result = create_manual(service, Path(__file__).resolve().parents[2] / ".local/manual")
        elif args.task == "metrics":
            if not args.session_id:
                parser.error("metrics requires --session-id")
            if args.format == "csv" and args.out_dir is None:
                parser.error("CSV export requires --out-dir (a new private local directory)")
            result = service.metrics(args.session_id)
            if args.out_dir is not None:
                from .metric_exports import export_metrics
                result = export_metrics(result, args.out_dir, args.format)
        elif args.task == "inspect":
            from .manual import inspect_market
            if not args.session_id:
                parser.error("inspect requires --session-id")
            result = inspect_market(service, args.session_id)
        elif args.task == "demo":
            result = demo(service)
        else:
            if not args.session_id:
                parser.error("recover requires --session-id")
            runner = service.recover(args.session_id)
            result = {"session_id": args.session_id, "phase": str(runner.phase), "published_version": runner.published_version,
                      "state_digest": digest(runner.economic_state()), "recovery_verified": True}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
