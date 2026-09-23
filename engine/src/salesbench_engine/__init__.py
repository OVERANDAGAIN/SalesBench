"""SalesBench's UI-independent experiment engine; no platform imports."""

from .environment import Engine, ObservationError
from .models import Experiment, MarketSetup

__all__ = ["Engine", "Experiment", "MarketSetup", "ObservationError"]
