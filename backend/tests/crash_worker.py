"""Fault-injection subprocess, not an application endpoint."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.persistence import database
from app.service import MarketService


def fault(operation, point):
    if operation == "boundary" and point == sys.argv[2]:
        os._exit(72)


engine, sessions = database(os.environ["SALESBENCH_DATABASE_URL"])
MarketService(sessions, fault_hook=fault).run_ready(sys.argv[1])
raise SystemExit("Expected fault did not occur")
