"""笔记导出服务

提供笔记导出为 Markdown 或 JSON 格式的功能
"""
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.paper import Paper
from app.models.note import Note


class MemoExportService:
    """笔记导出服务类"""
    
    async def export_markdown(
        self, 
        paper_id: int, 
        user_id: int,
        db: AsyncSession
    ) -> str:
        """导出指定论文的笔记为 Markdown 格式
        
        Args:
            paper_id: 论文 ID
            user_id: 用户 ID（用于权限验证）
            db: 数据库会话
            
        Returns:
            Markdown 格式的字符串
        """
        # 1. 查询论文信息
        paper_result = await db.execute(
            select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
        )
        paper = paper_result.scalar_one_or_none()
        
        if not paper:
            raise ValueError(f"论文不存在或无权限访问: paper_id={paper_id}")
        
        # 2. 查询该论文的所有笔记（包含关联的高亮信息）
        notes_result = await db.execute(
            select(Note).options(
                joinedload(Note.highlight)
            ).where(
                Note.paper_id == paper_id,
                Note.user_id == user_id
            ).order_by(Note.created_at)
        )
        notes = notes_result.scalars().all()
        
        # 3. 生成 Markdown
        md_lines = [
            f"# {paper.title if paper else 'Unknown Paper'}",
            f"",
            f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"笔记数量: {len(notes)}",
            f"",
            f"---",
            f"",
        ]
        
        for i, note in enumerate(notes, 1):
            md_lines.append(f"## 笔记 {i}")
            md_lines.append(f"")
            # 引用高亮文本（如果有）
            if note.highlight and note.highlight.selected_text:
                md_lines.append(f"> {note.highlight.selected_text}")
                md_lines.append(f"")
            md_lines.append(note.content)
            md_lines.append(f"")
            if note.created_at:
                md_lines.append(f"*创建于 {note.created_at.strftime('%Y-%m-%d %H:%M')}*")
            md_lines.append(f"")
            md_lines.append(f"---")
            md_lines.append(f"")
        
        return "\n".join(md_lines)
    
    async def export_json(
        self, 
        paper_id: int, 
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """导出指定论文的笔记为 JSON 格式
        
        Args:
            paper_id: 论文 ID
            user_id: 用户 ID（用于权限验证）
            db: 数据库会话
            
        Returns:
            包含笔记数据的字典
        """
        # 1. 查询论文信息
        paper_result = await db.execute(
            select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
        )
        paper = paper_result.scalar_one_or_none()
        
        if not paper:
            raise ValueError(f"论文不存在或无权限访问: paper_id={paper_id}")
        
        # 2. 查询该论文的所有笔记（包含关联的高亮信息）
        notes_result = await db.execute(
            select(Note).options(
                joinedload(Note.highlight)
            ).where(
                Note.paper_id == paper_id,
                Note.user_id == user_id
            ).order_by(Note.created_at)
        )
        notes = notes_result.scalars().all()
        
        return {
            "paper_id": paper_id,
            "paper_title": paper.title if paper else "Unknown",
            "exported_at": datetime.now().isoformat(),
            "notes": [
                {
                    "id": n.id,
                    "content": n.content,
                    "highlight_text": n.highlight.selected_text if n.highlight else None,
                    "highlight_id": n.highlight_id,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                    "updated_at": n.updated_at.isoformat() if n.updated_at else None,
                }
                for n in notes
            ]
        }
    
    async def batch_export(
        self, 
        paper_ids: List[int], 
        format: str, 
        user_id: int,
        db: AsyncSession
    ) -> str | Dict[str, Any]:
        """批量导出多篇论文的笔记
        
        Args:
            paper_ids: 论文 ID 列表
            format: 导出格式 ('md' 或 'json')
            user_id: 用户 ID（用于权限验证）
            db: 数据库会话
            
        Returns:
            Markdown 字符串或 JSON 字典
        """
        if format == 'md':
            results = []
            for pid in paper_ids:
                try:
                    result = await self.export_markdown(pid, user_id, db)
                    results.append(result)
                except ValueError as e:
                    # 跳过无权限的论文，记录错误
                    results.append(f"<!-- {e} -->")
            return "\n\n".join(results)
        else:
            all_exports = []
            errors = []
            for pid in paper_ids:
                try:
                    export_data = await self.export_json(pid, user_id, db)
                    all_exports.append(export_data)
                except ValueError as e:
                    errors.append({"paper_id": pid, "error": str(e)})
            return {
                "exports": all_exports, 
                "total": len(all_exports),
                "errors": errors if errors else None
            }


# 全局服务实例
memo_export_service = MemoExportService()
