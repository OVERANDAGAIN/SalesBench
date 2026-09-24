"""Platform envelopes shared by HTTP and in-process application callers."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: Identifier
    setup: dict
    market_config: dict = Field(default_factory=dict)
    metrics_policy: dict = Field(default_factory=dict)


class SubmitBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
    observation_version: Annotated[StrictInt, Field(ge=0)]
    opportunity_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    actions: list[dict]


class RotateBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: Annotated[str, Field(min_length=1, max_length=128)]


def postgres_json(value):
    """Reject text PostgreSQL JSONB cannot store; do not silently change actions."""
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("NUL is not supported in PostgreSQL JSONB text")
        value.encode("utf-8")
    elif isinstance(value, dict):
        for key, item in value.items():
            postgres_json(key)
            postgres_json(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            postgres_json(item)
