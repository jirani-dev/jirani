"""video: adopt TimestampMixin (add updated_at, tighten created_at) + drop deleted_at

Revision ID: e7c4b9f2a831
Revises: b3f9a2c71d04  (authors/levels/genres)
"""

import sqlalchemy as sa
from alembic import op

revision = "e7c4b9f2a831"
down_revision = "b3f9a2c71d04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video",
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    # Match the mixin's DDL: client-side default only, no server default.
    op.execute("ALTER TABLE video ALTER COLUMN updated_at DROP DEFAULT")
    # Tighten created_at: backfill any NULLs, then NOT NULL.
    op.execute("UPDATE video SET created_at = now() WHERE created_at IS NULL")
    op.execute("ALTER TABLE video ALTER COLUMN created_at SET NOT NULL")
    # Hard delete (2026-09-14 amendment): soft-delete tracking is gone.
    op.drop_column("video", "deleted_at")


def downgrade() -> None:
    op.add_column("video", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.execute("ALTER TABLE video ALTER COLUMN created_at DROP NOT NULL")
    op.drop_column("video", "updated_at")
