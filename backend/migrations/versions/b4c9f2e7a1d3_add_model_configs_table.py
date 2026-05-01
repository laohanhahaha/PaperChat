"""add_model_configs_table

Revision ID: b4c9f2e7a1d3
Revises: a3f8e1c7d2b5
Create Date: 2026-04-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c9f2e7a1d3'
down_revision: Union[str, Sequence[str], None] = 'a3f8e1c7d2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 model_configs 表"""
    op.create_table('model_configs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('display_name', sa.String(), nullable=False),
    sa.Column('model_name', sa.String(), nullable=False),
    sa.Column('api_key', sa.String(), nullable=False),
    sa.Column('api_base_url', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default='0'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_configs_user_id'), 'model_configs', ['user_id'], unique=False)


def downgrade() -> None:
    """删除 model_configs 表"""
    op.drop_index(op.f('ix_model_configs_user_id'), table_name='model_configs')
    op.drop_table('model_configs')
