"""add_generated_images_table

Revision ID: b3c1b9f6e2a4
Revises: 8d4dfd11b2d0
Create Date: 2026-05-08 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3c1b9f6e2a4"
down_revision: Union[str, Sequence[str], None] = "8d4dfd11b2d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "generated_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("image_base64", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("provider_model", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generated_images_thread_id"),
        "generated_images",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_images_user_id"),
        "generated_images",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_generated_images_user_id"), table_name="generated_images")
    op.drop_index(op.f("ix_generated_images_thread_id"), table_name="generated_images")
    op.drop_table("generated_images")
