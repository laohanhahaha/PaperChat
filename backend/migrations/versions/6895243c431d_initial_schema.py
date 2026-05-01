"""initial_schema

Revision ID: 6895243c431d
Revises: 
Create Date: 2026-04-18 01:16:18.114777

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6895243c431d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    初始表结构由 init_db() -> Base.metadata.create_all() 自动创建，
    此迁移仅记录版本号，不重复执行 DDL。
    """
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
