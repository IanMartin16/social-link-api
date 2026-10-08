"""detector_tables

Revision ID: 0d67f79f4ef6
Revises: d5a9fdfbd2a0
Create Date: 2026-10-07 21:41:17.932018

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0d67f79f4ef6'
down_revision: Union[str, Sequence[str], None] = 'd5a9fdfbd2a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ----- coin_registry (semilla del ID propio) -----
    op.create_table(
        "coin_registry",
        sa.Column("cl_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("coingecko_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("cmc_id", sa.Text(), nullable=True),
        sa.Column("contract_addr", sa.Text(), nullable=True),
        sa.Column("chain", sa.Text(), nullable=True),
        sa.Column("aliases", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("first_seen_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("coingecko_id", name="uq_registry_coingecko_id"),
    )
    op.create_index("ix_registry_symbol", "coin_registry", ["symbol"])

    # ----- trending_episode (cabecera) -----
    op.create_table(
        "trending_episode",
        sa.Column("episode_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cl_id", sa.BigInteger(), nullable=False),
        sa.Column("coingecko_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),

        sa.Column("entered_trend_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(38, 12), nullable=True),
        sa.Column("entry_rank", sa.Integer(), nullable=True),
        sa.Column("entry_mcap", sa.Numeric(38, 2), nullable=True),
        sa.Column("entry_vol24h", sa.Numeric(38, 2), nullable=True),
        sa.Column("entry_features", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),

        sa.Column("recent_high", sa.Numeric(38, 12), nullable=True),
        sa.Column("recent_high_win_d", sa.Integer(), server_default=sa.text("7"), nullable=False),
        sa.Column("peak_confidence", sa.Text(), server_default=sa.text("'observed'"), nullable=False),

        sa.Column("peak_price", sa.Numeric(38, 12), nullable=True),
        sa.Column("peak_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("trough_price", sa.Numeric(38, 12), nullable=True),
        sa.Column("trough_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(6, 5), nullable=True),

        sa.Column("left_trend_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("state", sa.Text(), server_default=sa.text("'ACTIVE_TRENDING'"), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("event_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("time_to_event_h", sa.Numeric(10, 3), nullable=True),
        sa.Column("dump_speed_h", sa.Numeric(10, 3), nullable=True),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),

        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),

        sa.ForeignKeyConstraint(["cl_id"], ["coin_registry.cl_id"], name="fk_episode_cl_id"),
    )
    # un episodio ABIERTO por coin → la reentrada continúa el mismo (constraint de DB)
    op.create_index(
        "uq_episode_open_coin", "trending_episode", ["cl_id"], unique=True,
        postgresql_where=sa.text("state <> 'CLOSED'"),
    )
    op.create_index(
        "ix_episode_open", "trending_episode", ["state"],
        postgresql_where=sa.text("state <> 'CLOSED'"),
    )
    op.create_index("ix_episode_cl", "trending_episode", ["cl_id", "entered_trend_at"])

    # ----- episode_track (serie temporal) -----
    op.create_table(
        "episode_track",
        sa.Column("track_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("episode_id", sa.BigInteger(), nullable=False),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(38, 12), nullable=True),
        sa.Column("source", sa.Text(), server_default=sa.text("'coingecko'"), nullable=False),
        sa.Column("in_trending", sa.Boolean(), nullable=True),
        sa.Column("trend_position", sa.Integer(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("vol24h", sa.Numeric(38, 2), nullable=True),
        sa.Column("drawdown_from_peak", sa.Numeric(6, 5), nullable=True),
        sa.Column("time_in_trend_h", sa.Numeric(10, 3), nullable=True),
        sa.Column("raw", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("live_features", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["trending_episode.episode_id"],
                                name="fk_track_episode", ondelete="CASCADE"),
        # único por (episodio, ts); su índice también sirve para lookups ordenados
        sa.UniqueConstraint("episode_id", "ts", name="uq_track_ep_ts"),
    )


def downgrade() -> None:
    op.drop_table("episode_track")   # uq_track_ep_ts cae con la tabla

    op.drop_index("ix_episode_cl", table_name="trending_episode")
    op.drop_index("ix_episode_open", table_name="trending_episode")
    op.drop_index("uq_episode_open_coin", table_name="trending_episode")
    op.drop_table("trending_episode")

    op.drop_index("ix_registry_symbol", table_name="coin_registry")
    op.drop_table("coin_registry")