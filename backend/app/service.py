"""Shared application boundary. PostgreSQL commits candidates computed ONLY by Runner.

No resident Engine is authoritative. Every resolver reconstructs a disposable
candidate from a verified committed transcript. HTTP and future Agent adapters
use these same methods; neither writes domain tables or calls Engine directly.
"""

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import secrets
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from salesbench_engine.runner import MarketConfig, Phase, Runner
from salesbench_engine.runner.codec import canonical, config_from_data, data, digest, setup_from_data
from salesbench_engine.runner.drivers import DriverReply
from salesbench_engine.runner.journal import source_digest
from salesbench_engine.runner.recovery import restore_committed
from salesbench_engine.runner.replay import ReplayMismatch

from .persistence import (
    ActionReceipt, ActorBinding, ActorProjection, BatchReceipt, JournalEntry,
    MarketSession, OutboxNotice, Publication, Resolution, SemanticEvent, MetricSnapshot, LeaderboardSnapshot,
)
from .metrics import new_policy
from .contracts import CreateSession, SubmitBatch, postgres_json

API_SCHEMA = "sb-platform-v1"


class ServiceError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code = code
        self.status = status
        super().__init__(code)


class CommitUnknown(ServiceError):
    def __init__(self):
        super().__init__("COMMIT_UNKNOWN", 503)


def token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


class SubmissionDriver:
    """Transport adapter for already-collected intents, not a Human/LLM policy."""
    def __init__(self, replies=None):
        self.replies = replies or {}

    def configuration(self):
        return {"driver": "persisted_batch"}

    async def decide(self, observation):
        return DriverReply(raw_output=self.replies[observation.opportunity_id], provider="platform", model="submitted_intent")


@dataclass(frozen=True)
class Claim:
    session_id: str
    fence: int
    version: int
    transcript_digest: str
    records: list[dict]
    batches: list[dict]


@dataclass(frozen=True)
class Candidate:
    claim: Claim
    runner: Runner


class MarketService:
    def __init__(self, sessions, *, fault_hook=None):
        self.sessions = sessions
        self.code_digest = source_digest()
        # Trusted test injection only; never exposed in requests/configuration.
        self._fault_hook = fault_hook or (lambda operation, point: None)

    def _commit(self, db, operation):
        try:
            self._fault_hook(operation, "before_commit")
            db.commit()
            self._fault_hook(operation, "after_commit")
        except Exception:
            try:
                db.rollback()
            except SQLAlchemyError:
                pass
            # A lost COMMIT acknowledgement is indistinguishable from rollback.
            # Never reuse a candidate as authoritative or mint another request ID.
            raise CommitUnknown() from None

    @staticmethod
    def _locked(db, session_id):
        row = db.scalar(select(MarketSession).where(MarketSession.id == session_id).with_for_update())
        if row is None:
            raise ServiceError("SESSION_NOT_FOUND", 404)
        return row

    @staticmethod
    def _binding(db, session_id, token):
        binding = db.scalar(select(ActorBinding).where(ActorBinding.session_id == session_id,
                                                      ActorBinding.token_digest == token_digest(token)))
        if binding is None:
            raise ServiceError("INVALID_ACTOR_BINDING", 403)
        return binding

    @staticmethod
    def _runtime(runner):
        boundary = runner.next_boundary
        status = str(runner.phase) if boundary is None else ("awaiting_batches" if boundary.wave else "round_close_pending")
        return {"status": status, "runner_phase": str(runner.phase), "published_version": runner.published_version,
                "engine_step": runner.economic_state().time.step,
                "next_boundary": data(boundary)}

    @classmethod
    def _projections(cls, runner):
        pending = runner.pending_observations()
        setup = runner.economic_state().setup
        return {actor.id: {"state": data(runner.observe(actor.id)), "opportunity": data(pending.get(actor.id))}
                for actor in (*setup.sellers, *setup.buyers)}

    def create(self, session_id: str, setup_payload: dict, market_config: dict, metrics_policy=None):
        try:
            CreateSession.model_validate({"session_id": session_id, "setup": setup_payload, "market_config": market_config})
            postgres_json(setup_payload)
            postgres_json(market_config)
            if set(setup_payload) != {"experiment", "suppliers", "sellers", "buyers", "products", "offers", "accounts"}:
                raise ValueError("Unknown setup fields")
            setup = setup_from_data(setup_payload)
            config = config_from_data({**data(MarketConfig()), **market_config})
            metric_policy = new_policy(metrics_policy)
            actor_ids = [a.id for a in (*setup.sellers, *setup.buyers)]
            if any(len(actor) > 128 for actor in actor_ids):
                raise ValueError("Actor ID storage limit")
            runner = Runner(setup, {actor: SubmissionDriver() for actor in actor_ids}, config=config)
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise ServiceError("INVALID_MARKET_SETUP", 422) from None
        fingerprint = digest({"setup": setup, "config": config, "metrics_policy": metric_policy})
        records = runner.journal.records
        tokens = {actor: secrets.token_urlsafe(32) for actor in actor_ids}
        with self.sessions() as db:
            # Serialize same-ID creation without locking unrelated sessions.
            from sqlalchemy import text
            create_lock = int(sha256(session_id.encode()).hexdigest()[:16], 16) - 2**63
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": create_lock})
            existing = db.get(MarketSession, session_id)
            if existing:
                expected_fingerprint = fingerprint if existing.metrics_policy is not None else digest({"setup": setup, "config": config})
                if existing.creation_fingerprint != expected_fingerprint or (existing.metrics_policy is None and metrics_policy):
                    raise ServiceError("SESSION_ID_CONFLICT")
                return {"session_id": session_id, "runtime": existing.runtime, "actor_tokens": None, "replayed": True}
            runtime = self._runtime(runner)
            db.add(MarketSession(id=session_id, creation_fingerprint=fingerprint, setup=data(setup), market_config=data(config),
                                 source_digest=self.code_digest, status=runtime["status"], published_version=0, fence=0,
                                 transcript_count=len(records), transcript_digest=digest(records),
                                 state_digest=digest(runner.economic_state()), runtime=runtime, next_boundary=data(runner.next_boundary), metrics_policy=metric_policy))
            db.flush()
            for actor in (*setup.sellers, *setup.buyers):
                db.add(ActorBinding(session_id=session_id, actor_id=actor.id,
                                    role="seller" if actor.id in {s.id for s in setup.sellers} else "buyer",
                                    token_digest=token_digest(tokens[actor.id])))
            db.flush()
            for actor, projection in self._projections(runner).items():
                db.add(ActorProjection(session_id=session_id, actor_id=actor, version=0, payload=projection))
            self._append_records(db, session_id, records)
            self._commit(db, "create")
        self._ensure_metrics(session_id)
        return {"session_id": session_id, "runtime": runtime, "actor_tokens": tokens, "replayed": False}

    def rotate_binding(self, session_id, actor_id):
        token = secrets.token_urlsafe(32)
        with self.sessions() as db:
            self._locked(db, session_id)
            row = db.get(ActorBinding, (session_id, actor_id))
            if row is None:
                raise ServiceError("ACTOR_NOT_FOUND", 404)
            row.token_digest = token_digest(token)
            self._commit(db, "binding")
        return {"session_id": session_id, "actor_id": actor_id, "actor_token": token}

    def observe(self, session_id, token):
        with self.sessions() as db:
            self._binding(db, session_id, token)  # Authenticate before materialization.
        # An economic COMMIT may land between ensure and the MVCC read. Retry
        # that exact missing derived boundary; never pair it with an older board.
        for attempt in range(3):
            self._ensure_metrics(session_id)
            try:
                return self._observe_committed(session_id, token)
            except ServiceError as error:
                if error.code != "METRICS_NOT_READY" or attempt == 2:
                    raise

    def _observe_committed(self, session_id, token):
        with self.sessions() as db:
            # One SQL statement gives a single MVCC view of projection AND runtime.
            row = db.execute(select(ActorProjection, MarketSession.runtime, MarketSession.metrics_policy,
                                    MetricSnapshot, LeaderboardSnapshot).join(
                ActorBinding, (ActorBinding.session_id == ActorProjection.session_id) & (ActorBinding.actor_id == ActorProjection.actor_id)
            ).join(MarketSession, MarketSession.id == ActorProjection.session_id).outerjoin(
                MetricSnapshot, (MetricSnapshot.session_id == MarketSession.id) & (MetricSnapshot.transcript_count == MarketSession.transcript_count)
            ).outerjoin(LeaderboardSnapshot, (LeaderboardSnapshot.session_id == MetricSnapshot.session_id) &
                        (LeaderboardSnapshot.source_publication_version == MetricSnapshot.leaderboard_source_version)).where(
                ActorProjection.session_id == session_id, ActorBinding.token_digest == token_digest(token)
            )).first()
            if row is None:
                raise ServiceError("INVALID_ACTOR_BINDING", 403)
            projection, runtime, policy, metrics, board = row
            public_board = None
            if policy is not None:
                from .metric_store import MetricStore
                if MetricStore.checked(metrics)["consistency_errors"]:
                    raise ServiceError("METRICS_INCONSISTENT", 503)
                public_board = MetricStore.checked(board)
            return {"schema_version": API_SCHEMA, "session_id": session_id, "actor_id": projection.actor_id,
                    "published_version": projection.version, **deepcopy(projection.payload), "runtime": deepcopy(runtime),
                    "leaderboard": public_board}

    def runtime(self, session_id, token):
        return self.observe(session_id, token)["runtime"]

    def receipt(self, session_id, token, request_id):
        with self.sessions() as db:
            actor = self._binding(db, session_id, token).actor_id
            row = db.get(BatchReceipt, (session_id, actor, request_id))
            if row is None:
                raise ServiceError("RECEIPT_NOT_FOUND", 404)
            return {**deepcopy(row.receipt), "replayed": False}

    def receipts(self, session_id, token):
        """Own recent receipts for reconnecting clients; never another actor's intents."""
        with self.sessions() as db:
            actor = self._binding(db, session_id, token).actor_id
            rows = db.scalars(select(BatchReceipt).where(
                BatchReceipt.session_id == session_id, BatchReceipt.actor_id == actor
            ).order_by((BatchReceipt.status == "pending").desc(), BatchReceipt.created_at.desc(), BatchReceipt.request_id).limit(50))
            return {"receipts": [deepcopy(row.receipt) for row in rows]}

    def notifications(self, session_id, token, after_version):
        with self.sessions() as db:
            self._binding(db, session_id, token)
            notices = db.scalars(select(OutboxNotice).where(OutboxNotice.session_id == session_id,
                                OutboxNotice.version > after_version).order_by(OutboxNotice.version).limit(100)).all()
            return {"notices": [deepcopy(n.payload) for n in notices]}

    def submit(self, session_id, token, request: dict):
        try:
            request = SubmitBatch.model_validate(request).model_dump()
            postgres_json(request)
            encoded = canonical(request)
        except (ValueError, TypeError, RecursionError):
            raise ServiceError("INVALID_REQUEST_ENVELOPE", 422) from None
        # Transport size limit, not a new economic/action budget.
        if len(encoded.encode("utf-8")) > 65536:
            raise ServiceError("REQUEST_TOO_LARGE", 413)
        fingerprint = digest(request)
        with self.sessions() as db:
            session = self._locked(db, session_id)
            actor = self._binding(db, session_id, token).actor_id
            key = (session_id, actor, request["request_id"])
            previous = db.get(BatchReceipt, key)
            if previous:
                if previous.fingerprint != fingerprint:
                    raise ServiceError("ACTION_ID_CONFLICT")
                return {**deepcopy(previous.receipt), "replayed": True}
            projection = db.get(ActorProjection, (session_id, actor))
            opportunity = projection.payload["opportunity"]
            code = None
            if request["observation_version"] != session.published_version:
                code = "STALE_OBSERVATION"
            elif session.status in ("failed", "completed"):
                code = "SESSION_TERMINAL"
            elif opportunity is None or request["opportunity_id"] != opportunity["opportunity_id"]:
                code = "OPPORTUNITY_NOT_CURRENT"
            elif db.scalar(select(BatchReceipt.request_id).where(BatchReceipt.session_id == session_id,
                            BatchReceipt.actor_id == actor, BatchReceipt.opportunity_id == request["opportunity_id"])):
                code = "OPPORTUNITY_ALREADY_SUBMITTED"
            status = "rejected" if code else "pending"
            receipt = {"schema_version": API_SCHEMA, "session_id": session_id, "actor_id": actor,
                       "request_id": request["request_id"], "opportunity_id": request["opportunity_id"],
                       "status": status, "code": code, "submitted_version": request["observation_version"],
                       "published_version": session.published_version, "outcomes": []}
            db.add(BatchReceipt(session_id=session_id, actor_id=actor, request_id=request["request_id"], fingerprint=fingerprint,
                                request=deepcopy(request), opportunity_id=request["opportunity_id"] if code is None else None,
                                submitted_version=request["observation_version"], status=status, receipt=receipt))
            self._commit(db, "submit")
        return {**receipt, "replayed": False}

    @staticmethod
    def _load_records(db, row):
        records = list(db.scalars(select(JournalEntry.payload).where(JournalEntry.session_id == row.id).order_by(JournalEntry.seq)))
        if len(records) != row.transcript_count or digest(records) != row.transcript_digest:
            raise ServiceError("TRANSCRIPT_INTEGRITY_ERROR", 503)
        return deepcopy(records)

    def claim(self, session_id) -> Claim | None:
        with self.sessions() as db:
            row = self._locked(db, session_id)
            if row.status in ("completed", "failed"):
                return None
            if row.source_digest != self.code_digest:
                raise ServiceError("RECOVERY_CODE_MISMATCH", 503)
            projections = db.scalars(select(ActorProjection).where(ActorProjection.session_id == session_id)).all()
            expected = {p.actor_id: p.payload["opportunity"]["opportunity_id"] for p in projections if p.payload["opportunity"]}
            pending = db.scalars(select(BatchReceipt).where(BatchReceipt.session_id == session_id, BatchReceipt.status == "pending")).all()
            batches = [b for b in pending if expected.get(b.actor_id) == b.opportunity_id]
            if row.next_boundary["wave"] is not None and len(batches) != len(expected):
                return None
            records = self._load_records(db, row)
            row.fence += 1
            claim = Claim(session_id, row.fence, row.published_version, row.transcript_digest, records,
                          [{"actor_id": b.actor_id, "request_id": b.request_id, "request": deepcopy(b.request),
                            "opportunity_id": b.opportunity_id} for b in batches])
            self._commit(db, "claim")
            return claim

    def compute(self, claim: Claim) -> Candidate:
        replies = {b["opportunity_id"]: canonical({"actions": b["request"]["actions"]}) for b in claim.batches}
        drivers = {actor: SubmissionDriver(replies) for actor in claim.records[0]["drivers"]}

        async def calculate():
            runner = await restore_committed(claim.records, drivers)
            if runner.published_version != claim.version:
                raise ReplayMismatch("Committed version mismatch")
            expected = {a: o.opportunity_id for a, o in runner.pending_observations().items()}
            supplied = {b["actor_id"]: b["opportunity_id"] for b in claim.batches}
            if supplied != expected:
                raise ReplayMismatch("Persisted opportunity collection differs from committed Runner")
            await runner.advance_boundary()
            if runner.phase == Phase.FAILED:
                # Persist only failures supported by the explicit restore contract.
                # An unrecordable implementation bug must not poison the last good boundary.
                await restore_committed(runner.journal.records, drivers)
            return runner

        try:
            return Candidate(claim, asyncio.run(calculate()))
        except ReplayMismatch:
            raise ServiceError("RECOVERY_TRACE_MISMATCH", 503) from None

    @staticmethod
    def _append_records(db, session_id, records):
        for record in records:
            db.add(JournalEntry(session_id=session_id, seq=record["seq"], payload=deepcopy(record)))
            kind = record["kind"]
            if kind == "published":
                db.add(Publication(session_id=session_id, version=record["version"], public=record["public"],
                                   context=record["context"], state_digest=record["state_digest"]))
                db.add(OutboxNotice(session_id=session_id, version=record["version"], payload={
                    "session_id": session_id, "published_version": record["version"], "kind": "observation_invalidated"}))
            if kind == "resolution":
                c = record["context"]
                db.add(Resolution(session_id=session_id, context_key=f"r{c['round']}:t{c['tick']}:{c['wave']}",
                                  purpose=record["purpose"], payload=deepcopy(record)))
            if kind in ("action_result", "round_closed"):
                for event in record["result"]["events"]:
                    db.add(SemanticEvent(session_id=session_id, event_id=event["id"], payload=deepcopy(event)))

    @staticmethod
    def _settle_batches(db, candidate, delta):
        claim, runner = candidate.claim, candidate.runner
        results = {r["actor_id"]: r["outcomes"] for r in delta if r["kind"] == "opportunity_result"}
        admissions = {r["actor_id"]: r for r in delta if r["kind"] == "admission"}
        action_results = {r["action_id"]: r["result"] for r in delta if r["kind"] == "action_result"}
        skips = {r["outcome"]["action_id"]: r["outcome"] for r in delta if r["kind"] == "skipped"}
        for batch in claim.batches:
            actor = batch["actor_id"]
            row = db.get(BatchReceipt, (claim.session_id, actor, batch["request_id"]))
            outcomes = results.get(actor, [])
            aborted = runner.phase == Phase.FAILED
            succeeded = bool(outcomes) and all(o["status"] == "succeeded" for o in outcomes)
            status = "aborted" if aborted else ("succeeded" if succeeded else "failed")
            row.status = status
            row.receipt = {**row.receipt, "status": status, "code": "SESSION_FAILED" if aborted else None,
                           "published_version": runner.published_version, "outcomes": [] if aborted else outcomes}
            known = {o["action_id"]: o for o in outcomes}
            admission = admissions.get(actor, {})
            for entry in admission.get("actions", []):
                action_id = entry["action_id"]
                if action_id in known:
                    outcome = known[action_id]
                elif action_id in action_results:
                    result = action_results[action_id]
                    outcome = {"action_id": action_id, "status": "succeeded" if result["ok"] else "business_failed", "result": result}
                else:
                    outcome = skips.get(action_id, {"action_id": action_id, "status": "aborted", "reason": "WAVE_EXECUTION_ABORTED"})
                db.add(ActionReceipt(session_id=claim.session_id, action_id=action_id, actor_id=actor, request_id=batch["request_id"],
                                     context=admission["context"], action=entry["action"], outcome=outcome))

    def commit_candidate(self, candidate: Candidate):
        claim, runner = candidate.claim, candidate.runner
        records = runner.journal.records
        if records[:len(claim.records)] != claim.records:
            raise ServiceError("CANDIDATE_PREFIX_CHANGED", 503)
        delta = records[len(claim.records):]
        with self.sessions() as db:
            row = self._locked(db, claim.session_id)
            if (row.fence, row.published_version, row.transcript_digest) != (claim.fence, claim.version, claim.transcript_digest):
                raise ServiceError("WRITER_FENCED")
            self._append_records(db, claim.session_id, delta)
            self._settle_batches(db, candidate, delta)
            runtime = self._runtime(runner)
            row.status, row.runtime = runtime["status"], runtime
            row.published_version = runner.published_version
            row.next_boundary = data(runner.next_boundary)
            row.transcript_count, row.transcript_digest = len(records), digest(records)
            row.state_digest = digest(runner.economic_state())
            for actor, projection in self._projections(runner).items():
                stored = db.get(ActorProjection, (claim.session_id, actor))
                stored.version, stored.payload = runner.published_version, projection
            self._commit(db, "boundary")
        # There is no second, in-process actor publication after COMMIT.
        # API readers use projections committed above; notification is a durable outbox.
        self._ensure_metrics(claim.session_id)
        return deepcopy(runtime)

    def _ensure_metrics(self, session_id):
        from .metric_store import MetricStore
        MetricStore(self).ensure(session_id)

    def metrics(self, session_id, *, publication_version=None):
        """Trusted host only; no tokens, private text or raw journal in the report."""
        from .metric_store import MetricStore
        return MetricStore(self).read(session_id, publication_version=publication_version)

    def leaderboard(self, session_id, *, publication_version=None):
        report = self.metrics(session_id, publication_version=publication_version)
        return {key: report[key] for key in ("session_id", "source_publication_version", "leaderboard", "leaderboard_history", "publication_leaderboards")}

    def run_ready(self, session_id):
        self._ensure_metrics(session_id)
        claim = self.claim(session_id)
        if claim is None:
            return {"progressed": False}
        candidate = self.compute(claim)
        return {"progressed": True, "runtime": self.commit_candidate(candidate)}

    def work_pending(self):
        with self.sessions() as db:
            ids = list(db.scalars(select(MarketSession.id).where(MarketSession.status.in_(("awaiting_batches", "round_close_pending")))))
        for session_id in ids:
            try:
                self.run_ready(session_id)
            except ServiceError as error:
                # One incompatible/corrupt session must not starve other sessions.
                logging.getLogger("salesbench.platform").warning("Session %s: %s", session_id, error.code)
            except Exception as error:
                # Keep other sessions running; no fabricated Wait or economic commit.
                # Exception messages/tracebacks may contain private SQL/driver payloads.
                logging.getLogger("salesbench.platform").error("Session %s stopped at committed boundary: %s",
                                                              session_id, type(error).__name__)

    def recover(self, session_id):
        """Read-only host audit; no untrusted state loading or economic commit."""
        with self.sessions() as db:
            # Lock makes the full transcript/digest read one consistent boundary.
            row = self._locked(db, session_id)
            if row.source_digest != self.code_digest:
                raise ServiceError("RECOVERY_CODE_MISMATCH", 503)
            records = self._load_records(db, row)
            expected = (row.published_version, row.state_digest)
        return self._restore_verified(records, expected)

    @staticmethod
    def _restore_verified(records, expected):
        """Shared host audit: replay AND compare the committed version/state digest."""
        try:
            runner = asyncio.run(restore_committed(records, {a: SubmissionDriver() for a in records[0]["drivers"]}))
        except ReplayMismatch:
            raise ServiceError("RECOVERY_TRACE_MISMATCH", 503) from None
        if (runner.published_version, digest(runner.economic_state())) != expected:
            raise ServiceError("RECOVERY_STATE_MISMATCH", 503)
        return runner
