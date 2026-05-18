"""add external source links table

Revision ID: d9a2f1e6c7b8
Revises: a3e9f2b1c4d5
Create Date: 2026-05-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d9a2f1e6c7b8"
down_revision: Union[str, Sequence[str], None] = "a3e9f2b1c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_source_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "url", name="uq_external_source_links_user_url"),
    )
    op.create_index(
        op.f("ix_external_source_links_user_id"),
        "external_source_links",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_source_links_source_kind"),
        "external_source_links",
        ["source_kind"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_external_source_links_source_kind"), table_name="external_source_links")
    op.drop_index(op.f("ix_external_source_links_user_id"), table_name="external_source_links")
    op.drop_table("external_source_links")