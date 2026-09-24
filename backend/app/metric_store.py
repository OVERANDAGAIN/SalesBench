"""Durable derived views. Reads committed DB records, never a candidate Runner.

Economic COMMIT is unchanged. A missing metric boundary is deterministically
materialized after COMMIT (or on reconnect); readers fail closed until the exact
committed transcript has its view. Repeated reads never invent new snapshot IDs.
"""
from copy import deepcopy

from sqlalchemy import select

from salesbench_engine.runner.codec import digest

from .metrics import derive, validate_policy
from .persistence import LeaderboardSnapshot, MarketSession, MetricSnapshot, Publication
from .service import ServiceError


class MetricStore:
    def __init__(self, service):
        self.service = service

    @staticmethod
    def validate(row):
        try:
            validate_policy(row.metrics_policy)
        except (ValueError, TypeError, KeyError):
            raise ServiceError("METRICS_POLICY_MISMATCH", 503) from None

    @staticmethod
    def checked(row):
        if row is None:
            raise ServiceError("METRICS_NOT_READY", 503)
        if digest(row.payload) != row.payload_digest:
            raise ServiceError("METRICS_SNAPSHOT_MISMATCH", 503)
        return deepcopy(row.payload)

    def ensure(self, sid):
        # Fast path avoids waiting on an in-flight economic transaction's row lock.
        with self.service.sessions() as db:
            row = db.get(MarketSession, sid)
            if row is None:
                raise ServiceError("SESSION_NOT_FOUND", 404)
            if row.metrics_policy is None:
                return  # Pre-migration sessions never advertised a leaderboard.
            self.validate(row)
            if row.source_digest != self.service.code_digest:
                raise ServiceError("RECOVERY_CODE_MISMATCH", 503)
            ready = db.get(MetricSnapshot, (sid, row.transcript_count))
            if ready is not None:
                payload = self.checked(ready)
                if (payload["source_transcript_digest"], payload["source_state_digest"]) != (row.transcript_digest, row.state_digest):
                    raise ServiceError("METRICS_SOURCE_MISMATCH", 503)
                return
        with self.service.sessions() as db:
            row = self.service._locked(db, sid)
            self.validate(row)
            if row.source_digest != self.service.code_digest:
                raise ServiceError("RECOVERY_CODE_MISMATCH", 503)
            records = self.service._load_records(db, row)
            # Preserve the original full economic recovery/digest checks.
            self.service._restore_verified(records, (row.published_version, row.state_digest))
            snapshots, boards = derive(sid, records, row.metrics_policy, row.runtime)
            for board in boards:
                key = (sid, board["source_publication_version"])
                existing = db.get(LeaderboardSnapshot, key)
                if existing is not None:
                    if self.checked(existing) != board:
                        raise ServiceError("METRICS_SNAPSHOT_MISMATCH", 503)
                else:
                    db.add(LeaderboardSnapshot(session_id=sid, source_publication_version=key[1],
                                               payload=board, payload_digest=digest(board)))
            db.flush()
            for snapshot in snapshots:
                existing = db.get(MetricSnapshot, (sid, snapshot["transcript_count"]))
                if existing is not None:
                    if (self.checked(existing), existing.leaderboard_source_version) != (snapshot["payload"], snapshot["leaderboard_source_version"]):
                        raise ServiceError("METRICS_SNAPSHOT_MISMATCH", 503)
                else:
                    db.add(MetricSnapshot(session_id=sid, **snapshot, payload_digest=digest(snapshot["payload"])))
            self.service._commit(db, "metrics")

    def read(self, sid, *, publication_version=None):
        self.ensure(sid)
        with self.service.sessions() as db:
            row = self.service._locked(db, sid)
            if row.metrics_policy is None:
                raise ServiceError("METRICS_NOT_ENABLED", 409)
            self.validate(row)
            snapshots = list(db.scalars(select(MetricSnapshot).where(MetricSnapshot.session_id == sid).order_by(MetricSnapshot.transcript_count)))
            if publication_version is None:
                selected = next((s for s in snapshots if s.transcript_count == row.transcript_count), None)
            else:
                if db.get(Publication, (sid, publication_version)) is None:
                    raise ServiceError("PUBLICATION_NOT_FOUND", 404)
                selected = next((s for s in reversed(snapshots) if s.publication_version == publication_version), None)
            payload = self.checked(selected)
            boards = list(db.scalars(select(LeaderboardSnapshot).where(
                LeaderboardSnapshot.session_id == sid, LeaderboardSnapshot.source_publication_version <= selected.publication_version
            ).order_by(LeaderboardSnapshot.source_publication_version)))
            history = [self.checked(b) for b in boards]
            current = next((b for b in history if b["source_publication_version"] == selected.leaderboard_source_version), None)
            mapping = [{"publication_version": s.publication_version, "transcript_count": s.transcript_count,
                        "leaderboard_source_version": s.leaderboard_source_version}
                       for s in snapshots if s.transcript_count <= selected.transcript_count]
            profit_history = [{"source_publication_version": s.publication_version, "transcript_count": s.transcript_count,
                               "seller_id": seller["seller_id"], "dev_profit_cents": seller["dev_profit_cents"]}
                              for s in snapshots if s.transcript_count <= selected.transcript_count for seller in self.checked(s)["sellers"]]
            return {**payload, "leaderboard": current, "leaderboard_history": history,
                    "publication_leaderboards": mapping, "profit_trajectory": profit_history}
