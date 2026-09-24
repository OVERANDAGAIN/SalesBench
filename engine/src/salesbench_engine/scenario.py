"""Command-line TEST scenario, deliberately not a platform API or research model."""

import argparse
import json
from random import Random

from .actions import CreateListing, Procure, Purchase, SendPrivate, SendPublic, UpdateListing, Wait
from .environment import Engine
from .models import Account, Buyer, Channel, Experiment, MarketSetup, Product, Seller, Supplier, SupplierOffer, View
from .policies import Policy, ScriptedDecision, ScriptedPolicy


def run_demo(seed: int = 7) -> dict:
    setup = MarketSetup(
        Experiment("test-scripted-market", seed, steps_per_demo_day=2),
        (Supplier("supplier", "Test supplier"),),
        (Seller("seller", "Test shop"),),
        (Buyer("buyer", "Buying participant"), Buyer("observer", "Waiting participant")),
        (Product("cup", "Cup"), Product("bag", "Bag")),
        (SupplierOffer("cup-offer", "supplier", "cup", 100, 10), SupplierOffer("bag-offer", "supplier", "bag", 200, 10)),
        (Account("supplier", 0), Account("seller", 2000), Account("buyer", 2000), Account("observer", 1000)),
    )
    engine = Engine(setup)
    # Only a local, seeded RNG; neither execution timing nor global random state.
    cup_price = Random(seed).choice((250, 300, 350))
    seller = ScriptedPolicy((
        ScriptedDecision(0, Procure("cup-offer", 4, 100)),
        ScriptedDecision(0, Procure("bag-offer", 2, 200)),
        ScriptedDecision(0, CreateListing("cup-listing", "cup", 250, "Initial cup listing")),
        ScriptedDecision(0, CreateListing("bag-listing", "bag", 450, "Test bag listing")),
        ScriptedDecision(0, UpdateListing("cup-listing", unit_price_cents=cup_price, description="Updated TEST offer")),
        ScriptedDecision(0, SendPublic("seller", "Yes, cups are available.")),
        ScriptedDecision(1, SendPrivate("buyer", "Scripted reply after one engine step.")),
    ))
    buyer = ScriptedPolicy((
        ScriptedDecision(0, SendPublic("seller", "Are cups available?")),
        ScriptedDecision(0, SendPrivate("seller", "Please tell me about the bag.")),
        ScriptedDecision(0, Purchase("cup-listing", 2, cup_price, 1 if cup_price == 250 else 2)),
        ScriptedDecision(1, Purchase("bag-listing", 1, 450, 1)),
    ))

    def turn(actor_id: str, policy: Policy, view: View = View.MARKET) -> None:
        intention = policy.decide(engine.observe(actor_id, view))
        result = engine.execute(actor_id, intention)
        if not result.ok:
            raise RuntimeError(f"Scenario action failed: {actor_id} {type(intention).__name__} {result.code}")

    def check(condition: bool, label: str) -> None:
        if not condition:
            raise RuntimeError(f"Scenario invariant failed: {label}")

    turn("supplier", ScriptedPolicy((ScriptedDecision(0, Wait()),)), View.SELF)
    offers = engine.observe("seller", View.SUPPLIERS).offers
    check(len(offers) == 2, "supplier observation")
    for _ in range(2):
        turn("seller", seller, View.SUPPLIERS)
    procured = engine.observe("seller", View.SELF)
    check(procured.account.balance_cents == 1200, "procurement debit")
    check({i.product_id: i.quantity for i in procured.inventory} == {"cup": 4, "bag": 2}, "procured inventory")
    for _ in range(3):
        turn("seller", seller, View.SELF)
    check(len(engine.observe("buyer").listings) == 2, "buyer market observation")
    turn("buyer", buyer, View.PUBLIC)
    turn("seller", seller, View.PUBLIC)
    turn("buyer", buyer, View.PRIVATE)
    turn("observer", ScriptedPolicy((ScriptedDecision(0, Wait()),)))
    turn("buyer", buyer)
    first_round = engine.observe("buyer", View.SELF)
    check(first_round.account.balance_cents == 2000 - cup_price * 2, "purchase debit")
    check(engine.observe("seller", View.SELF).account.balance_cents == 1200 + cup_price * 2, "seller credit")
    check(len(first_round.orders) == 1, "first order")
    check(len(engine.observe("buyer", View.PUBLIC).messages) == 2, "public exchange")
    engine.advance()
    continued = engine.observe("buyer", View.SELF)
    check(continued.account == first_round.account and continued.orders == first_round.orders, "continuity after advance")
    turn("seller", seller, View.PRIVATE)
    turn("buyer", buyer)
    snapshot = engine.snapshot()
    own_private = engine.observe("buyer", View.PRIVATE)
    check([m.step for m in own_private.messages] == [0, 1], "delayed private reply")
    check(engine.observe("observer", View.PRIVATE).messages == (), "private message isolation")
    check(engine.observe("observer", View.SELF).orders == (), "order isolation")
    check(sum(a.balance_cents for a in snapshot.accounts) == 5000, "money conservation")
    check([o.step for o in snapshot.orders] == [0, 1], "two-round orders")
    return {
        "scenario": "TEST scripted procurement-to-sale",
        "seed": seed,
        "step": snapshot.time.step,
        "demo_day": snapshot.time.demo_day,
        "test_rules": ["immediate_procurement", "immediate_cash_settlement", "gross_sales_ranking", "two_steps_per_demo_day"],
        "cup_price_cents": cup_price,
        "balances_cents": {a.actor_id: a.balance_cents for a in snapshot.accounts},
        "inventory": {i.product_id: i.quantity for i in snapshot.inventory},
        "orders": [{"id": o.id, "product_id": o.product_id, "quantity": o.quantity, "total_cents": o.total_cents, "step": o.step} for o in snapshot.orders],
        "counts": {
            "procurements": len(snapshot.procurements),
            "listings": len(snapshot.listings),
            "public_messages": sum(m.channel == Channel.PUBLIC for m in snapshot.messages),
            "private_messages": sum(m.channel == Channel.PRIVATE for m in snapshot.messages),
            "events": len(snapshot.events),
        },
        "checks": "passed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    arguments = parser.parse_args()
    print(json.dumps(run_demo(arguments.seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
