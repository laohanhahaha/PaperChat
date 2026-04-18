"""add_feature_flags_table

Revision ID: 99b52572dd9d
Revises: 1a6c80655666
Create Date: 2026-04-19 06:41:38.544137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99b52572dd9d'
down_revision: Union[str, Sequence[str], None] = '1a6c80655666'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 feature_flags 表"""
    op.create_table('feature_flags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feature_flags_name'), 'feature_flags', ['name'], unique=True)


def downgrade() -> None:
    """删除 feature_flags 表"""
    op.drop_index(op.f('ix_feature_flags_name'), table_name='feature_flags')
    op.drop_table('feature_flags')
