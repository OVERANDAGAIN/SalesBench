"""PostgreSQL storage records. No economic calculations or Engine mutations."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, create_engine, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class MarketSession(Base):
    __tablename__ = "market_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    setup: Mapped[dict] = mapped_column(JSONB)
    market_config: Mapped[dict] = mapped_column(JSONB)
    source_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    published_version: Mapped[int] = mapped_column(BigInteger)
    fence: Mapped[int] = mapped_column(BigInteger, default=0)
    transcript_count: Mapped[int] = mapped_column(BigInteger)
    transcript_digest: Mapped[str] = mapped_column(String(64))
    state_digest: Mapped[str] = mapped_column(String(64))
    runtime: Mapped[dict] = mapped_column(JSONB)
    next_boundary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metrics_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("published_version >= 0 AND fence >= 0 AND transcript_count >= 2", name="ck_session_counters"),)


class ActorBinding(Base):
    __tablename__ = "actor_bindings"
    session_id: Mapped[str] = mapped_column(ForeignKey("market_sessions.id"), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    role: Mapped[str] = mapped_column(String(16))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)


class ActorProjection(Base):
    __tablename__ = "actor_projections"
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (ForeignKeyConstraint(["session_id", "actor_id"], ["actor_bindings.session_id", "actor_bindings.actor_id"]),)


class Publication(Base):
    __tablename__ = "publications"
    session_id: Mapped[str] = mapped_column(ForeignKey("market_sessions.id"), primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public: Mapped[dict] = mapped_column(JSONB)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    state_digest: Mapped[str] = mapped_column(String(64))


class BatchReceipt(Base):
    __tablename__ = "batch_receipts"
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSONB)
    # NULL for pre-admission rejections; accepted opportunities can occur only once.
    opportunity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_version: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32))
    receipt: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["session_id", "actor_id"], ["actor_bindings.session_id", "actor_bindings.actor_id"]),
        UniqueConstraint("session_id", "actor_id", "opportunity_id", name="uq_actor_opportunity"),
        Index("ix_pending_batches", "session_id", "status"),
    )


class ActionReceipt(Base):
    __tablename__ = "action_receipts"
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    request_id: Mapped[str] = mapped_column(String(128))
    context: Mapped[dict] = mapped_column(JSONB)
    action: Mapped[dict] = mapped_column(JSONB)
    outcome: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (ForeignKeyConstraint(["session_id", "actor_id", "request_id"],
                                         ["batch_receipts.session_id", "batch_receipts.actor_id", "batch_receipts.request_id"]),)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    session_id: Mapped[str] = mapped_column(ForeignKey("market_sessions.id"), primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class Resolution(Base):
    __tablename__ = "resolutions"
    session_id: Mapped[str] = mapped_column(ForeignKey("market_sessions.id"), primary_key=True)
    context_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(32), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class SemanticEvent(Base):
    __tablename__ = "semantic_events"
    session_id: Mapped[str] = mapped_column(ForeignKey("market_sessions.id"), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class OutboxNotice(Base):
    __tablename__ = "outbox_notices"
    session_id: Mapped[str] = mapped_column(ForeignKey("market_sessions.id"), primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class LeaderboardSnapshot(Base):
    __tablename__ = "leaderboard_snapshots"
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_publication_version: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    payload_digest: Mapped[str] = mapped_column(String(64))
    __table_args__ = (ForeignKeyConstraint(["session_id", "source_publication_version"], ["publications.session_id", "publications.version"]),)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    session_id: Mapped[str] = mapped_column(ForeignKey("market_sessions.id"), primary_key=True)
    transcript_count: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    publication_version: Mapped[int] = mapped_column(BigInteger)
    leaderboard_source_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    payload_digest: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(["session_id", "publication_version"], ["publications.session_id", "publications.version"]),
        ForeignKeyConstraint(["session_id", "leaderboard_source_version"], ["leaderboard_snapshots.session_id", "leaderboard_snapshots.source_publication_version"]),
    )


def database(url: str):
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("This service requires PostgreSQL with psycopg; no SQLite fallback")
    options = parsed.query.get("options", "") + " -cstatement_timeout=15000 -clock_timeout=5000"
    parsed = parsed.update_query_dict({"options": options.strip()})
    engine = create_engine(parsed, pool_pre_ping=True, pool_size=5, max_overflow=5,
                           connect_args={"connect_timeout": 5}, hide_parameters=True)
    return engine, sessionmaker(engine, expire_on_commit=False)
