"""split_paper_analysis_cache

Revision ID: 1a6c80655666
Revises: 6b06f2d59928
Create Date: 2026-04-19 06:36:21.080313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a6c80655666'
down_revision: Union[str, Sequence[str], None] = '6b06f2d59928'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 创建新表
    op.create_table('paper_analysis_cache',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('paper_id', sa.Integer(), nullable=False),
    sa.Column('section_analysis', sa.Text(), nullable=True),
    sa.Column('deep_analysis', sa.Text(), nullable=True),
    sa.Column('analysis_status', sa.String(length=20), server_default='not_generated', nullable=True),
    sa.Column('last_analyzed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['paper_id'], ['papers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_paper_analysis_cache_paper_id', 'paper_analysis_cache', ['paper_id'], unique=False)

    # 2. 数据迁移：将 papers 中的分析字段迁移到新表
    op.execute("""
        INSERT INTO paper_analysis_cache (paper_id, section_analysis, deep_analysis, analysis_status, last_analyzed_at)
        SELECT id, section_analysis, deep_analysis,
               COALESCE(analysis_status, 'not_generated'),
               last_analyzed_at
        FROM papers
        WHERE section_analysis IS NOT NULL OR deep_analysis IS NOT NULL
    """)

    # 3. 从 papers 表删除旧列（SQLite 需要使用 batch_alter_table）
    with op.batch_alter_table('papers') as batch_op:
        batch_op.drop_column('analysis_status')
        batch_op.drop_column('last_analyzed_at')
        batch_op.drop_column('deep_analysis')
        batch_op.drop_column('section_analysis')


def downgrade() -> None:
    """Downgrade schema."""
    # 1. 在 papers 表恢复旧列
    with op.batch_alter_table('papers') as batch_op:
        batch_op.add_column(sa.Column('section_analysis', sa.TEXT(), nullable=True))
        batch_op.add_column(sa.Column('deep_analysis', sa.TEXT(), nullable=True))
        batch_op.add_column(sa.Column('last_analyzed_at', sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('analysis_status', sa.VARCHAR(length=20), server_default=sa.text("'not_generated'"), nullable=True))

    # 2. 数据回迁：将分析字段从缓存表迁回 papers
    op.execute("""
        UPDATE papers
        SET section_analysis = (
                SELECT pac.section_analysis FROM paper_analysis_cache pac
                WHERE pac.paper_id = papers.id
            ),
            deep_analysis = (
                SELECT pac.deep_analysis FROM paper_analysis_cache pac
                WHERE pac.paper_id = papers.id
            ),
            analysis_status = (
                SELECT COALESCE(pac.analysis_status, 'not_generated') FROM paper_analysis_cache pac
                WHERE pac.paper_id = papers.id
            ),
            last_analyzed_at = (
                SELECT pac.last_analyzed_at FROM paper_analysis_cache pac
                WHERE pac.paper_id = papers.id
            )
        WHERE EXISTS (
            SELECT 1 FROM paper_analysis_cache pac WHERE pac.paper_id = papers.id
        )
    """)

    # 3. 删除新表
    op.drop_index('ix_paper_analysis_cache_paper_id', table_name='paper_analysis_cache')
    op.drop_table('paper_analysis_cache')
