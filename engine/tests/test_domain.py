import unittest
from dataclasses import FrozenInstanceError, replace

from salesbench_engine import Engine
from salesbench_engine.environment import ObservationError
from salesbench_engine.models import Account, Buyer, Experiment, MarketSetup, Product, Seller, Supplier, SupplierOffer, View


def make_setup(**experiment_options):
    return MarketSetup(
        Experiment("test-session", **experiment_options),
        (Supplier("supplier", "Test supplier"),),
        (Seller("seller", "Test seller"), Seller("other-seller", "Other seller")),
        (Buyer("buyer", "Test buyer"), Buyer("other-buyer", "Other buyer")),
        (Product("cup", "Cup"), Product("bag", "Bag")),
        (SupplierOffer("cup-offer", "supplier", "cup", 100, 20), SupplierOffer("bag-offer", "supplier", "bag", 200, 10)),
        (Account("supplier", 0), Account("seller", 1000), Account("other-seller", 1000), Account("buyer", 1000), Account("other-buyer", 1000)),
    )


class DomainTests(unittest.TestCase):
    def test_supplier_offer_does_not_make_inventory_or_listing(self):
        engine = Engine(make_setup())
        self.assertEqual(len(engine.observe("seller", View.SUPPLIERS).offers), 2)
        self.assertEqual(engine.snapshot().inventory, ())
        self.assertEqual(engine.observe("buyer").listings, ())

    def test_buyer_cannot_observe_procurement_costs_or_other_balances(self):
        engine = Engine(make_setup())
        observation = engine.observe("buyer", View.SELF)
        self.assertEqual(observation.account, Account("buyer", 1000))
        self.assertEqual(observation.offers, ())
        self.assertEqual(observation.procurements, ())
        with self.assertRaises(ObservationError) as error:
            engine.observe("buyer", View.SUPPLIERS)
        self.assertEqual(error.exception.code, "FORBIDDEN")

    def test_observation_and_snapshot_records_are_immutable(self):
        engine = Engine(make_setup())
        with self.assertRaises(FrozenInstanceError):
            engine.observe("buyer").account.balance_cents = 1
        with self.assertRaises(FrozenInstanceError):
            engine.snapshot().offers[0].unit_cost_cents = 1
        self.assertEqual(engine.observe("buyer").account.balance_cents, 1000)

    def test_invalid_initial_state_is_rejected(self):
        setup = make_setup()
        invalid = (
            replace(setup, buyers=setup.buyers + (Buyer("seller", "Duplicate"),)),
            replace(setup, accounts=setup.accounts[:-1]),
            replace(setup, offers=(replace(setup.offers[0], product_id="missing"),)),
            replace(setup, accounts=(Account("supplier", -1), *setup.accounts[1:])),
            replace(setup, offers=(replace(setup.offers[0], unit_cost_cents=True),)),
            replace(setup, experiment=Experiment("session", steps_per_demo_day=0)),
        )
        for case in invalid:
            with self.subTest(case=case), self.assertRaises(ValueError):
                Engine(case)

    def test_unknown_actor_and_invalid_observation_fail_closed(self):
        engine = Engine(make_setup())
        for actor, view in (("missing", View.MARKET), ("buyer", "everything")):
            with self.subTest(actor=actor), self.assertRaises(ObservationError):
                engine.observe(actor, view)

    def test_ranking_is_explicitly_a_replaceable_test_rule(self):
        engine = Engine(make_setup())
        observation = engine.observe("buyer", View.LEADERBOARD)
        self.assertEqual(observation.ranking_rule, "test_gross_sales")
        self.assertEqual([r.seller_id for r in observation.ranking], ["other-seller", "seller"])


if __name__ == "__main__":
    unittest.main()
