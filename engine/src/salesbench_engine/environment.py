"""Single-process in-memory state owner. No network, database or wall clock."""

from copy import deepcopy
from dataclasses import dataclass, field, replace
from threading import RLock

from .actions import Action, CreateListing, Procure, Purchase, SendPrivate, SendPublic, UpdateListing, Wait

from .models import (
    Account, Actor, Buyer, Channel, Conversation, Event, Inventory, Listing,
    ListingView, MarketSetup, MarketSnapshot, MarketTime, Message, Observation,
    Order, Procurement, Product, Result, Seller, Supplier, SupplierOffer, View,
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


class _Rejected(Exception):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise _Rejected(code)


def _text(value: object, limit: int) -> str:
    _require(isinstance(value, str), "INVALID_TEXT")
    text = value.strip()
    _require(0 < len(text) <= limit, "INVALID_TEXT")
    return text


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
            if (listing_id is not None and view != View.PRODUCT) or (seller_id is not None and view not in (View.MARKET, View.PRODUCT, View.PUBLIC, View.PRIVATE)):
                raise ObservationError("INVALID_QUERY")
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

    def execute(self, actor_id: str, action: Action) -> Result:
        """Host-bound identity. A failed action leaves even events/IDs unchanged.

        Each successful call is a NEW intention; transport retries/idempotency
        belong to the future application adapter, not this synchronous boundary.
        """
        with self._lock:
            draft = deepcopy(self._state)
            first_event = len(draft.events)
            try:
                _require(_identifier(actor_id) and actor_id in draft.actors, "ACTOR_NOT_FOUND")
                _require(type(action) in (Procure, CreateListing, UpdateListing, SendPublic, SendPrivate, Purchase, Wait), "INVALID_ACTION")
                entity_id = self._apply(draft, actor_id, action)
                self._check_invariants(draft)
            except _Rejected as error:
                return Result(False, str(error), self._state.step)
            # Unexpected implementation exceptions also leave the original intact.
            self._state = draft
            return Result(True, "OK", draft.step, entity_id, tuple(draft.events[first_event:]))

    def advance(self, steps: int = 1) -> Result:
        """Trusted environment clock. Host may run due policies after each tick.

        No participant action, sleep, background task or implicit policy call.
        advance(n) emits n ticks; use n calls to advance(1) to interleave policies.
        """
        if not _integer(steps, 1):
            raise ValueError("steps must be a positive integer")
        with self._lock:
            draft = deepcopy(self._state)
            first_event = len(draft.events)
            for _ in range(steps):
                draft.step += 1
                self._emit(draft, "time_advanced", None, None)
            self._state = draft
            return Result(True, "OK", draft.step, events=tuple(draft.events[first_event:]))

    @staticmethod
    def _id(state: _State, prefix: str) -> str:
        state.counters[prefix] = state.counters.get(prefix, 0) + 1
        return f"{prefix}-{state.counters[prefix]:06d}"

    @classmethod
    def _emit(cls, state: _State, kind: str, actor_id: str | None, entity_id: str | None, audience: tuple[str, ...] | None = None) -> None:
        state.events.append(Event(cls._id(state, "event"), kind, state.step, actor_id, entity_id, audience))

    @staticmethod
    def _transfer(state: _State, payer: str, payee: str, total_cents: int) -> None:
        # TEST immediate cash settlement. No credit, fees, escrow or fulfillment.
        account = state.accounts[payer]
        _require(account.balance_cents >= total_cents, "INSUFFICIENT_FUNDS")
        state.accounts[payer] = replace(account, balance_cents=account.balance_cents - total_cents)
        receiver = state.accounts[payee]
        state.accounts[payee] = replace(receiver, balance_cents=receiver.balance_cents + total_cents)

    @staticmethod
    def _check_invariants(state: _State) -> None:
        initial_money = sum(a.balance_cents for a in state.setup.accounts)
        if sum(a.balance_cents for a in state.accounts.values()) != initial_money:
            raise RuntimeError("Money conservation violated")
        if any(not _integer(a.balance_cents) for a in state.accounts.values()):
            raise RuntimeError("Invalid account balance")
        if any(not _integer(i.quantity) for i in state.inventory.values()) or any(not _integer(o.available_quantity) for o in state.offers.values()):
            raise RuntimeError("Invalid stock")
        for product in state.setup.products:
            supplied = sum(o.available_quantity for o in state.setup.offers if o.product_id == product.id)
            remaining = sum(o.available_quantity for o in state.offers.values() if o.product_id == product.id)
            owned = sum(i.quantity for i in state.inventory.values() if i.product_id == product.id)
            sold = sum(o.quantity for o in state.orders.values() if o.product_id == product.id)
            if supplied != remaining + owned + sold:
                raise RuntimeError("Goods conservation violated")

    def _apply(self, state: _State, actor_id: str, action: Action) -> str | None:
        actor = state.actors[actor_id]
        if isinstance(action, Procure):
            _require(isinstance(actor, Seller), "FORBIDDEN")
            _require(_identifier(action.offer_id), "INVALID_ID")
            _require(_integer(action.quantity, 1), "INVALID_QUANTITY")
            _require(_integer(action.expected_unit_cost_cents), "INVALID_PRICE")
            offer = state.offers.get(action.offer_id)
            _require(offer is not None, "OFFER_NOT_FOUND")
            _require(offer.active, "OFFER_INACTIVE")
            _require(offer.unit_cost_cents == action.expected_unit_cost_cents, "PRICE_CHANGED")
            _require(offer.available_quantity >= action.quantity, "OUT_OF_STOCK")
            total = offer.unit_cost_cents * action.quantity
            self._transfer(state, actor_id, offer.supplier_id, total)
            state.offers[offer.id] = replace(offer, available_quantity=offer.available_quantity - action.quantity)
            key = (actor_id, offer.product_id)
            previous = state.inventory.get(key, Inventory(*key, 0))
            state.inventory[key] = replace(previous, quantity=previous.quantity + action.quantity)
            record_id = self._id(state, "procurement")
            state.procurements[record_id] = Procurement(record_id, actor_id, offer.supplier_id, offer.id, offer.product_id, action.quantity, offer.unit_cost_cents, total, state.step)
            self._emit(state, "procured", actor_id, record_id, (actor_id, offer.supplier_id))
            return record_id
        if isinstance(action, CreateListing):
            _require(isinstance(actor, Seller), "FORBIDDEN")
            _require(_identifier(action.listing_id) and _identifier(action.product_id), "INVALID_ID")
            _require(action.listing_id not in state.listings, "LISTING_ID_CONFLICT")
            _require(action.product_id in state.products, "PRODUCT_NOT_FOUND")
            _require(_integer(action.unit_price_cents), "INVALID_PRICE")
            description = _text(action.description, 2000)
            inventory = state.inventory.get((actor_id, action.product_id))
            _require(inventory is not None and inventory.quantity > 0, "OUT_OF_STOCK")
            state.listings[action.listing_id] = Listing(action.listing_id, actor_id, action.product_id, action.unit_price_cents, description)
            self._emit(state, "listing_created", actor_id, action.listing_id)
            return action.listing_id
        if isinstance(action, UpdateListing):
            _require(isinstance(actor, Seller), "FORBIDDEN")
            _require(_identifier(action.listing_id), "INVALID_ID")
            listing = state.listings.get(action.listing_id)
            _require(listing is not None, "LISTING_NOT_FOUND")
            _require(listing.seller_id == actor_id, "FORBIDDEN")
            _require(any(v is not None for v in (action.unit_price_cents, action.description, action.active)), "EMPTY_UPDATE")
            changes = {}
            if action.unit_price_cents is not None:
                _require(_integer(action.unit_price_cents), "INVALID_PRICE")
                changes["unit_price_cents"] = action.unit_price_cents
            if action.description is not None:
                changes["description"] = _text(action.description, 2000)
            if action.active is not None:
                _require(type(action.active) is bool, "INVALID_STATUS")
                changes["active"] = action.active
            state.listings[listing.id] = replace(listing, **changes)
            self._emit(state, "listing_updated", actor_id, listing.id)
            return listing.id
        if isinstance(action, Purchase):
            _require(isinstance(actor, Buyer), "FORBIDDEN")
            _require(_identifier(action.listing_id), "INVALID_ID")
            _require(_integer(action.quantity, 1), "INVALID_QUANTITY")
            _require(_integer(action.expected_unit_price_cents), "INVALID_PRICE")
            listing = state.listings.get(action.listing_id)
            _require(listing is not None, "LISTING_NOT_FOUND")
            _require(listing.active, "LISTING_INACTIVE")
            _require(listing.unit_price_cents == action.expected_unit_price_cents, "PRICE_CHANGED")
            key = (listing.seller_id, listing.product_id)
            inventory = state.inventory.get(key)
            _require(inventory is not None and inventory.quantity >= action.quantity, "OUT_OF_STOCK")
            total = listing.unit_price_cents * action.quantity
            self._transfer(state, actor_id, listing.seller_id, total)
            state.inventory[key] = replace(inventory, quantity=inventory.quantity - action.quantity)
            order_id = self._id(state, "order")
            state.orders[order_id] = Order(order_id, actor_id, listing.seller_id, listing.id, listing.product_id, action.quantity, listing.unit_price_cents, total, state.step)
            self._emit(state, "purchased", actor_id, order_id, (actor_id, listing.seller_id))
            return order_id
        if isinstance(action, (SendPublic, SendPrivate)):
            _require(isinstance(actor, (Seller, Buyer)), "FORBIDDEN")
            text = _text(action.text, 500)
            conversation_id = None
            audience = None
            if isinstance(action, SendPublic):
                _require(_identifier(action.seller_id), "INVALID_ID")
                _require(isinstance(state.actors.get(action.seller_id), Seller), "SELLER_NOT_FOUND")
                _require(isinstance(actor, Buyer) or actor_id == action.seller_id, "FORBIDDEN")
                seller_id = action.seller_id
                channel = Channel.PUBLIC
            else:
                _require(_identifier(action.recipient_id), "INVALID_ID")
                recipient = state.actors.get(action.recipient_id)
                _require(recipient is not None, "RECIPIENT_NOT_FOUND")
                _require((isinstance(actor, Buyer) and isinstance(recipient, Seller)) or (isinstance(actor, Seller) and isinstance(recipient, Buyer)), "FORBIDDEN")
                buyer_id, seller_id = (actor_id, recipient.id) if isinstance(actor, Buyer) else (recipient.id, actor_id)
                key = (buyer_id, seller_id)
                if key not in state.conversations:
                    state.conversations[key] = Conversation(self._id(state, "conversation"), *key)
                conversation_id = state.conversations[key].id
                audience = key
                channel = Channel.PRIVATE
            message_id = self._id(state, "message")
            state.messages.append(Message(message_id, channel, actor_id, seller_id, text, state.step, conversation_id))
            self._emit(state, "message_sent", actor_id, message_id, audience)
            return message_id
        self._emit(state, "waited", actor_id, None, (actor_id,))
        return None
