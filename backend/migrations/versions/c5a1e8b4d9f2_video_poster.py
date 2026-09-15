"""video poster_path column (additive, nullable)

Revision ID: c5a1e8b4d9f2
Revises: e7c4b9f2a831  (video TimestampMixin + hard delete)
"""

import sqlalchemy as sa
from alembic import op

revision = "c5a1e8b4d9f2"
down_revision = "e7c4b9f2a831"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video", sa.Column("poster_path", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("video", "poster_path")
