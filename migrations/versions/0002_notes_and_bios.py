"""doctor bios and appointment notes

Revision ID: 0002_notes_and_bios
Revises: 0001_initial
Create Date: 2026-10-23

Purely additive: a nullable profile blurb for doctors (used by the booking
front-end) and optional patient notes on an appointment (e.g. "child, age 4").
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_notes_and_bios"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("doctors", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "notes")
    op.drop_column("doctors", "bio")
