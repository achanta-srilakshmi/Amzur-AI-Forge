"""add_documents_table

Revision ID: a3e9f2b1c4d5
Revises: c4a9d8e7f1b2
Create Date: 2026-05-08 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "a3e9f2b1c4d5"
down_revision: Union[str, Sequence[str], None] = "c4a9d8e7f1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "thread_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_documents_user_thread",
        "documents",
        ["user_id", "thread_id"],
    )
    op.create_index(
        "ix_documents_file_hash_user",
        "documents",
        ["file_hash", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_file_hash_user", table_name="documents")
    op.drop_index("ix_documents_user_thread", table_name="documents")
    op.drop_table("documents")
