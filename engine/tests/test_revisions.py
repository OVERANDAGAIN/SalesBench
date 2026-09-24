import unittest

from salesbench_engine.actions import Purchase, UpdateListing
from test_transitions import stocked_engine


class RevisionTests(unittest.TestCase):
    def test_revision_tracks_actual_offer_content_changes_not_assignments_or_stock(self):
        engine = stocked_engine()
        engine.execute("seller", UpdateListing("cup-listing", unit_price_cents=300, description="Test cup", active=True))
        self.assertEqual((engine.snapshot().listings[0].offer_revision, engine.snapshot().listings[0].content_revision), (1, 1))
        engine.execute("seller", UpdateListing("cup-listing", description=" New text "))
        self.assertEqual((engine.snapshot().listings[0].offer_revision, engine.snapshot().listings[0].content_revision), (1, 2))
        engine.execute("seller", UpdateListing("cup-listing", description="New text"))
        self.assertEqual(engine.snapshot().listings[0].content_revision, 2)
        self.assertTrue(engine.execute("buyer", Purchase("cup-listing", 1, 300, 1)).ok)
        self.assertEqual(engine.snapshot().listings[0].offer_revision, 1)
        self.assertEqual(engine.snapshot().orders[0].offer_revision, 1)
        engine.execute("seller", UpdateListing("cup-listing", unit_price_cents=350, active=False, description="Closed"))
        self.assertEqual((engine.snapshot().listings[0].offer_revision, engine.snapshot().listings[0].content_revision), (2, 3))

    def test_price_aba_and_active_aba_reject_old_offer_and_preserve_state(self):
        for changes in ((dict(unit_price_cents=400), dict(unit_price_cents=300)), (dict(active=False), dict(active=True))):
            with self.subTest(changes=changes):
                engine = stocked_engine()
                for change in changes:
                    engine.execute("seller", UpdateListing("cup-listing", **change))
                before = engine.snapshot()
                self.assertEqual(engine.execute("buyer", Purchase("cup-listing", 1, 300, 1)).code, "STALE_LISTING")
                self.assertEqual(engine.snapshot(), before)
                self.assertTrue(engine.execute("buyer", Purchase("cup-listing", 1, 300, 3)).ok)
                self.assertEqual(engine.snapshot().orders[0].offer_revision, 3)

    def test_price_then_revision_then_active_precedence_and_revision_validation(self):
        engine = stocked_engine()
        engine.execute("seller", UpdateListing("cup-listing", unit_price_cents=400, active=False))
        before = engine.snapshot()
        for price, revision, expected in ((300, 1, "PRICE_CHANGED"), (400, 1, "STALE_LISTING"), (400, 2, "LISTING_INACTIVE"),
                                          (400, True, "INVALID_REVISION"), (400, 0, "INVALID_REVISION")):
            self.assertEqual(engine.execute("buyer", Purchase("cup-listing", 1, price, revision)).code, expected)
            self.assertEqual(engine.snapshot(), before)
