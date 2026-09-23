"""Policies receive only immutable observations and return actor-free intentions."""

from collections import deque
from dataclasses import dataclass
from typing import Protocol

from .actions import Action, Wait
from .models import Observation


class Policy(Protocol):
    """Shared Buyer/Seller/Supplier contract; role is in observation.actor."""

    def decide(self, observation: Observation) -> Action: ...


@dataclass(frozen=True)
class ScriptedDecision:
    at_step: int
    action: Action


class ScriptedPolicy:
    """TEST policy: one queued intention per call, wait until its engine step.

    A host controls turn order and calls execute with its bound actor ID.
    Decisions are consumed when proposed, even when the engine rejects them.
    This is not a retry strategy, scheduler or consumer model.
    """

    def __init__(self, decisions: tuple[ScriptedDecision, ...]):
        steps = [d.at_step for d in decisions]
        if any(type(s) is not int or s < 0 for s in steps) or steps != sorted(steps):
            raise ValueError("Scripted steps must be nonnegative integers in order")
        self._decisions = deque(decisions)

    def decide(self, observation: Observation) -> Action:
        if not self._decisions or self._decisions[0].at_step > observation.time.step:
            return Wait()
        return self._decisions.popleft().action
