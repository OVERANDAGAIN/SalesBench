"""Explicit recovery contract: validated canonical boundary transcript, not snapshot restore."""

from copy import deepcopy

from .codec import config_from_data, setup_from_data
from .drivers import DriverReply
from .journal import source_digest
from .protocol import ENGINE_RULES_VERSION, PROTOCOL_VERSION, RESOLVER_VERSION, Phase, RuntimeConfig
from .replay import ReplayMismatch, logical_records
from .scheduler import Runner


async def restore_committed(records: list[dict], drivers, *, runtime: RuntimeConfig = RuntimeConfig()) -> Runner:
    """Re-adjudicate a complete published prefix; bind future drivers only afterwards.

    Accepted endpoints: initial publication, Wave publication, Round close,
    completed, or recorded action/collection failure. No partial collection or
    uncommitted action suffix is accepted. Code/rules mismatches fail closed.
    """
    if len(records) < 2 or records[0].get("kind") != "manifest":
        raise ReplayMismatch("Missing committed manifest/publication")
    if any(r.get("seq") != i for i, r in enumerate(records)):
        raise ReplayMismatch("Non-contiguous transcript")
    manifest = records[0]
    if (manifest.get("protocol"), manifest.get("resolver"), manifest.get("engine_rules"), manifest.get("source_digest")) != (
        PROTOCOL_VERSION, RESOLVER_VERSION, ENGINE_RULES_VERSION, source_digest()
    ):
        raise ReplayMismatch("Code/rules mismatch; recover with the committed code version")
    last = records[-1]
    terminal = last.get("kind") == "aborted" or (last.get("kind") == "phase" and last.get("phase") == "completed")
    if last.get("kind") != "published" and not terminal:
        raise ReplayMismatch("Transcript is not a committed Runner boundary")
    replies = {}
    for row in records:
        if row["kind"] == "driver_reply":
            if row["opportunity_id"] in replies:
                raise ReplayMismatch("Duplicate opportunity")
            replies[row["opportunity_id"]] = DriverReply(**row["reply"])

    class RecordedDriver:
        def __init__(self, actor):
            self.actor = actor

        def configuration(self):
            return manifest["drivers"][self.actor]

        async def decide(self, observation):
            return replies.pop(observation.opportunity_id)

    if set(drivers) != set(manifest["drivers"]):
        raise ReplayMismatch("Recovery cannot change actor membership")
    runner = Runner(setup_from_data(manifest["setup"]), {a: RecordedDriver(a) for a in drivers},
                    config=config_from_data(manifest["market_config"]), runtime=runtime)
    runner._executor._replay_faults = {r["action_id"]: r["code"] for r in records if r["kind"] == "execution_fault"}
    boundaries = sum(r["kind"] == "published" for r in records) - 1
    for _ in range(boundaries):
        if runner.phase in (Phase.COMPLETED, Phase.FAILED):
            raise ReplayMismatch("Unexpected terminal boundary")
        await runner.advance_boundary()
    if last.get("kind") == "aborted" and runner.phase != Phase.FAILED:
        await runner.advance_boundary()
    if replies or logical_records(runner.journal.records) != logical_records(records):
        raise ReplayMismatch("Committed transcript diverges from Runner replay")
    # Preserve original timestamps/raw audit metadata in the durable prefix.
    runner.journal._records = deepcopy(records)
    runner._drivers = dict(drivers)
    runner._executor._replay_faults = {}
    return runner
