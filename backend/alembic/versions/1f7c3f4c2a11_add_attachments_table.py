"""add_attachments_table

Revision ID: 1f7c3f4c2a11
Revises: 555245a3bbec
Create Date: 2026-05-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "1f7c3f4c2a11"
down_revision: Union[str, Sequence[str], None] = "555245a3bbec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


attachmentkind = postgresql.ENUM(
    "image",
    "video",
    "csv",
    "code",
    "text",
    "other",
    name="attachmentkind",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    enum_type = postgresql.ENUM(
        "image",
        "video",
        "csv",
        "code",
        "text",
        "other",
        name="attachmentkind",
    )
    enum_type.create(bind, checkfirst=True)

    inspector = sa.inspect(bind)
    if inspector.has_table("attachments"):
        return

    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("kind", attachmentkind, nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attachments_message_id"), "attachments", ["message_id"], unique=False)
    op.create_index(op.f("ix_attachments_thread_id"), "attachments", ["thread_id"], unique=False)
    op.create_index(op.f("ix_attachments_user_id"), "attachments", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_attachments_user_id"), table_name="attachments")
    op.drop_index(op.f("ix_attachments_thread_id"), table_name="attachments")
    op.drop_index(op.f("ix_attachments_message_id"), table_name="attachments")
    op.drop_table("attachments")
    attachmentkind.drop(op.get_bind(), checkfirst=True)
