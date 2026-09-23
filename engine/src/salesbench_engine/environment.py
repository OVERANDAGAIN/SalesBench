"""Single-process in-memory state owner. No network, database or wall clock."""

from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock

from .models import (
    Account, Actor, Buyer, Channel, Conversation, Event, Inventory, Listing,
    ListingView, MarketSetup, MarketSnapshot, MarketTime, Message, Observation,
    Order, Procurement, Product, Seller, Supplier, SupplierOffer, View,
)
from .rules import RankingPolicy, TestGrossSalesRanking


def _integer(value: object, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


class ObservationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass
class _State:
    setup: MarketSetup
    actors: dict[str, Actor]
    products: dict[str, Product]
    accounts: dict[str, Account]
    offers: dict[str, SupplierOffer]
    step: int = 0
    inventory: dict[tuple[str, str], Inventory] = field(default_factory=dict)
    listings: dict[str, Listing] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    procurements: dict[str, Procurement] = field(default_factory=dict)
    conversations: dict[tuple[str, str], Conversation] = field(default_factory=dict)
    messages: list[Message] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


class Engine:
    def __init__(self, setup: MarketSetup, *, ranking: RankingPolicy | None = None):
        setup = deepcopy(setup)
        self._validate_setup(setup)
        self._state = _State(
            setup=setup,
            actors={a.id: a for a in (*setup.suppliers, *setup.sellers, *setup.buyers)},
            products={p.id: p for p in setup.products},
            accounts={a.actor_id: a for a in setup.accounts},
            offers={o.id: o for o in setup.offers},
        )
        self._ranking = ranking if ranking is not None else TestGrossSalesRanking()
        self._lock = RLock()

    @staticmethod
    def _validate_setup(setup: MarketSetup) -> None:
        def require(condition: bool, message: str) -> None:
            if not condition:
                raise ValueError(message)

        require(all(type(rows) is tuple for rows in (setup.suppliers, setup.sellers, setup.buyers, setup.products, setup.offers, setup.accounts)), "Setup collections must be immutable tuples")
        require(_identifier(setup.experiment.id), "Invalid experiment ID")
        require(type(setup.experiment.seed) is int, "Seed must be an integer")
        days = setup.experiment.steps_per_demo_day
        require(days is None or _integer(days, 1), "Invalid demo day mapping")
        actors = (*setup.suppliers, *setup.sellers, *setup.buyers)
        for rows, expected in ((setup.suppliers, Supplier), (setup.sellers, Seller), (setup.buyers, Buyer), (setup.products, Product), (setup.offers, SupplierOffer)):
            require(all(type(row) is expected for row in rows), "Invalid domain record type")
            require(all(_identifier(row.id) for row in rows), "Invalid ID")
            require(len({row.id for row in rows}) == len(rows), "Duplicate ID")
        require(len({a.id for a in actors}) == len(actors), "Actor IDs must be globally unique")
        actor_ids = {a.id for a in actors}
        require(all(isinstance(row.name, str) and bool(row.name.strip()) for row in (*actors, *setup.products)), "Invalid public name")
        require(all(type(a) is Account for a in setup.accounts), "Invalid account record")
        require(len({a.actor_id for a in setup.accounts}) == len(setup.accounts), "Duplicate account")
        require({a.actor_id for a in setup.accounts} == actor_ids, "Exactly one account per actor required")
        require(all(_integer(a.balance_cents) for a in setup.accounts), "Invalid initial money")
        suppliers = {s.id for s in setup.suppliers}
        products = {p.id for p in setup.products}
        for offer in setup.offers:
            require(offer.supplier_id in suppliers and offer.product_id in products, "Invalid offer reference")
            require(_integer(offer.unit_cost_cents) and _integer(offer.available_quantity), "Invalid offer money/stock")
            require(type(offer.active) is bool, "Invalid offer status")

    @staticmethod
    def _time(state: _State) -> MarketTime:
        steps = state.setup.experiment.steps_per_demo_day
        return MarketTime(state.step, None if steps is None else state.step // steps)

    def snapshot(self) -> MarketSnapshot:
        """Trusted host export; policies receive observe() instead."""
        with self._lock:
            s = self._state
            return MarketSnapshot(
                s.setup, self._time(s), tuple(s.accounts.values()), tuple(s.offers.values()),
                tuple(s.inventory.values()), tuple(s.listings.values()), tuple(s.orders.values()),
                tuple(s.procurements.values()), tuple(s.conversations.values()), tuple(s.messages),
                tuple(s.events), tuple(sorted(s.counters.items())),
            )

    def observe(self, actor_id: str, view: View = View.MARKET, *, seller_id: str | None = None, listing_id: str | None = None) -> Observation:
        with self._lock:
            s = self._state
            if not _identifier(actor_id) or actor_id not in s.actors:
                raise ObservationError("ACTOR_NOT_FOUND")
            try:
                view = View(view)
            except (ValueError, TypeError):
                raise ObservationError("INVALID_QUERY") from None
            if seller_id is not None and (not _identifier(seller_id) or not isinstance(s.actors.get(seller_id), Seller)):
                raise ObservationError("SELLER_NOT_FOUND")
            actor = s.actors[actor_id]
            data: dict = {}
            if view in (View.MARKET, View.PRODUCT):
                listings = [v for v in s.listings.values() if v.active and (seller_id is None or v.seller_id == seller_id)]
                if view == View.PRODUCT:
                    if not _identifier(listing_id):
                        raise ObservationError("INVALID_QUERY")
                    listings = [v for v in listings if v.id == listing_id]
                    if not listings:
                        raise ObservationError("LISTING_NOT_FOUND")
                data["listings"] = tuple(self._listing_view(s, v) for v in listings)
            elif view == View.SUPPLIERS:
                if not isinstance(actor, Seller):
                    raise ObservationError("FORBIDDEN")
                data.update(suppliers=s.setup.suppliers, offers=tuple(o for o in s.offers.values() if o.active), products=tuple(s.products.values()))
            elif view == View.LEADERBOARD:
                data.update(ranking=self._ranking.rank(s.setup.sellers, tuple(s.orders.values())), ranking_rule=self._ranking.name)
            elif view == View.SELF:
                data["orders"] = tuple(o for o in s.orders.values() if actor_id in (o.buyer_id, o.seller_id))
                if isinstance(actor, Seller):
                    data.update(inventory=tuple(i for i in s.inventory.values() if i.seller_id == actor_id), listings=tuple(self._listing_view(s, v) for v in s.listings.values() if v.seller_id == actor_id))
                if isinstance(actor, (Seller, Supplier)):
                    data["procurements"] = tuple(p for p in s.procurements.values() if actor_id in (p.seller_id, p.supplier_id))
                if isinstance(actor, Supplier):
                    data["offers"] = tuple(o for o in s.offers.values() if o.supplier_id == actor_id)
            elif view == View.PUBLIC:
                data["messages"] = tuple(m for m in s.messages if m.channel == Channel.PUBLIC and (seller_id is None or m.seller_id == seller_id))
            elif view == View.PRIVATE:
                if isinstance(actor, Supplier) or (isinstance(actor, Seller) and seller_id not in (None, actor_id)):
                    raise ObservationError("FORBIDDEN")
                conversations = tuple(c for c in s.conversations.values() if actor_id in (c.buyer_id, c.seller_id) and (seller_id is None or c.seller_id == seller_id))
                ids = {c.id for c in conversations}
                data.update(conversations=conversations, messages=tuple(m for m in s.messages if m.channel == Channel.PRIVATE and m.conversation_id in ids))
            visible_events = tuple(e for e in s.events if e.audience is None or actor_id in e.audience)
            return Observation(s.setup.experiment.id, self._time(s), actor, s.accounts[actor_id], view, events=visible_events, **data)

    @staticmethod
    def _listing_view(state: _State, listing: Listing) -> ListingView:
        inventory = state.inventory.get((listing.seller_id, listing.product_id))
        return ListingView(listing, state.products[listing.product_id], state.actors[listing.seller_id], inventory.quantity if inventory else 0)
