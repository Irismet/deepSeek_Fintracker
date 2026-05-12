"""Increase split_type column size to 20

Revision ID: d42ac723db9e
Revises: e106e0e0871c
Create Date: 2026-05-12 17:28:03.158777

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd42ac723db9e'
down_revision = 'e106e0e0871c'
branch_labels = None
depends_on = None


def upgrade():
    # Изменяем размер колонки split_type с VARCHAR(10) на VARCHAR(20)
    op.alter_column('split_events', 'split_type',
                    existing_type=sa.VARCHAR(length=10),
                    type_=sa.VARCHAR(length=20),
                    existing_nullable=False)


def downgrade():
    op.alter_column('split_events', 'split_type',
                    existing_type=sa.VARCHAR(length=20),
                    type_=sa.VARCHAR(length=10),
                    existing_nullable=False)