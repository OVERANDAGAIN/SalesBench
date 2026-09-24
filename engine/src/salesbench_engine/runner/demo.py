"""Small TEST benchmark, no network or model service. JSON output is not an API."""

import argparse
import asyncio
import json
from pathlib import Path

from ..actions import CreateListing, Procure, Purchase, SendPrivate, SendPublic, UpdateListing, Wait
from ..models import Account, Buyer, Experiment, MarketSetup, Product, Seller, Supplier, SupplierOffer
from .codec import digest
from .drivers import ScriptedDriver
from .protocol import MarketConfig
from .replay import replay
from .scheduler import Runner


def demo_setup(seed=7):
    return MarketSetup(
        Experiment("wave-demo", seed), (Supplier("supplier", "TEST supplier"),),
        tuple(Seller(f"seller-{n}", f"TEST seller {n}") for n in range(1, 4)),
        tuple(Buyer(f"buyer-{n}", f"TEST buyer {n}") for n in range(1, 5)),
        (Product("cup", "Cup"), Product("bag", "Bag")),
        (SupplierOffer("cups", "supplier", "cup", 100, 30), SupplierOffer("bags", "supplier", "bag", 200, 30)),
        (Account("supplier", 0), *(Account(f"seller-{n}", 2000) for n in range(1, 4)),
         *(Account(f"buyer-{n}", 2000) for n in range(1, 5))),
    )


def demo_script(obs):
    actor = obs.actor_id
    context = obs.context
    if context.wave == "ROUND_PROCUREMENT":
        return (Procure("cups", 1 if actor == "seller-1" else 2, 100),)
    if context.wave == "SELLER_STRATEGY":
        listing = actor + "/cup"
        if context.round == 1 and context.tick == 1:
            return (CreateListing(listing, "cup", 300, "TEST cup"), SendPublic(actor, "Cups available."))
        if context.tick == 2:
            return (UpdateListing(listing, unit_price_cents=350, description="Updated TEST cup"),
                    SendPrivate("buyer-1", "Scripted reply in next Seller Wave."))
        return (Wait(),)
    if context.tick == 1:
        listing = next(x.listing for x in obs.state.public.listings if x.listing.id == "seller-1/cup")
        return (SendPrivate("seller-1", "I would like one cup."),
                Purchase(listing.id, 1, listing.unit_price_cents, listing.offer_revision))
    return (Wait(),)


async def run_demo(seed=7, resolution_seed=7):
    setup = demo_setup(seed)
    runner = Runner(setup, {a.id: ScriptedDriver(demo_script) for a in (*setup.sellers, *setup.buyers)},
                    config=MarketConfig(resolution_seed=resolution_seed))
    await runner.run()
    return runner


def summary(runner):
    state = runner.economic_state()
    records = runner.journal.records
    return {
        "scenario": "TEST Market Wave Runner", "phase": runner.phase, "step": state.time.step,
        "market_seed": state.setup.experiment.seed, "resolution_seed": runner.config.resolution_seed,
        "state_digest": digest(state),
        "round_closes": [r["round"] for r in records if r["kind"] == "round_closed"],
        "waves": [{"round": r["context"]["round"], "tick": r["context"]["tick"], "wave": r["context"]["wave"],
                   "published_version": r["version"]} for r in records if r["kind"] == "published" and r["boundary"] == "wave_completed"],
        "purchase_resolutions": [{"context": r["context"], "order": r["order"]} for r in records if r["kind"] == "resolution" and r["purpose"] == "purchase" and r["order"]],
        "orders": [{"buyer": o.buyer_id, "listing": o.listing_id, "quantity": o.quantity, "total_cents": o.total_cents,
                    "offer_revision": o.offer_revision, "step": o.step} for o in state.orders],
        "balances_cents": {a.actor_id: a.balance_cents for a in state.accounts},
        "business_failures": [r["result"]["code"] for r in records if r["kind"] == "action_result" and not r["result"]["ok"]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--resolution-seed", type=int, default=7)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.replay:
        runner = asyncio.run(replay(json.loads(args.replay.read_text(encoding="utf-8"))))
    else:
        runner = asyncio.run(run_demo(args.seed, args.resolution_seed))
    if args.journal:
        runner.journal.write(args.journal)
    print(json.dumps({**summary(runner), "replay_verified": bool(args.replay)}, ensure_ascii=False, indent=2))
    if runner.phase != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
