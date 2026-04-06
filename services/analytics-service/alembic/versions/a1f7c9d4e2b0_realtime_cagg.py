"""enable real-time continuous aggregation

Revision ID: a1f7c9d4e2b0
Revises: 5c42cb1eeecd
Create Date: 2026-04-06 09:20:00.000000

The three telemetry continuous aggregates were created with the default
``timescaledb.materialized_only = true`` which means SELECT from the view
only returns rows that have already been materialized by the background
refresh job. For a live dashboard this creates visible gaps:

    * telemetry_1min   — lagged by ~2-3 minutes
    * telemetry_15min  — lagged by ~15-30 minutes
    * telemetry_1hour  — lagged by ~60-75 minutes

Setting ``materialized_only = false`` switches the view into real-time
aggregation mode: Timescale transparently UNIONs the materialized rows
with an on-the-fly ``time_bucket`` aggregation over the raw hypertable
for buckets that haven't been materialized yet. The dashboard sees a
continuous series up to ``now()`` while still benefitting from the
pre-computed rollups for older data.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f7c9d4e2b0"
down_revision: str | Sequence[str] | None = "5c42cb1eeecd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_VIEWS = ("telemetry_1min", "telemetry_15min", "telemetry_1hour")


def upgrade() -> None:
    for view in _VIEWS:
        op.execute(f"ALTER MATERIALIZED VIEW {view} SET (timescaledb.materialized_only = false)")


def downgrade() -> None:
    for view in _VIEWS:
        op.execute(f"ALTER MATERIALIZED VIEW {view} SET (timescaledb.materialized_only = true)")
