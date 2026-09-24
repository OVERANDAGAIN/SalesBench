"""Versioned, deterministic statistics over VERIFIED committed transcript facts.

No execution, pending intents, SQL, model calls, or participant-private exports.
The store verifies economic recovery before calling this module. Fact deltas are
Engine-recorded post-action tables, not a second implementation of transfers.
"""

from collections import Counter, defaultdict
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from salesbench_engine.runner.codec import digest

SCHEMA = "sb-metrics-v1"
POLICY = "dev_cash_profit_v1"


def new_policy(options=None):
    options = options or {}
    if set(options) - {"refresh"} or options.get("refresh", "tick_close") not in ("tick_close", "round_close"):
        raise ValueError("Unsupported metrics refresh policy")
    return {"policy_id": POLICY, "policy_version": 1, "metric_schema_version": SCHEMA,
            "refresh": options.get("refresh", "tick_close"),
            "calculator_digest": sha256(Path(__file__).read_text(encoding="utf-8").encode("utf-8")).hexdigest()}


def validate_policy(policy):
    if policy != new_policy({"refresh": policy.get("refresh")}):
        raise ValueError("Metrics code/policy mismatch; use the session's recorded version")


def seller_metrics(setup, facts, counters):
    initial = {a["actor_id"]: a["balance_cents"] for a in setup["accounts"]}
    cash = {a["actor_id"]: a["balance_cents"] for a in facts["accounts"]}
    rows, errors = [], []
    for seller in sorted(setup["sellers"], key=lambda a: a["id"]):
        actor = seller["id"]
        orders = [o for o in facts["orders"] if o["seller_id"] == actor]
        procurements = [p for p in facts["procurements"] if p["seller_id"] == actor]
        revenue = sum(o["total_cents"] for o in orders)
        spend = sum(p["total_cents"] for p in procurements)
        profit = revenue - spend
        if profit != cash[actor] - initial[actor]:
            errors.append({"code": "PROFIT_CASH_DELTA_MISMATCH", "seller_id": actor,
                           "revenue_minus_procurement_cents": profit, "cash_delta_cents": cash[actor] - initial[actor]})
            profit = None  # Do not silently select either conflicting value.
        rows.append({"seller_id": actor, "display_name": seller["name"], "initial_cash_cents": initial[actor],
                     "current_cash_cents": cash[actor], "cumulative_sales_revenue_cents": revenue,
                     "cumulative_procurement_spend_cents": spend, "dev_profit_cents": profit,
                     "orders_count": len(orders), "units_sold": sum(o["quantity"] for o in orders),
                     "units_procured": sum(p["quantity"] for p in procurements),
                     "current_inventory_units": sum(i["quantity"] for i in facts["inventory"] if i["seller_id"] == actor),
                     "active_listing_count": sum(v["active"] for v in facts["listings"] if v["seller_id"] == actor),
                     **{key: counters[actor][key] for key in ("price_change_count", "public_messages_sent", "private_messages_sent",
                                                             "successful_actions", "failed_actions", "skipped_actions")}})
    return rows, errors


def leaderboard(sid, publication, policy, sellers, previous):
    previous_ranks = {r["seller_id"]: r["current_rank"] for r in previous["rows"]} if previous else {}
    context = publication["context"] or {"round": 0, "tick": 0}
    rows = [{"seller_id": s["seller_id"], "display_name": s["display_name"], "current_rank": index + 1,
             "previous_rank": previous_ranks.get(s["seller_id"]), "dev_profit_cents": s["dev_profit_cents"]}
            for index, s in enumerate(sorted(sellers, key=lambda s: (-s["dev_profit_cents"], s["seller_id"])))]
    body = {"session_id": sid, "source_publication_version": publication["version"],
            "round_index": context["round"], "tick_index": context["tick"],
            "policy_id": policy["policy_id"], "policy_version": policy["policy_version"],
            "metric_schema_version": SCHEMA, "refresh_policy": policy["refresh"],
            "generated_from_committed_state": True, "rows": rows}
    return {"leaderboard_snapshot_id": "lb-" + digest(body), **body}


def derive(sid, records, policy, runtime):
    """Reproducible metric boundaries and public snapshots from a committed prefix.

    Caller must verify the entire prefix via restore_committed and state digest.
    We only copy recorded fact tables, never execute/guess failed economic effects.
    """
    validate_policy(policy)
    setup = records[0]["setup"]
    facts = {"accounts": deepcopy(setup["accounts"]), "orders": [], "procurements": [], "inventory": [], "listings": []}
    counters = defaultdict(Counter)
    actions, snapshots, boards, price_history, ticks = {}, [], [], [], []
    technical_failures = invalid_batches = 0
    last_publication = None
    previous_tick_orders = previous_tick_gmv = 0

    def report(publication, status):
        sellers, errors = seller_metrics(setup, facts, counters)
        initial = {a["actor_id"]: a["balance_cents"] for a in setup["accounts"]}
        cash = {a["actor_id"]: a["balance_cents"] for a in facts["accounts"]}
        buyers = []
        for buyer in sorted(setup["buyers"], key=lambda a: a["id"]):
            actor = buyer["id"]
            orders = [o for o in facts["orders"] if o["buyer_id"] == actor]
            buyers.append({"buyer_id": actor, "display_name": buyer["name"], "initial_balance_cents": initial[actor],
                           "current_balance_cents": cash[actor], "cumulative_spend_cents": sum(o["total_cents"] for o in orders),
                           "orders_count": len(orders), "units_bought": sum(o["quantity"] for o in orders),
                           **{key: counters[actor][key] for key in ("public_messages_sent", "private_messages_sent", "failed_purchase_count")}})
        context = publication["context"] or {"round": 1, "tick": 0}
        current_round, current_tick = context["round"], context["tick"]
        config = records[0]["market_config"]
        if publication["boundary"] == "round_closed" and current_round < config["max_rounds"]:
            current_round, current_tick = current_round + 1, 0
        elif publication["boundary"] == "wave_completed":
            if context["wave"] == "ROUND_PROCUREMENT":
                current_tick = 1
            elif context["wave"] == "BUYER_ACTION" and current_tick < config["ticks_per_round"]:
                current_tick += 1
        totals = sum(counters.values(), Counter())
        summary = {"session_id": sid, "status": status, "current_round": current_round, "current_tick": current_tick,
                   "tick_count": len(ticks), "publication_count": publication["version"] + 1,
                   "total_orders": len(facts["orders"]), "total_units_sold": sum(o["quantity"] for o in facts["orders"]),
                   "total_gmv_cents": sum(o["total_cents"] for o in facts["orders"]),
                   "public_message_count": totals["public_messages_sent"], "private_message_count": totals["private_messages_sent"],
                   "succeeded_actions": totals["successful_actions"], "failed_actions": totals["failed_actions"],
                   "skipped_actions": totals["skipped_actions"], "technical_failure_count": technical_failures,
                   "invalid_batch_count": invalid_batches, "metric_schema_version": SCHEMA, "ranking_policy": policy["policy_id"]}
        return {"metric_schema_version": SCHEMA, "policy": deepcopy(policy), "session_id": sid,
                "source_publication_version": publication["version"], "generated_from_committed_state": True,
                "summary": summary, "sellers": sellers, "buyers": buyers, "consistency_errors": errors,
                "price_trajectory": deepcopy(price_history), "tick_history": deepcopy(ticks)}

    def save(publication, end_seq, status):
        payload = report(publication, status)
        payload.update(source_transcript_count=end_seq, source_transcript_digest=digest(records[:end_seq]),
                       source_state_digest=records[end_seq - 1]["state_digest"],
                       economic_visibility="committed_failure_prefix" if status == "failed" else "published")
        snapshots.append({"transcript_count": end_seq, "publication_version": publication["version"],
                          "leaderboard_source_version": boards[-1]["source_publication_version"] if boards else None,
                          "payload": payload})

    for record in records:
        kind = record["kind"]
        if kind == "admission":
            if record["status"] == "invalid_batch":
                invalid_batches += 1
            for entry in record.get("actions", []):
                actions[entry["action_id"]] = {**entry, "actor_id": record["actor_id"], "context": record["context"]}
        elif kind == "action_result":
            entry = actions[record["action_id"]]
            actor, action = entry["actor_id"], entry["action"]
            before_prices = {v["id"]: v["unit_price_cents"] for v in facts["listings"]}
            facts.update({k: deepcopy(v) for k, v in record["changes"].items() if k in facts})
            success = record["result"]["ok"]
            counters[actor]["successful_actions" if success else "failed_actions"] += 1
            if not success and action["type"] == "purchase":
                counters[actor]["failed_purchase_count"] += 1
            if success:
                if action["type"] in ("send_public", "send_private"):
                    counters[actor]["public_messages_sent" if action["type"] == "send_public" else "private_messages_sent"] += 1
                if action["type"] in ("create_listing", "update_listing"):
                    listing = next(v for v in facts["listings"] if v["id"] == action["listing_id"])
                    old = before_prices.get(listing["id"])
                    if old != listing["unit_price_cents"]:
                        if old is not None:
                            counters[actor]["price_change_count"] += 1
                        price_history.append({"seller_id": actor, "listing_id": listing["id"], **entry["context"],
                                              "unit_price_cents": listing["unit_price_cents"], "offer_revision": listing["offer_revision"]})
        elif kind == "skipped":
            counters[actions[record["outcome"]["action_id"]]["actor_id"]]["skipped_actions"] += 1
        elif kind == "published":
            last_publication = record
            tick_close = record["boundary"] == "wave_completed" and record["context"]["wave"] == "BUYER_ACTION"
            if tick_close:
                gmv = sum(o["total_cents"] for o in facts["orders"])
                ticks.append({"round_index": record["context"]["round"], "tick_index": record["context"]["tick"],
                              "source_publication_version": record["version"], "orders_count": len(facts["orders"]) - previous_tick_orders,
                              "sales_revenue_cents": gmv - previous_tick_gmv})
                previous_tick_orders, previous_tick_gmv = len(facts["orders"]), gmv
            refresh = record["boundary"] == "initial" or (tick_close if policy["refresh"] == "tick_close" else record["boundary"] == "round_closed")
            sellers, errors = seller_metrics(setup, facts, counters)
            if refresh and not errors:
                boards.append(leaderboard(sid, record, policy, sellers, boards[-1] if boards else None))
            config = records[0]["market_config"]
            completed = record["boundary"] == "round_closed" and record["context"]["round"] == config["max_rounds"]
            closing = tick_close and record["context"]["tick"] == config["ticks_per_round"]
            save(record, record["seq"] + 1, "completed" if completed else "round_close_pending" if closing else "awaiting_batches")
        elif kind == "aborted":
            technical_failures += 1
            save(last_publication, record["seq"] + 1, "failed")

    # A completed phase may follow the final round-close publication in the SAME commit.
    snapshots[-1]["transcript_count"] = len(records)
    snapshots[-1]["payload"].update(source_transcript_count=len(records), source_transcript_digest=digest(records))
    if snapshots[-1]["payload"]["summary"]["status"] != runtime["status"]:
        raise ValueError("Committed runtime differs from transcript boundary")
    return snapshots, boards
