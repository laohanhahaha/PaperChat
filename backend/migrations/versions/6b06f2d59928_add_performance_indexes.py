"""add_performance_indexes

Revision ID: 6b06f2d59928
Revises: 6895243c431d
Create Date: 2026-04-19 06:25:30.363565

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b06f2d59928'
down_revision: Union[str, Sequence[str], None] = '6895243c431d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    性能索引由 init_db() -> Base.metadata.create_all() 自动创建，
    此迁移仅记录版本号，不重复执行 DDL。
    """
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
