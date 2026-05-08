"""add_generated_image_storage_and_message_link

Revision ID: c4a9d8e7f1b2
Revises: b3c1b9f6e2a4
Create Date: 2026-05-08 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4a9d8e7f1b2"
down_revision: Union[str, Sequence[str], None] = "b3c1b9f6e2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "generated_images",
        sa.Column("message_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "generated_images",
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
    )
    op.create_index(
        op.f("ix_generated_images_message_id"),
        "generated_images",
        ["message_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_generated_images_message_id_messages",
        "generated_images",
        "messages",
        ["message_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_generated_images_message_id_messages",
        "generated_images",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_generated_images_message_id"), table_name="generated_images")
    op.drop_column("generated_images", "storage_path")
    op.drop_column("generated_images", "message_id")
