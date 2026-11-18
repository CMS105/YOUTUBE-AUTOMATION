"""add live discovery creator authorizations and recording sessions

Revision ID: 7a89b3f12456
Revises: 62bbfa64a758
Create Date: 2026-11-18 17:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7a89b3f12456'
down_revision: Union[str, None] = '62bbfa64a758'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. live_discoveries
    op.create_table(
        'live_discoveries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('video_id', sa.String(length=100), nullable=False),
        sa.Column('channel_id', sa.String(length=100), nullable=False),
        sa.Column('channel_title', sa.String(length=200), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('thumbnail_url', sa.String(length=500), nullable=True),
        sa.Column('stream_url', sa.String(length=500), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('live_status', sa.String(length=30), server_default='live', nullable=False),
        sa.Column('authorization_status', sa.String(length=30), server_default='AWAITING_AUTHORIZATION', nullable=False),
        sa.Column('recording_status', sa.String(length=30), server_default='IDLE', nullable=False),
        sa.Column('viewer_count', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id', name='uq_live_discoveries_video_id'),
    )
    op.create_index('ix_live_discoveries_video_id', 'live_discoveries', ['video_id'])
    op.create_index('ix_live_discoveries_channel_id', 'live_discoveries', ['channel_id'])
    op.create_index('ix_live_discoveries_live_status', 'live_discoveries', ['live_status'])

    # 2. creator_authorizations
    op.create_table(
        'creator_authorizations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('channel_id', sa.String(length=100), nullable=False),
        sa.Column('creator_name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('authorized_source', sa.String(length=500), nullable=True),
        sa.Column('allowed_scope', sa.String(length=100), server_default='clip_creation', nullable=False),
        sa.Column('authorized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('streamer_id', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['streamer_id'], ['streamers.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_id', name='uq_creator_authorizations_channel_id'),
    )
    op.create_index('ix_creator_authorizations_channel_id', 'creator_authorizations', ['channel_id'])
    op.create_index('ix_creator_authorizations_status', 'creator_authorizations', ['status'])

    # 3. recording_sessions
    op.create_table(
        'recording_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=32), nullable=False),
        sa.Column('discovery_id', sa.Integer(), nullable=True),
        sa.Column('authorization_id', sa.Integer(), nullable=True),
        sa.Column('channel_id', sa.String(length=100), nullable=False),
        sa.Column('video_id', sa.String(length=100), nullable=True),
        sa.Column('source_input', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='recording', nullable=False),
        sa.Column('obs_output_path', sa.String(length=1000), nullable=True),
        sa.Column('recording_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['discovery_id'], ['live_discoveries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['authorization_id'], ['creator_authorizations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recording_id'], ['recordings.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', name='uq_recording_sessions_session_id'),
    )
    op.create_index('ix_recording_sessions_session_id', 'recording_sessions', ['session_id'])
    op.create_index('ix_recording_sessions_channel_id', 'recording_sessions', ['channel_id'])
    op.create_index('ix_recording_sessions_status', 'recording_sessions', ['status'])


def downgrade() -> None:
    op.drop_table('recording_sessions')
    op.drop_table('creator_authorizations')
    op.drop_table('live_discoveries')
