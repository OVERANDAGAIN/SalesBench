"""Versioned benchmark protocol, separate from model transport settings."""

from dataclasses import dataclass
from enum import StrEnum
import math

from ..models import ListingView, MarketTime, Message, Observation, Result, Seller

PROTOCOL_VERSION = "sb-wave-v1"
RESOLVER_VERSION = "sha256-actor-v1"
ENGINE_RULES_VERSION = "sb-engine-revisions-v1"


class Role(StrEnum):
    SELLER = "seller"
    BUYER = "buyer"


class Phase(StrEnum):
    CREATED = "created"
    COLLECTING = "collecting"
    EXECUTING = "executing"
    PUBLISHING = "publishing"
    CLOSING_ROUND = "closing_round"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class WaveDefinition:
    name: str
    role: Role
    allowed_actions: tuple[str, ...]
    max_actions: int = 3
    max_messages: int = 2
    max_purchases: int = 0


PROCUREMENT = WaveDefinition("ROUND_PROCUREMENT", Role.SELLER, ("procure", "wait"), 1, 0)
SELLER_STRATEGY = WaveDefinition(
    "SELLER_STRATEGY", Role.SELLER,
    ("create_listing", "update_listing", "send_public", "send_private", "wait"),
)
BUYER_ACTION = WaveDefinition(
    "BUYER_ACTION", Role.BUYER, ("send_public", "send_private", "purchase", "wait"),
    max_purchases=1,
)


@dataclass(frozen=True)
class MarketConfig:
    design_id: str = "salesbench-wave-demo"
    resolution_seed: int = 7
    max_rounds: int = 2
    ticks_per_round: int = 3
    waves: tuple[WaveDefinition, ...] = (SELLER_STRATEGY, BUYER_ACTION)

    def __post_init__(self):
        if not isinstance(self.design_id, str) or not self.design_id.strip():
            raise ValueError("A stable market design_id is required")
        if type(self.resolution_seed) is not int:
            raise ValueError("resolution_seed must be an integer")
        if any(type(n) is not int or n < 1 for n in (self.max_rounds, self.ticks_per_round)):
            raise ValueError("Round and tick limits must be positive integers")
        # Dispatch is data-driven; new Wave kinds require explicit protocol work.
        # Do not accidentally advertise unimplemented conversation micro-waves.
        if type(self.waves) is not tuple or len(self.waves) != 2:
            raise ValueError("V1 requires SELLER_STRATEGY then BUYER_ACTION")
        for actual, supported in zip(self.waves, (SELLER_STRATEGY, BUYER_ACTION)):
            if (actual.name, actual.role, actual.allowed_actions) != (supported.name, supported.role, supported.allowed_actions):
                raise ValueError("Unsupported V1 Wave definition")
            if any(type(n) is not int or n < 0 for n in (actual.max_actions, actual.max_messages, actual.max_purchases)):
                raise ValueError("Invalid Wave budget")
            if actual.max_actions < 1 or actual.max_messages > actual.max_actions or actual.max_purchases != supported.max_purchases:
                raise ValueError("Invalid V1 action/message/purchase budget")


@dataclass(frozen=True)
class RuntimeConfig:
    concurrency: int = 8
    timeout_seconds: float = 30.0

    def __post_init__(self):
        if type(self.concurrency) is not int or self.concurrency < 1:
            raise ValueError("concurrency must be a positive integer")
        if type(self.timeout_seconds) not in (int, float) or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")


@dataclass(frozen=True)
class WaveContext:
    round: int
    tick: int
    wave: str

    @property
    def id(self) -> str:
        return f"r{self.round}:t{self.tick}:{self.wave}"


@dataclass(frozen=True)
class Boundary:
    """Trusted-host scheduling boundary, not an actor action or new Wave kind."""
    context: WaveContext
    wave: WaveDefinition | None  # None means the existing Round close.


@dataclass(frozen=True)
class ActionOutcome:
    action_id: str
    status: str
    reason: str | None = None
    result: Result | None = None


@dataclass(frozen=True)
class PublicSnapshot:
    version: int
    time: MarketTime
    sellers: tuple[Seller, ...]
    listings: tuple[ListingView, ...]
    messages: tuple[Message, ...]


@dataclass(frozen=True)
class AuthorizedState:
    public: PublicSnapshot
    own: Observation
    inbox: Observation
    previous_outcomes: tuple[ActionOutcome, ...]


@dataclass(frozen=True)
class DecisionObservation:
    context: WaveContext
    opportunity_id: str
    wave: WaveDefinition
    state: AuthorizedState
    procurement: Observation | None = None

    @property
    def actor_id(self) -> str:
        return self.state.own.actor.id
