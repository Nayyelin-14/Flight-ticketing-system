"""add is_verified and verification_token to users

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "users",
        sa.Column("verification_token", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_users_verification_token",
        "users",
        ["verification_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_verification_token", table_name="users")
    op.drop_column("users", "verification_token")
    op.drop_column("users", "is_verified")
