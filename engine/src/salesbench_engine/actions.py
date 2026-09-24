"""Actor-free intentions: the trusted host binds identity when calling execute."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Procure:
    offer_id: str
    quantity: int
    expected_unit_cost_cents: int


@dataclass(frozen=True)
class CreateListing:
    listing_id: str
    product_id: str
    unit_price_cents: int
    description: str


@dataclass(frozen=True)
class UpdateListing:
    listing_id: str
    unit_price_cents: int | None = None
    description: str | None = None
    active: bool | None = None


@dataclass(frozen=True)
class SendPublic:
    seller_id: str
    text: str


@dataclass(frozen=True)
class SendPrivate:
    recipient_id: str
    text: str


@dataclass(frozen=True)
class Purchase:
    listing_id: str
    quantity: int
    expected_unit_price_cents: int
    expected_offer_revision: int


@dataclass(frozen=True)
class Wait:
    """An explicit policy decision to abstain. Does not advance market time."""


type Action = Procure | CreateListing | UpdateListing | SendPublic | SendPrivate | Purchase | Wait
