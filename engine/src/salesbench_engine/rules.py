"""Named TEST rules, not agreed research mechanisms."""

from collections import defaultdict
from typing import Protocol

from .models import Order, RankingEntry, Seller


class RankingPolicy(Protocol):
    name: str

    def rank(self, sellers: tuple[Seller, ...], orders: tuple[Order, ...]) -> tuple[RankingEntry, ...]: ...


class TestGrossSalesRanking:
    """TEST: publish gross sales and units; ties use stable seller IDs."""

    name = "test_gross_sales"

    def rank(self, sellers: tuple[Seller, ...], orders: tuple[Order, ...]) -> tuple[RankingEntry, ...]:
        totals: dict[str, int] = defaultdict(int)
        units: dict[str, int] = defaultdict(int)
        for order in orders:
            totals[order.seller_id] += order.total_cents
            units[order.seller_id] += order.quantity
        ordered = sorted(sellers, key=lambda seller: (-totals[seller.id], seller.id))
        return tuple(RankingEntry(s.id, rank, totals[s.id], units[s.id]) for rank, s in enumerate(ordered, 1))
