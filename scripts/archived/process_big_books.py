"""处理大文件书籍 - 限制页数"""
import json
from pathlib import Path
import pdfplumber
from book_targets import CORE_BOOKS, build_book_metadata

BOOKS_DIR = Path("papers/books_cache")
OUTPUT_JSON = "papers/books_big.json"

# 大书列表（>10MB）
BIG_BOOKS = [
    ("cognitive_neuroscience", "Principles_of_Neural_Science", 300),  # 只读300页
    ("cognitive_neuroscience", "The_Cognitive_Neurosciences", 200),
    ("cognitive_modeling_AI", "The_Computational_Brain", 200),
    ("cognitive_modeling_AI", "AI_A_Modern_Approach", 250),
    ("cognitive_modeling_AI", "How_to_Build_a_Brain", 200),
    ("psychological_science", "Memory_From_Mind_to_Molecules", 200),
    ("social_sciences", "Social_Cognition", 200),
    ("social_sciences", "Cultural_Origins_of_Human_Cognition", 200),
]

print("处理大文件书籍（限制页数）")
print("="*60)

all_chunks = []

for track, title, max_pages in BIG_BOOKS:
    book_path = BOOKS_DIR / f"{track}_{title}.pdf"

    if not book_path.exists():
        print(f"[SKIP] {title} - 文件不存在")
        continue

    file_size_mb = book_path.stat().st_size / 1024 / 1024
    print(f"\n[处理] {title}")
    print(f"  大小: {file_size_mb:.1f}MB, 限制: 前{max_pages}页")

    try:
        # 找到对应的book_info
        book_info = None
        for b in CORE_BOOKS[track]:
            if b["title"] == title:
                book_info = b
                break

        if not book_info:
            print(f"  跳过: 配置不存在")
            continue

        with pdfplumber.open(book_path) as pdf:
            total_pages = len(pdf.pages)
            read_pages = min(max_pages, total_pages)
            print(f"  总页数: {total_pages}, 读取: {read_pages}页")

            text = ""
            for i, page in enumerate(pdf.pages[:read_pages]):
                if i % 50 == 0 and i > 0:
                    print(f"    已读: {i}页...")
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

            if len(text) < 1000:
                print(f"  跳过: 文本太少({len(text)}字符)")
                continue

            print(f"  提取文本: {len(text)}字符")

            # 分块
            chunk_size = 2000
            chunk_count = 0
            for i in range(0, len(text), chunk_size):
                chunk_text = text[i:i+chunk_size]
                if len(chunk_text) < 500:
                    continue

                metadata = build_book_metadata(
                    {**book_info, "track": track},
                    f"Section {i//chunk_size + 1}",
                    0
                )

                all_chunks.append({
                    "title": f"{title.replace('_', ' ')} - Section {i//chunk_size + 1}",
                    "authors": [book_info["author"]],
                    "abstract": chunk_text[:500],
                    "fulltext": chunk_text,
                    "year": "",
                    "track": track,
                    "citation_count": 999,
                    "url": "",
                    "source": "book",
                    "tier": "core_textbook",
                    **metadata
                })
                chunk_count += 1

            print(f"  [OK] 生成 {chunk_count} chunks")

    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")

print(f"\n{'='*60}")
print(f"处理完成:")
print(f"  总chunks: {len(all_chunks)}")

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(all_chunks, f, ensure_ascii=False, indent=2)

print(f"  输出: {OUTPUT_JSON}")
print("="*60)
