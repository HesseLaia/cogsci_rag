"""
将处理好的书籍数据合并到论文数据集
去重 + 统计
"""

import json
from pathlib import Path

PAPERS_JSON = "data/all_papers_fulltext.json"
BOOKS_JSON = "data/books_processed.json"
OUTPUT_JSON = "data/all_papers_fulltext.json"  # 覆盖原文件（会备份）


def merge_datasets():
    """合并论文和书籍数据"""

    # 读取论文
    with open(PAPERS_JSON, "r", encoding="utf-8") as f:
        papers = json.load(f)
    print(f"现有论文: {len(papers)} 篇")

    # 读取书籍chunks
    if not Path(BOOKS_JSON).exists():
        print(f"错误: {BOOKS_JSON} 不存在")
        print("请先运行 book_processor_enhanced.py 处理书籍")
        return

    with open(BOOKS_JSON, "r", encoding="utf-8") as f:
        books = json.load(f)
    print(f"书籍chunks: {len(books)} 个")

    # 去重（基于title）
    existing_titles = {p["title"].lower().strip() for p in papers}
    new_books = []

    for book in books:
        title_key = book["title"].lower().strip()
        if title_key not in existing_titles:
            new_books.append(book)
            existing_titles.add(title_key)

    print(f"去重后新增: {len(new_books)} 个chunks")

    # 合并
    merged = papers + new_books

    # 备份原文件
    backup_path = Path(PAPERS_JSON).with_suffix(".backup.json")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    print(f"原文件已备份: {backup_path}")

    # 保存合并结果
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    # 统计
    print(f"\n{'='*50}")
    print(f"合并完成！")
    print(f"  论文: {len(papers)}")
    print(f"  书籍: {len(new_books)}")
    print(f"  总计: {len(merged)}")

    # 按track统计
    track_stats = {}
    for item in merged:
        track = item.get("track", "unknown")
        source = item.get("source", "paper")
        key = f"{track}_{source}"
        track_stats[key] = track_stats.get(key, 0) + 1

    print(f"\n按Track统计:")
    for key, count in sorted(track_stats.items()):
        print(f"  {key:<40} {count:>4}")

    print(f"\n输出: {OUTPUT_JSON}")
    print(f"{'='*50}")


if __name__ == "__main__":
    merge_datasets()
