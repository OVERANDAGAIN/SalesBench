"""Immutable domain records and actor-visible snapshots. Money is integer cents."""

from dataclasses import dataclass
from enum import StrEnum


class Channel(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class View(StrEnum):
    MARKET = "market"
    PRODUCT = "product"
    LEADERBOARD = "leaderboard"
    SUPPLIERS = "suppliers"
    SELF = "self"
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass(frozen=True)
class Experiment:
    id: str
    seed: int = 0
    steps_per_demo_day: int | None = None


@dataclass(frozen=True)
class MarketTime:
    step: int = 0
    demo_day: int | None = None


@dataclass(frozen=True)
class Supplier:
    id: str
    name: str


@dataclass(frozen=True)
class Seller:
    id: str
    name: str


@dataclass(frozen=True)
class Buyer:
    id: str
    name: str


type Actor = Supplier | Seller | Buyer


@dataclass(frozen=True)
class Product:
    id: str
    name: str


@dataclass(frozen=True)
class SupplierOffer:
    id: str
    supplier_id: str
    product_id: str
    unit_cost_cents: int
    available_quantity: int
    active: bool = True


@dataclass(frozen=True)
class Inventory:
    seller_id: str
    product_id: str
    quantity: int


@dataclass(frozen=True)
class Listing:
    id: str
    seller_id: str
    product_id: str
    unit_price_cents: int
    description: str
    active: bool = True


@dataclass(frozen=True)
class Account:
    actor_id: str
    balance_cents: int


@dataclass(frozen=True)
class Conversation:
    id: str
    buyer_id: str
    seller_id: str


@dataclass(frozen=True)
class Message:
    id: str
    channel: Channel
    author_id: str
    seller_id: str
    text: str
    step: int
    conversation_id: str | None = None


@dataclass(frozen=True)
class Order:
    id: str
    buyer_id: str
    seller_id: str
    listing_id: str
    product_id: str
    quantity: int
    unit_price_cents: int
    total_cents: int
    step: int
    settlement: str = "test_immediate"


@dataclass(frozen=True)
class Procurement:
    id: str
    seller_id: str
    supplier_id: str
    offer_id: str
    product_id: str
    quantity: int
    unit_cost_cents: int
    total_cents: int
    step: int


@dataclass(frozen=True)
class Event:
    id: str
    kind: str
    step: int
    actor_id: str | None
    entity_id: str | None
    # None means public. A tuple restricts delivery to these participants.
    audience: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Result:
    ok: bool
    code: str
    step: int
    entity_id: str | None = None
    events: tuple[Event, ...] = ()


@dataclass(frozen=True)
class ListingView:
    listing: Listing
    product: Product
    seller: Seller
    available_quantity: int


@dataclass(frozen=True)
class RankingEntry:
    seller_id: str
    rank: int
    gross_sales_cents: int
    units_sold: int


@dataclass(frozen=True)
class Observation:
    experiment_id: str
    time: MarketTime
    actor: Actor
    account: Account
    view: View
    listings: tuple[ListingView, ...] = ()
    suppliers: tuple[Supplier, ...] = ()
    offers: tuple[SupplierOffer, ...] = ()
    products: tuple[Product, ...] = ()
    inventory: tuple[Inventory, ...] = ()
    orders: tuple[Order, ...] = ()
    procurements: tuple[Procurement, ...] = ()
    conversations: tuple[Conversation, ...] = ()
    messages: tuple[Message, ...] = ()
    ranking: tuple[RankingEntry, ...] = ()
    ranking_rule: str | None = None
    events: tuple[Event, ...] = ()


@dataclass(frozen=True)
class MarketSetup:
    experiment: Experiment
    suppliers: tuple[Supplier, ...]
    sellers: tuple[Seller, ...]
    buyers: tuple[Buyer, ...]
    products: tuple[Product, ...]
    offers: tuple[SupplierOffer, ...]
    accounts: tuple[Account, ...]


@dataclass(frozen=True)
class MarketSnapshot:
    """Trusted host/test export, NEVER a participant observation or HTTP DTO."""

    setup: MarketSetup
    time: MarketTime
    accounts: tuple[Account, ...]
    offers: tuple[SupplierOffer, ...]
    inventory: tuple[Inventory, ...]
    listings: tuple[Listing, ...]
    orders: tuple[Order, ...]
    procurements: tuple[Procurement, ...]
    conversations: tuple[Conversation, ...]
    messages: tuple[Message, ...]
    events: tuple[Event, ...]
    counters: tuple[tuple[str, int], ...]
