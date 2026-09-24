"""Persistent market sessions and canonical transcripts

Revision ID: sb_platform_001
Revises: none (initial schema)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'sb_platform_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Explicit PostgreSQL schema; application startup never performs DDL.
    op.create_table('market_sessions',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('creation_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('setup', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('market_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source_digest', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('published_version', sa.BigInteger(), nullable=False),
    sa.Column('fence', sa.BigInteger(), nullable=False),
    sa.Column('transcript_count', sa.BigInteger(), nullable=False),
    sa.Column('transcript_digest', sa.String(length=64), nullable=False),
    sa.Column('state_digest', sa.String(length=64), nullable=False),
    sa.Column('runtime', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('next_boundary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('published_version >= 0 AND fence >= 0 AND transcript_count >= 2', name='ck_session_counters'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('actor_bindings',
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('actor_id', sa.String(length=128), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('token_digest', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['market_sessions.id'], ),
    sa.PrimaryKeyConstraint('session_id', 'actor_id'),
    sa.UniqueConstraint('token_digest')
    )
    op.create_table('journal_entries',
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('seq', sa.BigInteger(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['market_sessions.id'], ),
    sa.PrimaryKeyConstraint('session_id', 'seq')
    )
    op.create_table('outbox_notices',
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('version', sa.BigInteger(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['market_sessions.id'], ),
    sa.PrimaryKeyConstraint('session_id', 'version')
    )
    op.create_table('publications',
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('version', sa.BigInteger(), nullable=False),
    sa.Column('public', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('state_digest', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['market_sessions.id'], ),
    sa.PrimaryKeyConstraint('session_id', 'version')
    )
    op.create_table('resolutions',
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('context_key', sa.String(length=128), nullable=False),
    sa.Column('purpose', sa.String(length=32), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['market_sessions.id'], ),
    sa.PrimaryKeyConstraint('session_id', 'context_key', 'purpose')
    )
    op.create_table('semantic_events',
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('event_id', sa.String(length=80), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['market_sessions.id'], ),
    sa.PrimaryKeyConstraint('session_id', 'event_id')
    )
    op.create_table('actor_projections',
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('actor_id', sa.String(length=128), nullable=False),
    sa.Column('version', sa.BigInteger(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['session_id', 'actor_id'], ['actor_bindings.session_id', 'actor_bindings.actor_id'], ),
    sa.PrimaryKeyConstraint('session_id', 'actor_id')
    )
    op.create_table('batch_receipts',
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('actor_id', sa.String(length=128), nullable=False),
    sa.Column('request_id', sa.String(length=128), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('request', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('opportunity_id', sa.String(length=64), nullable=True),
    sa.Column('submitted_version', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('receipt', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['session_id', 'actor_id'], ['actor_bindings.session_id', 'actor_bindings.actor_id'], ),
    sa.PrimaryKeyConstraint('session_id', 'actor_id', 'request_id'),
    sa.UniqueConstraint('session_id', 'actor_id', 'opportunity_id', name='uq_actor_opportunity')
    )
    op.create_index('ix_pending_batches', 'batch_receipts', ['session_id', 'status'], unique=False)
    op.create_table('action_receipts',
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('action_id', sa.String(length=80), nullable=False),
    sa.Column('actor_id', sa.String(length=128), nullable=False),
    sa.Column('request_id', sa.String(length=128), nullable=False),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('action', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('outcome', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['session_id', 'actor_id', 'request_id'], ['batch_receipts.session_id', 'batch_receipts.actor_id', 'batch_receipts.request_id'], ),
    sa.PrimaryKeyConstraint('session_id', 'action_id')
    )


def downgrade():
    # Administrative rollback removes market data; never invoked by the service.
    op.drop_table('action_receipts')
    op.drop_index('ix_pending_batches', table_name='batch_receipts')
    op.drop_table('batch_receipts')
    op.drop_table('actor_projections')
    op.drop_table('semantic_events')
    op.drop_table('resolutions')
    op.drop_table('publications')
    op.drop_table('outbox_notices')
    op.drop_table('journal_entries')
    op.drop_table('actor_bindings')
    op.drop_table('market_sessions')
