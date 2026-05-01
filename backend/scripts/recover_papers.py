"""论文记录恢复脚本

从 uploads/ 目录的 PDF 文件恢复 papers 表记录。
使用同步 sqlite3 直接操作数据库，避免异步依赖。
"""
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber

# ── 配置 ──────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"
DB_PATH = BACKEND_DIR / "chatpdf.db"
DEFAULT_USER_ID = 1

# UUID 正则：8-4-4-4-12 格式
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def extract_pdf_metadata(file_path: str) -> dict:
    """用 pdfplumber 提取 PDF 元数据（标题、作者、页数）"""
    try:
        with pdfplumber.open(file_path) as pdf:
            title = ""
            authors = ""
            page_count = len(pdf.pages)

            # 尝试从 PDF 元数据中提取
            if pdf.metadata:
                title = pdf.metadata.get("Title", "") or ""
                authors = pdf.metadata.get("Author", "") or ""

            # 如果没有标题，尝试从第一页文本提取
            if not title and len(pdf.pages) > 0:
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""
                lines = text.strip().split("\n")
                if lines:
                    # 通常标题在第一行
                    title = lines[0][:200] if lines[0] else ""

            return {
                "title": title,
                "authors": authors,
                "page_count": page_count,
            }
    except Exception as e:
        print(f"  [警告] 提取元数据失败: {e}")
        return {"title": "", "authors": "", "page_count": 0}


def infer_title_from_filename(filename: str) -> str:
    """从文件名推断标题：去掉 UUID 前缀和 .pdf 后缀"""
    name = filename
    # 去掉 .pdf 后缀
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    # 去掉 UUID 前缀（如果有的话）
    match = UUID_PATTERN.match(name)
    if match:
        remainder = name[match.end():]
        # 去掉可能的分隔符（- 或 _）
        remainder = remainder.lstrip("-_")
        if remainder:
            return remainder.replace("-", " ").replace("_", " ").strip()
    # 如果没有 UUID 前缀，直接用文件名
    return name.replace("-", " ").replace("_", " ").strip()


def recover_papers():
    """主恢复流程"""
    # 1. 检查 uploads 目录
    if not UPLOAD_DIR.exists():
        print(f"[错误] 上传目录不存在: {UPLOAD_DIR}")
        sys.exit(1)

    pdf_files = sorted(
        f for f in os.listdir(UPLOAD_DIR)
        if f.lower().endswith(".pdf") and os.path.isfile(UPLOAD_DIR / f)
    )
    # 排除 .gitkeep 等非 PDF
    pdf_files = [f for f in pdf_files if not f.startswith(".")]

    print(f"发现 {len(pdf_files)} 个 PDF 文件")
    if not pdf_files:
        print("[完成] 没有需要恢复的 PDF 文件")
        return

    # 2. 连接数据库
    if not DB_PATH.exists():
        print(f"[错误] 数据库文件不存在: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    # 检查 papers 表是否存在
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='papers'"
    )
    if not cursor.fetchone():
        print("[错误] papers 表不存在，请先初始化数据库")
        conn.close()
        sys.exit(1)

    # 查询已有记录的 file_path，避免重复插入
    cursor.execute("SELECT file_path FROM papers")
    existing_paths = {row[0] for row in cursor.fetchall()}
    print(f"数据库已有 {len(existing_paths)} 条论文记录")

    # 3. 逐个处理 PDF 文件
    recovered = 0
    skipped = 0
    failed = 0

    for i, filename in enumerate(pdf_files, 1):
        file_path = UPLOAD_DIR / filename
        abs_path = str(file_path)
        # 使用与项目一致的相对路径格式（与上传逻辑相同）
        rel_path = str(Path("./uploads") / filename)

        # 检查是否已存在（同时检查绝对路径和相对路径）
        if abs_path in existing_paths or rel_path in existing_paths:
            print(f"  [{i}/{len(pdf_files)}] 跳过（已存在）: {filename}")
            skipped += 1
            continue

        file_size = os.path.getsize(abs_path)

        # 提取 PDF 元数据
        metadata = extract_pdf_metadata(abs_path)

        # 确定标题：优先使用 PDF 元数据中的标题，否则从文件名推断
        title = metadata["title"]
        if not title or title == "未命名论文":
            title = infer_title_from_filename(filename)
        if not title:
            title = filename[:-4]  # 最后兜底用文件名

        authors = metadata["authors"]
        page_count = metadata["page_count"]

        # 插入记录
        now = datetime.now().isoformat()
        try:
            cursor.execute(
                """INSERT INTO papers
                   (user_id, title, authors, file_path, file_size, page_count,
                    tags, category, reading_status, is_private, last_read_page,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    DEFAULT_USER_ID,
                    title,
                    authors if authors else None,
                    abs_path,  # 使用绝对路径，确保可访问
                    file_size,
                    page_count,
                    None,       # tags
                    None,       # category
                    "completed",  # reading_status 设为 completed（PDF 已存在）
                    0,          # is_private
                    0,          # last_read_page
                    now,        # created_at
                    now,        # updated_at
                ),
            )
            conn.commit()
            recovered += 1
            print(
                f"  [{i}/{len(pdf_files)}] 恢复成功: {filename}"
                f" -> \"{title[:50]}\" ({page_count}页, {file_size/1024:.1f}KB)"
            )
        except Exception as e:
            conn.rollback()
            failed += 1
            print(f"  [{i}/{len(pdf_files)}] 插入失败: {filename} -> {e}")

    conn.close()

    # 4. 汇总
    print("\n" + "=" * 60)
    print(f"恢复完成！总计 {len(pdf_files)} 个文件:")
    print(f"  成功恢复: {recovered}")
    print(f"  跳过（已存在）: {skipped}")
    print(f"  失败: {failed}")
    print("=" * 60)


if __name__ == "__main__":
    recover_papers()
