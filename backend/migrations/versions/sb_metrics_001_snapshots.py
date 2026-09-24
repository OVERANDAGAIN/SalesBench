"""Versioned development metrics, derived only from committed transcripts.

Existing sessions retain NULL policy: no fabricated historical public rankings.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "sb_metrics_001"
down_revision = "sb_platform_001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("market_sessions", sa.Column("metrics_policy", JSONB(), nullable=True))
    op.create_table("leaderboard_snapshots",
                    sa.Column("session_id", sa.String(64), primary_key=True),
                    sa.Column("source_publication_version", sa.BigInteger(), primary_key=True),
                    sa.Column("payload", JSONB(), nullable=False),
                    sa.Column("payload_digest", sa.String(64), nullable=False),
                    sa.ForeignKeyConstraint(["session_id", "source_publication_version"], ["publications.session_id", "publications.version"]))
    op.create_table("metric_snapshots",
                    sa.Column("session_id", sa.String(64), sa.ForeignKey("market_sessions.id"), primary_key=True),
                    sa.Column("transcript_count", sa.BigInteger(), primary_key=True),
                    sa.Column("publication_version", sa.BigInteger(), nullable=False),
                    sa.Column("leaderboard_source_version", sa.BigInteger(), nullable=True),
                    sa.Column("payload", JSONB(), nullable=False),
                    sa.Column("payload_digest", sa.String(64), nullable=False),
                    sa.ForeignKeyConstraint(["session_id", "publication_version"], ["publications.session_id", "publications.version"]),
                    sa.ForeignKeyConstraint(["session_id", "leaderboard_source_version"], ["leaderboard_snapshots.session_id", "leaderboard_snapshots.source_publication_version"]))


def downgrade():
    op.drop_table("metric_snapshots")
    op.drop_table("leaderboard_snapshots")
    op.drop_column("market_sessions", "metrics_policy")
