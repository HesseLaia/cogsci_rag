"""
增强版书籍处理器：支持 PDF + EPUB + MOBI
自动识别格式并提取
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Tuple

# PDF 处理
try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False
    print("警告: pdfplumber 未安装，无法处理PDF")

# EPUB 处理
try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    HAS_EPUB = True
except ImportError:
    HAS_EPUB = False
    print("警告: ebooklib/beautifulsoup4 未安装，无法处理EPUB")
    print("安装方法: pip install ebooklib beautifulsoup4")

from book_targets import CORE_BOOKS, EXTRACTION_STRATEGIES, build_book_metadata


# ── 配置 ──────────────────────────────────────────────────────
BOOKS_DIR = Path("data/books_cache")
OUTPUT_JSON = "data/books_processed.json"

MAX_CHUNK_SIZE = 2000
OVERLAP = 200


# ── EPUB 处理 ──────────────────────────────────────────────────
def extract_epub_text(epub_path: Path) -> str:
    """从 EPUB 提取纯文本"""
    if not HAS_EPUB:
        print(f"  [X] 无法处理EPUB，请安装: pip install ebooklib beautifulsoup4")
        return ""

    try:
        book = epub.read_epub(str(epub_path))
        text = ""

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                content = item.get_content()
                soup = BeautifulSoup(content, 'html.parser')
                # 提取文本，保留段落结构
                paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3'])
                for p in paragraphs:
                    text += p.get_text() + "\n\n"

        return text.strip()
    except Exception as e:
        print(f"  EPUB提取失败: {e}")
        return ""


def extract_epub_chapters(epub_path: Path) -> Dict[str, str]:
    """从 EPUB 按章节提取（更精确）"""
    if not HAS_EPUB:
        return {}

    try:
        book = epub.read_epub(str(epub_path))
        chapters = {}

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # 尝试从文件名推断章节
                filename = item.get_name()
                content = item.get_content()
                soup = BeautifulSoup(content, 'html.parser')

                # 查找章节标题
                title_tag = soup.find(['h1', 'h2'])
                if title_tag:
                    chapter_title = title_tag.get_text().strip()
                else:
                    chapter_title = filename

                # 提取文本
                text = ""
                for p in soup.find_all(['p', 'h3', 'h4']):
                    text += p.get_text() + "\n\n"

                if len(text.strip()) > 100:  # 过滤太短的
                    chapters[chapter_title] = text.strip()

        return chapters
    except Exception as e:
        print(f"  EPUB章节提取失败: {e}")
        return {}


# ── PDF 处理（从原版复制） ────────────────────────────────────
def extract_pdf_text(pdf_path: Path, max_pages: int = None) -> str:
    """提取PDF文本"""
    if not HAS_PDF:
        print(f"  [X] 无法处理PDF，请安装: pip install pdfplumber")
        return ""

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


# ── 通用章节识别 ──────────────────────────────────────────────
CHAPTER_PATTERNS = [
    r'^Chapter\s+\d+',
    r'^\d+\.\s+[A-Z]',
    r'^CHAPTER\s+[IVX]+',
    r'^Part\s+[IVX]+',
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
    """检测章节标题和位置"""
    chapters = []
    lines = text.split('\n')
    pos = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            pos += len(line) + 1
            continue

        for pattern in CHAPTER_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                chapters.append((stripped, pos))
                break

        pos += len(line) + 1

    return chapters


def is_summary_section(text: str) -> bool:
    """判断是否是summary章节"""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in SUMMARY_PATTERNS)


def split_into_chapters(text: str) -> Dict[str, str]:
    """按章节拆分文本"""
    chapters = detect_chapters(text)

    if not chapters:
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


def extract_highlights(chapter_text: str) -> str:
    """提取精华：Summary + Key Points"""
    lines = chapter_text.split('\n')
    highlights = []
    in_summary = False

    for line in lines:
        stripped = line.strip()

        if is_summary_section(stripped):
            in_summary = True
            highlights.append(stripped)
            continue

        if in_summary and any(re.match(p, stripped, re.IGNORECASE)
                             for p in CHAPTER_PATTERNS):
            in_summary = False

        if in_summary:
            highlights.append(stripped)

        if re.match(r'^[\*\-•]\s+|^\d+\.\s+', stripped):
            highlights.append(stripped)

    return '\n'.join(highlights) if highlights else chapter_text[:2000]


def chunk_text(text: str, chunk_size: int = MAX_CHUNK_SIZE,
               overlap: int = OVERLAP) -> List[str]:
    """智能分块"""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        boundary = text.rfind('\n\n', start, end)
        if boundary == -1 or boundary <= start:
            boundary = text.rfind('\n', start, end)

        if boundary == -1 or boundary <= start:
            boundary = end

        chunks.append(text[start:boundary].strip())
        start = boundary - overlap if boundary > start + overlap else boundary

    return chunks


# ── 主处理函数（支持多格式）───────────────────────────────────
def process_book(book_path: Path, book_info: Dict, track: str) -> List[Dict]:
    """处理单本书（自动识别格式）"""
    print(f"\n处理: {book_info['title']}")

    # 识别格式
    suffix = book_path.suffix.lower()
    print(f"  格式: {suffix}")

    # 提取文本
    if suffix == '.pdf':
        if not HAS_PDF:
            print(f"  [X] 跳过：pdfplumber 未安装")
            return []
        strategy_name = book_info.get("extraction_strategy", "章节级")
        strategy = EXTRACTION_STRATEGIES.get(strategy_name, EXTRACTION_STRATEGIES["章节级"])
        max_pages = 500 if strategy_name == "精读模式" else 300
        full_text = extract_pdf_text(book_path, max_pages=max_pages)
        chapters = split_into_chapters(full_text)

    elif suffix == '.epub':
        if not HAS_EPUB:
            print(f"  [X] 跳过：ebooklib 未安装")
            return []
        strategy_name = book_info.get("extraction_strategy", "章节级")
        strategy = EXTRACTION_STRATEGIES.get(strategy_name, EXTRACTION_STRATEGIES["章节级"])
        # EPUB 通常已经按章节组织好了
        chapters = extract_epub_chapters(book_path)
        if not chapters:
            # fallback: 提取全文再拆分
            full_text = extract_epub_text(book_path)
            chapters = split_into_chapters(full_text)

    else:
        print(f"  [X] 不支持的格式: {suffix}")
        return []

    if not chapters:
        print(f"  [X] 文本提取失败")
        return []

    print(f"  检测到 {len(chapters)} 个章节")

    # 过滤目标章节
    target_chapters = book_info.get("target_chapters", [])
    if isinstance(target_chapters, list) and len(target_chapters) > 0:
        filtered_chapters = {}
        for target in target_chapters:
            for ch_title, ch_text in chapters.items():
                if target.lower() in ch_title.lower():
                    filtered_chapters[ch_title] = ch_text
                    print(f"  匹配章节: {ch_title}")
        chapters = filtered_chapters if filtered_chapters else chapters

    # 处理章节
    processed_chunks = []
    strategy = EXTRACTION_STRATEGIES.get(strategy_name, EXTRACTION_STRATEGIES["章节级"])

    for ch_title, ch_text in chapters.items():
        if "summaries" in strategy["include_elements"]:
            ch_text = extract_highlights(ch_text)

        chunks = chunk_text(ch_text, chunk_size=strategy["chunk_size"],
                          overlap=strategy["overlap"])

        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 200:
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

    print(f"  [OK] 生成 {len(processed_chunks)} 个chunks")
    return processed_chunks


# ── 批量处理 ──────────────────────────────────────────────────
def process_all_books():
    """处理所有已下载的书籍（支持PDF+EPUB）"""

    all_chunks = []

    for track, books in CORE_BOOKS.items():
        print(f"\n{'='*60}")
        print(f"Track: {track}")
        print(f"{'='*60}")

        for book_info in books:
            title = book_info["title"]
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_"
                               for c in title)[:50]

            # 按优先级查找：PDF > EPUB > MOBI
            book_path = None
            for ext in ['.pdf', '.epub', '.mobi']:
                candidate = BOOKS_DIR / f"{track}_{safe_title}{ext}"
                if candidate.exists():
                    book_path = candidate
                    break

            if not book_path:
                print(f"\n跳过（未下载）: {title}")
                continue

            try:
                chunks = process_book(book_path, book_info, track)
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"  [ERROR] 处理失败: {e}")
                print(f"  继续处理下一本...")

    # 保存为JSON
    output = []
    for chunk in all_chunks:
        output.append({
            "title": f"{chunk['metadata']['book_title']} - {chunk['metadata']['chapter']}",
            "authors": [chunk['metadata']['author']],
            "abstract": chunk['text'][:500] + "...",
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

支持的格式: PDF, EPUB
下一步：python merge_books.py
{'='*60}
    """)


if __name__ == "__main__":
    # 检查依赖
    print("检查依赖...")
    if HAS_PDF:
        print("  [OK] PDF支持 (pdfplumber)")
    if HAS_EPUB:
        print("  [OK] EPUB支持 (ebooklib)")

    if not HAS_PDF and not HAS_EPUB:
        print("\n错误：至少需要安装一个库：")
        print("  pip install pdfplumber              # PDF支持")
        print("  pip install ebooklib beautifulsoup4 # EPUB支持")
        exit(1)

    print()
    process_all_books()
