"""audio hard delete: drop audio.deleted_at

Revision ID: 3f3601bd9d70
Revises: c5a1e8b4d9f2  (video poster)
"""

import sqlalchemy as sa
from alembic import op

revision = "3f3601bd9d70"
down_revision = "c5a1e8b4d9f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM audio WHERE deleted_at IS NOT NULL"))
    op.drop_column("audio", "deleted_at")


def downgrade() -> None:
    op.add_column("audio", sa.Column("deleted_at", sa.DateTime(), nullable=True))
