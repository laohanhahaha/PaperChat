"""add_custom_subagents_table

Revision ID: d8f2a3b7c1e5
Revises: c7d4e9f1a2b6
Create Date: 2026-04-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f2a3b7c1e5'
down_revision: Union[str, Sequence[str], None] = 'c7d4e9f1a2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 custom_subagents 表"""
    op.create_table('custom_subagents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=False, server_default=''),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('tool_subset', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('is_preset', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_custom_subagents_user_id'), 'custom_subagents', ['user_id'], unique=False)


def downgrade() -> None:
    """删除 custom_subagents 表"""
    op.drop_index(op.f('ix_custom_subagents_user_id'), table_name='custom_subagents')
    op.drop_table('custom_subagents')
