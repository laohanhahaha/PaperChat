"""add file_hash to papers

Revision ID: c7d4e9f1a2b6
Revises: b4c9f2e7a1d3
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7d4e9f1a2b6'
down_revision: Union[str, None] = 'b4c9f2e7a1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('papers', sa.Column('file_hash', sa.String(64), nullable=True))
    op.create_index(op.f('ix_papers_file_hash'), 'papers', ['file_hash'])


def downgrade() -> None:
    op.drop_index(op.f('ix_papers_file_hash'), table_name='papers')
    op.drop_column('papers', 'file_hash')
