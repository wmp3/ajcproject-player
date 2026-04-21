"""rename date to publication_date and add added_date

Revision ID: a7d2f1b84c5e
Revises: c8f22b18c02b
Create Date: 2026-04-21 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a7d2f1b84c5e"
down_revision = "c8f22b18c02b"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("items", "date", new_column_name="publication_date")
    op.add_column("items", sa.Column("added_date", sa.String(), nullable=True))


def downgrade():
    op.drop_column("items", "added_date")
    op.alter_column("items", "publication_date", new_column_name="date")
