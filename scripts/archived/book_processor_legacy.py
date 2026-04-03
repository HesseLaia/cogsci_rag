"""
书籍PDF处理：章节拆分 + 精华提取
策略：防止教材噪声，只提取有价值部分
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Tuple
import pdfplumber
from book_targets import CORE_BOOKS, EXTRACTION_STRATEGIES, build_book_metadata


# ── 配置 ──────────────────────────────────────────────────────
BOOKS_DIR = Path("papers/books_cache")
OUTPUT_JSON = "papers/books_processed.json"

MAX_CHUNK_SIZE = 2000  # 字符
OVERLAP = 200


# ── 章节识别 ──────────────────────────────────────────────────
CHAPTER_PATTERNS = [
    r'^Chapter\s+\d+',           # Chapter 1
    r'^\d+\.\s+[A-Z]',           # 1. Introduction
    r'^CHAPTER\s+[IVX]+',        # CHAPTER I
    r'^Part\s+[IVX]+',           # Part I
]

SUMMARY_PATTERNS = [
    r'summary',
    r'key\s+points?',
    r'conclusion',
    r'overview',
    r'in\s+brief',
    r'chapter\s+review',
]


def detect_chapters(text: str) -> List[Tuple[str, int]]:
    """
    检测章节标题和位置
    返回: [(chapter_title, start_position), ...]
    """
    chapters = []
    lines = text.split('\n')
    pos = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            pos += len(line) + 1
            continue

        # 匹配章节标题
        for pattern in CHAPTER_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                chapters.append((stripped, pos))
                break

        pos += len(line) + 1

    return chapters


def is_summary_section(text: str) -> bool:
    """判断是否是summary/key points章节"""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in SUMMARY_PATTERNS)


# ── 文本提取 ──────────────────────────────────────────────────
def extract_pdf_text(pdf_path: Path, max_pages: int = None) -> str:
    """提取PDF文本（带页码限制）"""
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            pages_to_read = pdf.pages[:max_pages] if max_pages else pdf.pages
            for page in pages_to_read:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"  PDF提取失败: {e}")
        return ""


def split_into_chapters(text: str) -> Dict[str, str]:
    """
    按章节拆分文本
    返回: {chapter_title: chapter_text}
    """
    chapters = detect_chapters(text)

    if not chapters:
        # 如果没检测到章节，按页数粗略拆分
        print("  未检测到章节标记，按固定长度拆分")
        return split_by_length(text)

    chapter_dict = {}
    for i, (title, start_pos) in enumerate(chapters):
        end_pos = chapters[i + 1][1] if i + 1 < len(chapters) else len(text)
        chapter_text = text[start_pos:end_pos].strip()
        chapter_dict[title] = chapter_text

    return chapter_dict


def split_by_length(text: str, chunk_size: int = 8000) -> Dict[str, str]:
    """备用方案：按固定长度拆分"""
    chunks = {}
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i:i + chunk_size]
        chunks[f"Section {i // chunk_size + 1}"] = chunk_text
    return chunks


# ── 精华提取 ──────────────────────────────────────────────────
def extract_highlights(chapter_text: str) -> str:
    """
    从章节中提取精华：
    1. Summary段落
    2. Key Points列表
    3. 加粗/斜体的关键概念（需OCR或特殊标记）
    """
    lines = chapter_text.split('\n')
    highlights = []
    in_summary = False

    for line in lines:
        stripped = line.strip()

        # 检测summary开始
        if is_summary_section(stripped):
            in_summary = True
            highlights.append(stripped)
            continue

        # summary结束条件（遇到新的大标题）
        if in_summary and any(re.match(p, stripped, re.IGNORECASE)
                             for p in CHAPTER_PATTERNS):
            in_summary = False

        if in_summary:
            highlights.append(stripped)

        # 提取带编号的要点（bullet points）
        if re.match(r'^[\*\-•]\s+|^\d+\.\s+', stripped):
            highlights.append(stripped)

    return '\n'.join(highlights) if highlights else chapter_text[:2000]


# ── 智能分块 ──────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = MAX_CHUNK_SIZE,
               overlap: int = OVERLAP) -> List[str]:
    """
    智能分块：尽量在段落边界切分
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # 寻找段落边界（双换行）
        boundary = text.rfind('\n\n', start, end)
        if boundary == -1 or boundary <= start:
            # 找不到段落边界，找单换行
            boundary = text.rfind('\n', start, end)

        if boundary == -1 or boundary <= start:
            # 还是找不到，强制切分
            boundary = end

        chunks.append(text[start:boundary].strip())
        start = boundary - overlap if boundary > start + overlap else boundary

    return chunks


# ── 主处理流程 ────────────────────────────────────────────────
def process_book(pdf_path: Path, book_info: Dict, track: str) -> List[Dict]:
    """
    处理单本书：
    1. 提取文本
    2. 按章节拆分
    3. 根据策略过滤/提取
    4. 分块 + metadata
    """
    print(f"\n处理: {book_info['title']}")

    # 检查目标章节
    target_chapters = book_info.get("target_chapters", [])
    strategy_name = book_info.get("extraction_strategy", "章节级")
    strategy = EXTRACTION_STRATEGIES.get(strategy_name, EXTRACTION_STRATEGIES["章节级"])

    print(f"  策略: {strategy_name}")

    # 提取全文（限制页数，避免太大）
    max_pages = 500 if strategy_name == "精读模式" else 300
    full_text = extract_pdf_text(pdf_path, max_pages=max_pages)

    if not full_text or len(full_text) < 500:
        print(f"  ✗ 文本提取失败或内容过少")
        return []

    print(f"  提取文本: {len(full_text)} 字符")

    # 章节拆分
    chapters = split_into_chapters(full_text)
    print(f"  检测到 {len(chapters)} 个章节")

    # 过滤章节（如果有目标章节列表）
    if isinstance(target_chapters, list) and len(target_chapters) > 0:
        filtered_chapters = {}
        for target in target_chapters:
            for ch_title, ch_text in chapters.items():
                if target.lower() in ch_title.lower():
                    filtered_chapters[ch_title] = ch_text
                    print(f"  匹配章节: {ch_title}")
        chapters = filtered_chapters if filtered_chapters else chapters

    # 根据策略处理章节
    processed_chunks = []

    for ch_title, ch_text in chapters.items():
        # 应用提取策略
        if "summaries" in strategy["include_elements"]:
            ch_text = extract_highlights(ch_text)

        # 分块
        chunks = chunk_text(ch_text, chunk_size=strategy["chunk_size"],
                          overlap=strategy["overlap"])

        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 200:  # 过滤太短的块
                continue

            metadata = build_book_metadata(
                {**book_info, "track": track},
                ch_title,
                i
            )

            processed_chunks.append({
                "text": chunk,
                "metadata": metadata
            })

    print(f"  ✓ 生成 {len(processed_chunks)} 个chunks")
    return processed_chunks


# ── 批量处理所有书籍 ──────────────────────────────────────────
def process_all_books():
    """处理所有已下载的书籍"""

    all_chunks = []

    for track, books in CORE_BOOKS.items():
        print(f"\n{'='*60}")
        print(f"Track: {track}")
        print(f"{'='*60}")

        for book_info in books:
            title = book_info["title"]
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_"
                               for c in title)[:50]
            pdf_path = BOOKS_DIR / f"{track}_{safe_title}.pdf"

            if not pdf_path.exists():
                print(f"\n跳过（未下载）: {title}")
                continue

            chunks = process_book(pdf_path, book_info, track)
            all_chunks.extend(chunks)

    # 保存为JSON
    output = []
    for chunk in all_chunks:
        output.append({
            "title": f"{chunk['metadata']['book_title']} - {chunk['metadata']['chapter']}",
            "authors": [chunk['metadata']['author']],
            "abstract": chunk['text'][:500] + "...",  # 摘要用前500字
            "fulltext": chunk['text'],
            "year": "",
            "track": chunk['metadata']['track'],
            "citation_count": 999,
            "url": "",
            "source": "book",
            "tier": "core_textbook",
            **chunk['metadata']
        })

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"""
{'='*60}
处理完成！
  书籍chunks: {len(all_chunks)}
  输出文件: {OUTPUT_JSON}

下一步：
  1. 将 books_processed.json 合并到 all_papers_fulltext.json
  2. 重建向量库（或增量添加）
{'='*60}
    """)


if __name__ == "__main__":
    process_all_books()
