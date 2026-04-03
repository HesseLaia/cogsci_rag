"""简化版书籍处理 - 只处理小文件，快速测试"""
import json
from pathlib import Path
import pdfplumber
from book_targets import CORE_BOOKS, build_book_metadata

BOOKS_DIR = Path("papers/books_cache")
OUTPUT_JSON = "papers/books_test.json"

print("简化处理 - 只处理小于10MB的PDF")
print("="*60)

all_chunks = []
processed_count = 0

for track, books in CORE_BOOKS.items():
    for book_info in books:
        title = book_info["title"]
        book_path = BOOKS_DIR / f"{track}_{title}.pdf"

        if not book_path.exists():
            continue

        file_size_mb = book_path.stat().st_size / 1024 / 1024

        if file_size_mb > 10:
            print(f"[SKIP] {title} ({file_size_mb:.1f}MB - 太大)")
            continue

        print(f"[处理] {title} ({file_size_mb:.1f}MB)")

        try:
            with pdfplumber.open(book_path) as pdf:
                # 只读前50页
                text = ""
                for page in pdf.pages[:50]:
                    text += (page.extract_text() or "") + "\n"

                if len(text) < 1000:
                    print(f"  跳过: 文本太少")
                    continue

                # 简单分块：每2000字符一块
                chunk_size = 2000
                for i in range(0, len(text), chunk_size):
                    chunk_text = text[i:i+chunk_size]
                    if len(chunk_text) < 500:
                        continue

                    metadata = build_book_metadata(
                        {**book_info, "track": track},
                        f"Part {i//chunk_size + 1}",
                        0
                    )

                    all_chunks.append({
                        "title": f"{book_info['title']} - Part {i//chunk_size + 1}",
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

                print(f"  生成 {len([c for c in all_chunks if book_info['title'] in c['title']])} chunks")
                processed_count += 1

        except Exception as e:
            print(f"  错误: {e}")

print(f"\n处理完成:")
print(f"  处理书籍: {processed_count}本")
print(f"  总chunks: {len(all_chunks)}")

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(all_chunks, f, ensure_ascii=False, indent=2)

print(f"  输出: {OUTPUT_JSON}")
