"""expand_attachment_kinds

Revision ID: 8d4dfd11b2d0
Revises: 1f7c3f4c2a11
Create Date: 2026-05-08 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8d4dfd11b2d0"
down_revision: Union[str, Sequence[str], None] = "1f7c3f4c2a11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    for value in ("table", "pdf", "formula"):
        op.execute(f"ALTER TYPE attachmentkind ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL does not support dropping enum values safely in-place.
    pass