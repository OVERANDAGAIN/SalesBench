"""Re-adjudicate recorded actions from original setup without calling any model."""

from .codec import config_from_data, setup_from_data
from .drivers import DriverReply
from .journal import source_digest
from .protocol import ENGINE_RULES_VERSION, PROTOCOL_VERSION, RESOLVER_VERSION, RuntimeConfig
from .scheduler import Runner


class ReplayMismatch(ValueError):
    pass


def logical_records(records):
    # Wall time and provider transport diagnostics cannot affect the market.
    return [{k: v for k, v in row.items() if k not in ("seq", "recorded_at")}
            for row in records if row["kind"] not in ("manifest", "driver_reply")]


async def replay(records: list[dict]) -> Runner:
    if not records or records[0].get("kind") != "manifest":
        raise ReplayMismatch("Missing manifest")
    manifest = records[0]
    if (manifest["protocol"], manifest["resolver"], manifest["engine_rules"], manifest["source_digest"]) != (
        PROTOCOL_VERSION, RESOLVER_VERSION, ENGINE_RULES_VERSION, source_digest()
    ):
        raise ReplayMismatch("Protocol/rules/source version mismatch; use the recorded code revision")
    replies = {}
    for record in records:
        if record["kind"] == "driver_reply":
            key = record["opportunity_id"]
            if key in replies:
                raise ReplayMismatch("Duplicate recorded opportunity")
            replies[key] = DriverReply(**record["reply"])

    class RecordedDriver:
        def __init__(self, actor):
            self.actor = actor

        def configuration(self):
            return manifest["drivers"][self.actor]

        async def decide(self, observation):
            if observation.opportunity_id not in replies:
                raise ReplayMismatch("Missing recorded action batch")
            return replies.pop(observation.opportunity_id)

    runner = Runner(setup_from_data(manifest["setup"]),
                    {actor: RecordedDriver(actor) for actor in manifest["drivers"]},
                    config=config_from_data(manifest["market_config"]), runtime=RuntimeConfig())
    runner._executor._replay_faults = {r["action_id"]: r["code"] for r in records if r["kind"] == "execution_fault"}
    await runner.run()
    if replies or logical_records(records) != logical_records(runner.journal.records):
        raise ReplayMismatch("Recorded trace diverges from re-adjudicated observations/actions/results/state")
    return runner
