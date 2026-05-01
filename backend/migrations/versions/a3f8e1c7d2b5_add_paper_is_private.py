"""add_paper_is_private

Revision ID: a3f8e1c7d2b5
Revises: 99b52572dd9d
Create Date: 2026-04-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f8e1c7d2b5'
down_revision: Union[str, Sequence[str], None] = '99b52572dd9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 papers.is_private 字段"""
    op.add_column('papers', sa.Column('is_private', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """移除 papers.is_private 字段"""
    op.drop_column('papers', 'is_private')
