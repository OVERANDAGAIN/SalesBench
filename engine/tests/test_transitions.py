import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import patch

from salesbench_engine import Engine, ObservationError
from salesbench_engine.actions import CreateListing, Procure, Purchase, SendPrivate, SendPublic, UpdateListing, Wait
from salesbench_engine.models import Channel, View
from test_domain import make_setup


def stocked_engine(quantity=5, price=300):
    engine = Engine(make_setup(steps_per_demo_day=2))
    for action in (Procure("cup-offer", quantity, 100), CreateListing("cup-listing", "cup", price, "Test cup")):
        result = engine.execute("seller", action)
        if not result.ok:
            raise AssertionError(f"Fixture action failed: {result.code}")
    return engine


class TransitionTests(unittest.TestCase):
    def assert_rejected_without_change(self, engine, actor, action, code):
        before = engine.snapshot()
        result = engine.execute(actor, action)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, code)
        self.assertEqual(result.events, ())
        self.assertEqual(engine.snapshot(), before)

    def test_procurement_moves_money_and_goods_between_supplier_and_seller(self):
        engine = Engine(make_setup())
        result = engine.execute("seller", Procure("cup-offer", 3, 100))
        self.assertTrue(result.ok)
        seller = engine.observe("seller", View.SELF)
        supplier = engine.observe("supplier", View.SELF)
        self.assertEqual(seller.account.balance_cents, 700)
        self.assertEqual(supplier.account.balance_cents, 300)
        self.assertEqual(seller.inventory[0].quantity, 3)
        self.assertEqual(supplier.offers[0].available_quantity, 17)
        self.assertEqual(seller.procurements, supplier.procurements)
        self.assertEqual(seller.procurements[0].total_cents, 300)
        self.assertEqual(result.events[0].kind, "procured")
        self.assertEqual(engine.observe("buyer").events, ())

    def test_procurement_insufficient_funds_preserves_entire_state(self):
        self.assert_rejected_without_change(Engine(make_setup()), "seller", Procure("cup-offer", 11, 100), "INSUFFICIENT_FUNDS")

    def test_procurement_rejects_invalid_offer_price_quantity_and_actor(self):
        engine = Engine(make_setup())
        for actor, action, code in (
            ("buyer", Procure("cup-offer", 1, 100), "FORBIDDEN"),
            ("seller", Procure("missing", 1, 100), "OFFER_NOT_FOUND"),
            ("seller", Procure("cup-offer", 1, 99), "PRICE_CHANGED"),
            ("seller", Procure("cup-offer", 21, 100), "OUT_OF_STOCK"),
            ("seller", Procure("cup-offer", True, 100), "INVALID_QUANTITY"),
            ("seller", Procure("cup-offer", 1, 100.0), "INVALID_PRICE"),
        ):
            with self.subTest(action=action):
                self.assert_rejected_without_change(engine, actor, action, code)
        setup = make_setup()
        closed = Engine(replace(setup, offers=(replace(setup.offers[0], active=False),)))
        self.assert_rejected_without_change(closed, "seller", Procure("cup-offer", 1, 100), "OFFER_INACTIVE")

    def test_listing_requires_owned_stock_and_maintains_separate_product_and_cost(self):
        engine = Engine(make_setup())
        self.assert_rejected_without_change(engine, "seller", CreateListing("cup-listing", "cup", 300, "Cup"), "OUT_OF_STOCK")
        engine.execute("seller", Procure("cup-offer", 2, 100))
        result = engine.execute("seller", CreateListing("cup-listing", "cup", 300, " First description "))
        self.assertTrue(result.ok)
        result = engine.execute("seller", UpdateListing("cup-listing", unit_price_cents=350, description="New description"))
        self.assertTrue(result.ok)
        visible = engine.observe("buyer", View.PRODUCT, listing_id="cup-listing").listings[0]
        self.assertEqual(visible.listing.unit_price_cents, 350)
        self.assertEqual(visible.listing.description, "New description")
        self.assertEqual(visible.product.name, "Cup")
        self.assertEqual(visible.available_quantity, 2)
        self.assertEqual(engine.observe("seller", View.SUPPLIERS).offers[0].unit_cost_cents, 100)

    def test_listing_ids_and_ownership_cannot_be_overwritten(self):
        engine = stocked_engine()
        for actor, action, code in (
            ("seller", CreateListing("cup-listing", "cup", 1, "Overwrite"), "LISTING_ID_CONFLICT"),
            ("other-seller", UpdateListing("cup-listing", unit_price_cents=1), "FORBIDDEN"),
            ("buyer", UpdateListing("cup-listing", active=False), "FORBIDDEN"),
            ("seller", UpdateListing("cup-listing"), "EMPTY_UPDATE"),
        ):
            with self.subTest(action=action):
                self.assert_rejected_without_change(engine, actor, action, code)

    def test_buyer_observation_excludes_other_orders_inventory_costs_and_money(self):
        engine = stocked_engine()
        engine.execute("buyer", Purchase("cup-listing", 1, 300, 1))
        owner = engine.observe("buyer", View.SELF)
        other = engine.observe("other-buyer", View.SELF)
        self.assertEqual(len(owner.orders), 1)
        self.assertEqual(other.orders, ())
        self.assertEqual(other.account.balance_cents, 1000)
        self.assertEqual(other.inventory, ())
        self.assertEqual(other.offers, ())
        self.assertEqual(other.procurements, ())
        self.assertFalse(any(e.kind in ("procured", "purchased") for e in other.events))
        self.assertEqual(engine.observe("other-seller", View.SELF).orders, ())

    def test_public_messages_and_seller_replies_are_visible(self):
        engine = stocked_engine()
        self.assertTrue(engine.execute("buyer", SendPublic("seller", " In stock? ")).ok)
        self.assertTrue(engine.execute("seller", SendPublic("seller", "Yes.")).ok)
        first = engine.observe("buyer", View.PUBLIC, seller_id="seller")
        other = engine.observe("other-buyer", View.PUBLIC, seller_id="seller")
        self.assertEqual(first.messages, other.messages)
        self.assertEqual([m.text for m in first.messages], ["In stock?", "Yes."])
        self.assertTrue(all(m.channel == Channel.PUBLIC and m.conversation_id is None for m in first.messages))
        self.assertEqual(engine.observe("buyer", View.PUBLIC, seller_id="other-seller").messages, ())

    def test_private_conversations_messages_and_events_are_participant_scoped(self):
        engine = stocked_engine()
        secret = engine.execute("buyer", SendPrivate("seller", "First buyer secret"))
        engine.execute("seller", SendPrivate("buyer", "First buyer reply"))
        engine.execute("other-buyer", SendPrivate("seller", "Second buyer secret"))
        first = engine.observe("buyer", View.PRIVATE)
        second = engine.observe("other-buyer", View.PRIVATE)
        seller = engine.observe("seller", View.PRIVATE)
        self.assertEqual([m.text for m in first.messages], ["First buyer secret", "First buyer reply"])
        self.assertEqual([m.text for m in second.messages], ["Second buyer secret"])
        self.assertEqual(len(seller.messages), 3)
        self.assertEqual(len(seller.conversations), 2)
        self.assertEqual(len(first.conversations), 1)
        self.assertFalse(any(e.entity_id == secret.entity_id for e in second.events))
        self.assertEqual(engine.observe("other-seller", View.PRIVATE).messages, ())
        self.assertEqual(engine.observe("buyer", View.PRIVATE, seller_id="other-seller").messages, ())
        with self.assertRaises(ObservationError):
            engine.observe("supplier", View.PRIVATE)
        with self.assertRaises(ObservationError):
            engine.observe("other-seller", View.PRIVATE, seller_id="seller")

    def test_invalid_messages_cannot_create_conversations_or_impersonate_sellers(self):
        engine = stocked_engine()
        for actor, action, code in (
            ("buyer", SendPrivate("other-buyer", "Hello"), "FORBIDDEN"),
            ("buyer", SendPrivate("missing", "Hello"), "RECIPIENT_NOT_FOUND"),
            ("buyer", SendPrivate("seller", "   "), "INVALID_TEXT"),
            ("buyer", SendPublic("seller", "a" * 501), "INVALID_TEXT"),
            ("other-seller", SendPublic("seller", "Impersonation"), "FORBIDDEN"),
            ("supplier", SendPrivate("buyer", "Hello"), "FORBIDDEN"),
        ):
            with self.subTest(action=action):
                self.assert_rejected_without_change(engine, actor, action, code)

    def test_purchase_cash_stock_order_and_event_are_consistent(self):
        engine = stocked_engine()
        result = engine.execute("buyer", Purchase("cup-listing", 2, 300, 1))
        self.assertTrue(result.ok)
        buyer = engine.observe("buyer", View.SELF)
        seller = engine.observe("seller", View.SELF)
        self.assertEqual(buyer.account.balance_cents, 400)
        self.assertEqual(seller.account.balance_cents, 1100)
        self.assertEqual(seller.inventory[0].quantity, 3)
        self.assertEqual(buyer.orders, seller.orders)
        order = buyer.orders[0]
        self.assertEqual((order.quantity, order.unit_price_cents, order.total_cents), (2, 300, 600))
        self.assertEqual((order.id, order.step, order.settlement), (result.entity_id, 0, "test_immediate"))
        self.assertEqual(result.events[0].kind, "purchased")
        engine.execute("seller", UpdateListing("cup-listing", unit_price_cents=350))
        self.assertEqual(engine.observe("buyer", View.SELF).orders[0], order)

    def test_purchase_insufficient_buyer_money_is_atomic(self):
        self.assert_rejected_without_change(stocked_engine(price=1100), "buyer", Purchase("cup-listing", 1, 1100, 1), "INSUFFICIENT_FUNDS")

    def test_purchase_insufficient_seller_stock_is_atomic(self):
        self.assert_rejected_without_change(stocked_engine(), "buyer", Purchase("cup-listing", 6, 300, 1), "OUT_OF_STOCK")

    def test_purchase_stale_expected_price_is_atomic(self):
        engine = stocked_engine()
        observed = engine.observe("buyer", View.PRODUCT, listing_id="cup-listing").listings[0]
        engine.execute("seller", UpdateListing("cup-listing", unit_price_cents=350))
        self.assert_rejected_without_change(engine, "buyer", Purchase("cup-listing", 1, observed.listing.unit_price_cents, 1), "PRICE_CHANGED")

    def test_purchase_rejects_bad_actor_listing_status_quantity_and_price(self):
        engine = stocked_engine()
        for actor, action, code in (
            ("missing", Purchase("cup-listing", 1, 300, 1), "ACTOR_NOT_FOUND"),
            ("seller", Purchase("cup-listing", 1, 300, 1), "FORBIDDEN"),
            ("buyer", Purchase("missing", 1, 300, 1), "LISTING_NOT_FOUND"),
            ("buyer", Purchase([], 1, 300, 1), "INVALID_ID"),
            ("buyer", Purchase("cup-listing", 1, True, 1), "INVALID_PRICE"),
            ("buyer", {"type": "purchase", "actor_id": "other-buyer"}, "INVALID_ACTION"),
        ):
            with self.subTest(action=action):
                self.assert_rejected_without_change(engine, actor, action, code)
        for quantity in (0, -1, True, 1.5, "1"):
            with self.subTest(quantity=quantity):
                self.assert_rejected_without_change(engine, "buyer", Purchase("cup-listing", quantity, 300, 1), "INVALID_QUANTITY")
        engine.execute("seller", UpdateListing("cup-listing", active=False))
        self.assert_rejected_without_change(engine, "buyer", Purchase("cup-listing", 1, 300, 2), "LISTING_INACTIVE")
        self.assertEqual(engine.observe("buyer").listings, ())
        with self.assertRaises(ObservationError):
            engine.observe("buyer", View.PRODUCT, listing_id="cup-listing")

    def test_multi_field_update_cannot_partially_apply(self):
        self.assert_rejected_without_change(stocked_engine(), "seller", UpdateListing("cup-listing", unit_price_cents=250, description=" "), "INVALID_TEXT")

    def test_exception_after_draft_mutation_does_not_commit_or_consume_ids(self):
        engine = stocked_engine()
        before = engine.snapshot()
        with patch.object(engine, "_emit", side_effect=RuntimeError("Injected failure")):
            with self.assertRaisesRegex(RuntimeError, "Injected failure"):
                engine.execute("buyer", Purchase("cup-listing", 1, 300, 1))
        self.assertEqual(engine.snapshot(), before)
        result = engine.execute("buyer", Purchase("cup-listing", 1, 300, 1))
        self.assertEqual(result.entity_id, "order-000001")

    def test_advance_preserves_market_and_assigns_steps_without_wall_clock(self):
        engine = stocked_engine()
        engine.execute("buyer", Purchase("cup-listing", 1, 300, 1))
        before = engine.observe("buyer", View.SELF)
        result = engine.advance(2)
        after = engine.observe("buyer", View.SELF)
        self.assertEqual([e.step for e in result.events], [1, 2])
        self.assertEqual((after.time.step, after.time.demo_day), (2, 1))
        self.assertEqual(after.account, before.account)
        self.assertEqual(after.orders, before.orders)
        engine.execute("buyer", SendPrivate("seller", "Next round"))
        self.assertEqual(engine.observe("buyer", View.PRIVATE).messages[0].step, 2)
        self.assertTrue(engine.execute("buyer", Purchase("cup-listing", 1, 300, 1)).ok)

    def test_invalid_advance_cannot_change_state(self):
        engine = stocked_engine()
        before = engine.snapshot()
        for steps in (0, -1, True, 0.5):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                engine.advance(steps)
            self.assertEqual(engine.snapshot(), before)

    def test_wait_logs_abstention_without_money_stock_or_time_changes(self):
        engine = stocked_engine()
        before = engine.snapshot()
        result = engine.execute("other-buyer", Wait())
        after = engine.snapshot()
        self.assertTrue(result.ok)
        self.assertEqual(after.accounts, before.accounts)
        self.assertEqual(after.inventory, before.inventory)
        self.assertEqual(after.orders, before.orders)
        self.assertEqual(after.time, before.time)
        self.assertEqual(result.events[0].kind, "waited")
        self.assertNotIn(result.events[0], engine.observe("buyer").events)

    def test_multiple_listings_share_owned_stock_without_double_counting(self):
        engine = stocked_engine(quantity=1)
        self.assertTrue(engine.execute("seller", CreateListing("second-listing", "cup", 250, "Same stock")).ok)
        self.assertTrue(engine.execute("buyer", Purchase("cup-listing", 1, 300, 1)).ok)
        self.assert_rejected_without_change(engine, "other-buyer", Purchase("second-listing", 1, 250, 1), "OUT_OF_STOCK")
        self.assertEqual([v.available_quantity for v in engine.observe("buyer").listings], [0, 0])

    def test_competing_buyers_cannot_buy_the_same_last_unit(self):
        engine = stocked_engine(quantity=1)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda actor: engine.execute(actor, Purchase("cup-listing", 1, 300, 1)), ("buyer", "other-buyer")))
        self.assertEqual(sum(r.ok for r in results), 1)
        self.assertEqual([r.code for r in results if not r.ok], ["OUT_OF_STOCK"])
        state = engine.snapshot()
        self.assertEqual(len(state.orders), 1)
        self.assertEqual(state.inventory[0].quantity, 0)
        self.assertEqual(sum(a.balance_cents for a in state.accounts), 4000)

    def test_sessions_have_independent_state_and_counters(self):
        first = stocked_engine()
        second = Engine(make_setup())
        before = second.snapshot()
        first.execute("buyer", Purchase("cup-listing", 1, 300, 1))
        first.advance()
        self.assertEqual(second.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
