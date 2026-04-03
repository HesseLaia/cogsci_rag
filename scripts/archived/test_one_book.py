"""测试处理单本书"""
import sys
from pathlib import Path

print("=" * 60)
print("测试书籍处理")
print("=" * 60)

# 测试导入
print("\n1. 测试导入...")
try:
    from book_processor_enhanced import process_book, BOOKS_DIR, HAS_PDF, HAS_EPUB
    from book_targets import CORE_BOOKS
    print(f"  [OK] 导入成功")
    print(f"  PDF支持: {HAS_PDF}")
    print(f"  EPUB支持: {HAS_EPUB}")
except Exception as e:
    print(f"  [ERROR] 导入失败: {e}")
    sys.exit(1)

# 测试文件查找
print("\n2. 测试文件查找...")
print(f"  书籍目录: {BOOKS_DIR}")
print(f"  目录存在: {BOOKS_DIR.exists()}")

if BOOKS_DIR.exists():
    all_books = list(BOOKS_DIR.glob("*.pdf")) + list(BOOKS_DIR.glob("*.epub"))
    print(f"  找到 {len(all_books)} 本书")
    for b in all_books[:3]:
        print(f"    - {b.name}")

# 测试处理一本小书
print("\n3. 测试处理 The Conscious Mind...")
try:
    book_info = CORE_BOOKS['philosophy'][0]
    book_path = BOOKS_DIR / f"philosophy_{book_info['title']}.pdf"

    print(f"  文件路径: {book_path}")
    print(f"  文件存在: {book_path.exists()}")

    if book_path.exists():
        file_size = book_path.stat().st_size / 1024 / 1024
        print(f"  文件大小: {file_size:.1f} MB")

        print(f"  开始处理...")
        chunks = process_book(book_path, book_info, 'philosophy')
        print(f"  [OK] 成功! 生成 {len(chunks)} 个chunks")

        if chunks:
            print(f"\n  示例chunk:")
            print(f"    标题: {chunks[0]['metadata']['book_title']}")
            print(f"    章节: {chunks[0]['metadata']['chapter']}")
            print(f"    文本长度: {len(chunks[0]['text'])} 字符")
    else:
        print(f"  [ERROR] 文件不存在")

except Exception as e:
    print(f"  [ERROR] 处理失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
