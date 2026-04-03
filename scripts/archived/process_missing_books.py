"""处理缺失的2本书"""
import json
from pathlib import Path
import pdfplumber
from book_targets import CORE_BOOKS, build_book_metadata

BOOKS_DIR = Path("papers/books_cache")
OUTPUT_JSON = "papers/books_missing.json"

print("处理缺失的2本书")
print("="*60)

all_chunks = []

# 1. Principles of Neural Science (118MB超大书)
print("\n[1/2] Principles of Neural Science")
book_path = BOOKS_DIR / "cognitive_neuroscience_Principles_of_Neural_Science.pdf"

if book_path.exists():
    file_size = book_path.stat().st_size / 1024 / 1024
    print(f"  大小: {file_size:.1f}MB")
    print(f"  策略: 只读前200页 + 搜索关键章节")

    try:
        book_info = CORE_BOOKS['cognitive_neuroscience'][0]

        with pdfplumber.open(book_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"  总页数: {total_pages}")

            # 策略：读前200页（通常是基础和认知部分）
            text = ""
            for i in range(min(200, total_pages)):
                if i % 50 == 0:
                    print(f"    读取: {i}页...")
                page_text = pdf.pages[i].extract_text()
                if page_text:
                    text += page_text + "\n"

            print(f"  提取文本: {len(text)}字符")

            # 分块
            chunk_size = 2000
            chunk_count = 0
            for i in range(0, len(text), chunk_size):
                chunk_text = text[i:i+chunk_size]
                if len(chunk_text) < 500:
                    continue

                metadata = build_book_metadata(
                    {**book_info, "track": "cognitive_neuroscience"},
                    f"Section {i//chunk_size + 1}",
                    0
                )

                all_chunks.append({
                    "title": f"Principles of Neural Science - Section {i//chunk_size + 1}",
                    "authors": [book_info["author"]],
                    "abstract": chunk_text[:500],
                    "fulltext": chunk_text,
                    "year": "",
                    "track": "cognitive_neuroscience",
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
else:
    print(f"  [SKIP] 文件不存在")

# 2. Cultural Origins of Human Cognition
print("\n[2/2] Cultural Origins of Human Cognition")
book_path = BOOKS_DIR / "social_sciences_Cultural_Origins_of_Human_Cognition.pdf"

if book_path.exists():
    file_size = book_path.stat().st_size / 1024 / 1024
    print(f"  大小: {file_size:.1f}MB")
    print(f"  策略: 读取全部内容（文件适中）")

    try:
        book_info = None
        for b in CORE_BOOKS['social_sciences']:
            if 'Cultural_Origins' in b['title']:
                book_info = b
                break

        if not book_info:
            print(f"  [ERROR] 配置未找到")
        else:
            with pdfplumber.open(book_path) as pdf:
                total_pages = len(pdf.pages)
                print(f"  总页数: {total_pages}")

                text = ""
                for i in range(total_pages):
                    if i % 50 == 0:
                        print(f"    读取: {i}页...")
                    page_text = pdf.pages[i].extract_text()
                    if page_text:
                        text += page_text + "\n"

                print(f"  提取文本: {len(text)}字符")

                # 分块
                chunk_size = 2000
                chunk_count = 0
                for i in range(0, len(text), chunk_size):
                    chunk_text = text[i:i+chunk_size]
                    if len(chunk_text) < 500:
                        continue

                    metadata = build_book_metadata(
                        {**book_info, "track": "social_sciences"},
                        f"Section {i//chunk_size + 1}",
                        0
                    )

                    all_chunks.append({
                        "title": f"Cultural Origins of Human Cognition - Section {i//chunk_size + 1}",
                        "authors": [book_info["author"]],
                        "abstract": chunk_text[:500],
                        "fulltext": chunk_text,
                        "year": "",
                        "track": "social_sciences",
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
else:
    print(f"  [SKIP] 文件不存在")

print(f"\n{'='*60}")
print(f"处理完成:")
print(f"  总chunks: {len(all_chunks)}")

if all_chunks:
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    print(f"  输出: {OUTPUT_JSON}")

    # 自动合并
    print(f"\n合并到主文件...")
    try:
        processed = json.load(open('papers/books_processed.json', encoding='utf-8'))
        existing_titles = {d['title'] for d in processed}

        new_count = 0
        for chunk in all_chunks:
            if chunk['title'] not in existing_titles:
                processed.append(chunk)
                existing_titles.add(chunk['title'])
                new_count += 1

        with open('papers/books_processed.json', 'w', encoding='utf-8') as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)

        print(f"  新增: {new_count} chunks")
        print(f"  总计: {len(processed)} chunks")
        print(f"  [OK] 已合并")
    except Exception as e:
        print(f"  [ERROR] 合并失败: {e}")
else:
    print(f"  无新数据")

print("="*60)
