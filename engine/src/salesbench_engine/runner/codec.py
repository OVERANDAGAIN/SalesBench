"""Strict untrusted action parsing and stable, language-neutral journal encoding."""

from dataclasses import asdict, fields, is_dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import get_args, get_origin, get_type_hints
import types

from .. import actions as a
from .. import models as m
from .protocol import MarketConfig, Role, WaveDefinition

ACTION_TYPES = {
    "procure": a.Procure, "create_listing": a.CreateListing,
    "update_listing": a.UpdateListing, "send_public": a.SendPublic,
    "send_private": a.SendPrivate, "purchase": a.Purchase, "wait": a.Wait,
}


def data(value):
    if is_dataclass(value):
        return data(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: data(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [data(v) for v in value]
    return value


def canonical(value) -> str:
    return json.dumps(data(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def action_data(action: a.Action) -> dict:
    name = next(name for name, cls in ACTION_TYPES.items() if type(action) is cls)
    return {"type": name, **data(action)}


def encode_batch(actions) -> str:
    return canonical({"actions": [action_data(action) for action in actions]})


class InvalidBatch(ValueError):
    """Protocol rejection; distinct from a legal action failing in the Engine."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidBatch("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _matches(value, annotation):
    if get_origin(annotation) is types.UnionType:
        return any(_matches(value, part) for part in get_args(annotation))
    return type(value) is annotation


def parse_batch(raw: str, wave: WaveDefinition, actor_id: str) -> tuple[a.Action, ...]:
    if type(raw) is not str or len(raw) > 65536:
        raise InvalidBatch("OUTPUT_SIZE_LIMIT")
    try:
        parsed = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as error:
        if isinstance(error, InvalidBatch):
            raise
        raise InvalidBatch("INVALID_JSON") from None
    if type(parsed) is not dict or set(parsed) != {"actions"} or type(parsed["actions"]) is not list:
        raise InvalidBatch("INVALID_ENVELOPE")
    rows = parsed["actions"]
    if not 1 <= len(rows) <= wave.max_actions:
        raise InvalidBatch("ACTION_BUDGET")
    result = []
    for row in rows:
        if type(row) is not dict or type(row.get("type")) is not str or row["type"] not in wave.allowed_actions:
            raise InvalidBatch("ACTION_NOT_ALLOWED")
        cls = ACTION_TYPES[row["type"]]
        payload = {k: v for k, v in row.items() if k != "type"}
        hints = get_type_hints(cls)
        if any(k not in hints or not _matches(v, hints[k]) for k, v in payload.items()):
            raise InvalidBatch("INVALID_FIELDS")
        try:
            action = cls(**payload)
        except TypeError:
            raise InvalidBatch("MISSING_FIELDS") from None
        # Namespace prevents actor commit order deciding listing-ID ownership.
        if isinstance(action, a.CreateListing) and (
            not action.listing_id.startswith(actor_id + "/") or not action.listing_id[len(actor_id) + 1:].strip()
            or "/" in action.listing_id[len(actor_id) + 1:]
        ):
            raise InvalidBatch("LISTING_NAMESPACE")
        result.append(action)
    if any(isinstance(x, a.Wait) for x in result) and len(result) != 1:
        raise InvalidBatch("WAIT_MUST_BE_ALONE")
    if sum(isinstance(x, (a.SendPublic, a.SendPrivate)) for x in result) > wave.max_messages:
        raise InvalidBatch("MESSAGE_BUDGET")
    purchases = [i for i, x in enumerate(result) if isinstance(x, a.Purchase)]
    if len(purchases) > wave.max_purchases or (purchases and purchases[-1] != len(result) - 1):
        raise InvalidBatch("PURCHASE_MUST_BE_SINGLE_AND_LAST")
    return tuple(result)


def action_schema(wave: WaveDefinition) -> dict:
    """Provider-independent schema description included in every model request."""
    return {name: {f.name: str(get_type_hints(ACTION_TYPES[name])[f.name]) for f in fields(ACTION_TYPES[name])} for name in wave.allowed_actions}


def setup_from_data(value: dict) -> m.MarketSetup:
    rows = {name: tuple(cls(**v) for v in value[name]) for name, cls in (
        ("suppliers", m.Supplier), ("sellers", m.Seller), ("buyers", m.Buyer),
        ("products", m.Product), ("offers", m.SupplierOffer), ("accounts", m.Account),
    )}
    return m.MarketSetup(m.Experiment(**value["experiment"]), **rows)


def config_from_data(value: dict) -> MarketConfig:
    return MarketConfig(**{**value, "waves": tuple(WaveDefinition(
        **{**w, "role": Role(w["role"]), "allowed_actions": tuple(w["allowed_actions"])}
    ) for w in value["waves"])})
