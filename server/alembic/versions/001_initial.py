"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "simulations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("market", sa.String(20), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False, server_default="1m"),
        sa.Column("session_filter", sa.String(50), nullable=True),
        sa.Column("session_start", sa.String(10), nullable=True),
        sa.Column("session_end", sa.String(10), nullable=True),
        sa.Column("num_rounds", sa.Integer, nullable=False, server_default="10"),
        sa.Column("starting_capital", sa.Float, nullable=False, server_default="10000"),
        sa.Column("fee_bps", sa.Float, nullable=False, server_default="10"),
        sa.Column("slippage_bps", sa.Float, nullable=False, server_default="5"),
        sa.Column("seed", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "rounds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("simulation_id", UUID(as_uuid=True), sa.ForeignKey("simulations.id"), nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("hidden_date", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("current_index", sa.Integer, server_default="0"),
        sa.Column("total_candles", sa.Integer, server_default="0"),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("round_id", UUID(as_uuid=True), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("ts_index", sa.Integer, nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("type", sa.String(10), nullable=False, server_default="market"),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("limit_price", sa.Float, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "fills",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("round_id", UUID(as_uuid=True), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("ts_index", sa.Integer, nullable=False),
        sa.Column("fill_price", sa.Float, nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("fee", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("round_id", UUID(as_uuid=True), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("ts_index", sa.Integer, nullable=False),
        sa.Column("equity", sa.Float, nullable=False),
        sa.Column("cash", sa.Float, nullable=False),
        sa.Column("position_qty", sa.Float, nullable=False, server_default="0"),
        sa.Column("avg_price", sa.Float, nullable=False, server_default="0"),
        sa.Column("unrealized_pnl", sa.Float, nullable=False, server_default="0"),
        sa.Column("realized_pnl", sa.Float, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("snapshots")
    op.drop_table("fills")
    op.drop_table("orders")
    op.drop_table("rounds")
    op.drop_table("simulations")
    op.drop_table("users")
