"""重建 paper_text_blocks 表数据

对所有论文重新提取文本块，解决 paper_text_blocks 表为空导致对话失败的问题。
逻辑参考 app/services/pdf_service.py 的 extract_text_blocks() 方法。
"""
import os
import sqlite3
import pdfplumber


BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BACKEND_DIR, "chatpdf.db")
UPLOADS_DIR = os.path.join(BACKEND_DIR, "uploads")


def extract_text_blocks(file_path: str) -> list[dict]:
    """从 PDF 提取文本块（同步版本，逻辑与 pdf_service.py 一致）"""
    blocks = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                chars = page.chars
                if not chars:
                    continue

                # 按 y 坐标分组（同一行的字符）
                lines = {}
                for char in chars:
                    y_key = round(char.get("top", 0), 1)
                    if y_key not in lines:
                        lines[y_key] = []
                    lines[y_key].append(char)

                # 对每一行排序并合并成文本块
                for y_key in sorted(lines.keys()):
                    line_chars = sorted(lines[y_key], key=lambda c: c.get("x0", 0))
                    if not line_chars:
                        continue

                    text = "".join(c.get("text", "") for c in line_chars).strip()
                    if not text:
                        continue

                    x0 = min(c.get("x0", 0) for c in line_chars)
                    y0 = min(c.get("top", 0) for c in line_chars)
                    x1 = max(c.get("x1", 0) for c in line_chars)
                    y1 = max(c.get("bottom", 0) for c in line_chars)

                    blocks.append({
                        "page_number": page_num,
                        "text": text,
                        "x0": x0,
                        "y0": y0,
                        "x1": x1,
                        "y1": y1,
                        "block_type": "text",
                    })
    except Exception as e:
        print(f"  [ERROR] 提取失败: {e}")

    return blocks


def resolve_pdf_path(file_path: str) -> str | None:
    """解析 PDF 文件的实际路径（兼容绝对路径和相对路径）"""
    # 1. 绝对路径直接检查
    if os.path.isabs(file_path) and os.path.isfile(file_path):
        return file_path

    # 2. 相对于 uploads 目录
    rel_path = os.path.join(UPLOADS_DIR, file_path)
    if os.path.isfile(rel_path):
        return rel_path

    # 3. 仅文件名，在 uploads 目录下查找
    filename = os.path.basename(file_path)
    filename_path = os.path.join(UPLOADS_DIR, filename)
    if os.path.isfile(filename_path):
        return filename_path

    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    # 查询所有论文
    papers = cur.execute(
        "SELECT id, file_path, title FROM papers ORDER BY id"
    ).fetchall()
    print(f"共找到 {len(papers)} 篇论文\n")

    total_inserted = 0
    total_errors = 0

    for paper_id, file_path, title in papers:
        print(f"[Paper {paper_id}] {title[:60] if title else '(无标题)'}")
        print(f"  file_path: {file_path}")

        # 先清除该论文已有的文本块（避免重复）
        cur.execute("DELETE FROM paper_text_blocks WHERE paper_id = ?", (paper_id,))

        # 解析 PDF 路径
        actual_path = resolve_pdf_path(file_path)
        if not actual_path:
            print(f"  [SKIP] PDF 文件不存在: {file_path}")
            total_errors += 1
            continue

        # 提取文本块
        blocks = extract_text_blocks(actual_path)
        if not blocks:
            print(f"  [WARN] 提取到 0 个文本块")
            total_errors += 1
            continue

        # 批量插入
        rows = [
            (paper_id, b["page_number"], b["text"], b["x0"], b["y0"], b["x1"], b["y1"], b["block_type"])
            for b in blocks
        ]
        cur.executemany(
            "INSERT INTO paper_text_blocks (paper_id, page_number, text, x0, y0, x1, y1, block_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        total_inserted += len(rows)
        print(f"  [OK] 插入 {len(rows)} 个文本块")

    conn.commit()
    conn.close()

    print(f"\n{'='*50}")
    print(f"完成！共插入 {total_inserted} 个文本块，{total_errors} 篇论文有问题")


if __name__ == "__main__":
    main()
