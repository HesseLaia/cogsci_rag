"""
自动化重构脚本
执行项目结构重组、文件移动、路径归档

运行前请确保：
1. 已提交所有更改到Git
2. 已创建 refactor 分支
3. 仔细阅读了 REFACTOR_PLAN.md

运行方式：python refactor.py --execute
（不带 --execute 参数只会预览操作，不会真正执行）
"""

import os
import shutil
import argparse
from pathlib import Path
from typing import List, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 操作记录
operations = []

def log_operation(op_type: str, source: str, target: str = ""):
    """记录操作"""
    operations.append((op_type, source, target))
    if target:
        print(f"[{op_type}] {source} -> {target}")
    else:
        print(f"[{op_type}] {source}")


def create_directories(dry_run: bool = True):
    """创建新目录结构"""
    directories = [
        "src",
        "src/rag",
        "src/crawlers", 
        "src/processors",
        "src/config",
        "data",
        "data/processed",
        "data/cache",
        "data/archives",
        "data/archives/tracks",
        "docs",
        "scripts",
        "scripts/archived",
    ]
    
    print("\n=== Phase 1: 创建目录结构 ===")
    for dir_path in directories:
        full_path = PROJECT_ROOT / dir_path
        if not full_path.exists():
            log_operation("MKDIR", str(dir_path))
            if not dry_run:
                full_path.mkdir(parents=True, exist_ok=True)
                # 创建 __init__.py
                if dir_path.startswith("src/") and not dir_path.endswith("config"):
                    init_file = full_path / "__init__.py"
                    init_file.write_text('"""Package initialization."""\n', encoding='utf-8')


def move_file(source: str, target: str, dry_run: bool = True):
    """移动文件"""
    src_path = PROJECT_ROOT / source
    tgt_path = PROJECT_ROOT / target
    
    if src_path.exists():
        log_operation("MOVE", source, target)
        if not dry_run:
            tgt_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(tgt_path))
        return True
    else:
        print(f"[SKIP] {source} (不存在)")
        return False


def copy_file(source: str, target: str, dry_run: bool = True):
    """复制文件"""
    src_path = PROJECT_ROOT / source
    tgt_path = PROJECT_ROOT / target
    
    if src_path.exists():
        log_operation("COPY", source, target)
        if not dry_run:
            tgt_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_path), str(tgt_path))
        return True
    return False


def archive_file(source: str, archive_dir: str, dry_run: bool = True):
    """归档文件"""
    src_path = PROJECT_ROOT / source
    filename = Path(source).name
    target = f"{archive_dir}/{filename}"
    
    if src_path.exists():
        log_operation("ARCHIVE", source, target)
        if not dry_run:
            tgt_path = PROJECT_ROOT / target
            tgt_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(tgt_path))
        return True
    return False


def refactor_code_files(dry_run: bool = True):
    """重构核心代码文件"""
    print("\n=== Phase 2: 移动核心代码 ===")
    
    # 暂时不移动，需要重构后再移动
    # 这里只是标记需要重构的文件
    print("[TODO] cogsci_rag.py 需要拆分为:")
    print("  - src/rag/retriever.py")
    print("  - src/rag/generator.py")
    print("  - src/rag/__init__.py")
    print("  - cli.py (新命令行入口)")


def move_crawlers(dry_run: bool = True):
    """移动爬虫模块"""
    print("\n=== Phase 3: 移动爬虫模块 ===")
    
    crawler_files = [
        ("cogsci_crawler.py", "src/crawlers/paper_metadata_crawler.py"),
        ("spider.py", "src/crawlers/fulltext_spider.py"),
        ("enrich_papers.py", "src/crawlers/paper_enricher.py"),
        ("book_crawler.py", "src/crawlers/book_crawler.py"),
        ("paper_crawler.py", "src/crawlers/unified_crawler.py"),
    ]
    
    for source, target in crawler_files:
        move_file(source, target, dry_run)


def move_processors(dry_run: bool = True):
    """移动处理器模块"""
    print("\n=== Phase 4: 移动处理器模块 ===")
    
    processor_files = [
        ("book_processor_enhanced.py", "src/processors/book_processor.py"),
        ("merge_books.py", "src/processors/data_merger.py"),
    ]
    
    for source, target in processor_files:
        move_file(source, target, dry_run)


def move_config(dry_run: bool = True):
    """移动配置文件"""
    print("\n=== Phase 5: 移动配置文件 ===")
    
    move_file("book_targets.py", "src/config/book_targets.py", dry_run)
    
    # 创建统一配置文件
    settings_content = '''"""统一配置管理"""
from pathlib import Path
import os

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 数据路径
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
ARCHIVES_DIR = DATA_DIR / "archives"

# 主数据文件
PAPERS_JSON = PROCESSED_DIR / "all_papers_fulltext.json"
BOOKS_JSON = PROCESSED_DIR / "books_processed.json"

# 缓存路径
BOOKS_CACHE_DIR = CACHE_DIR / "books"
PDFS_CACHE_DIR = CACHE_DIR / "pdfs"

# 向量库路径
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION = "cogsci_papers"

# 嵌入模型
EMBED_MODEL = "all-MiniLM-L6-v2"

# OpenRouter API配置（从环境变量读取）
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# 检索配置
TOP_K = 6
MIN_CITATIONS = 10

# Track名称映射
TRACK_NAMES = {
    "psychological_science": "心理科学",
    "cognitive_neuroscience": "认知神经科学",
    "cognitive_modeling_AI": "认知建模与AI",
    "social_sciences": "社会科学与人文",
    "linguistics": "语言学",
    "philosophy": "心智哲学",
}
'''
    
    settings_path = PROJECT_ROOT / "src/config/settings.py"
    if not dry_run:
        log_operation("CREATE", "src/config/settings.py")
        settings_path.write_text(settings_content, encoding='utf-8')
    else:
        log_operation("CREATE", "src/config/settings.py")


def move_data_files(dry_run: bool = True):
    """整理数据文件"""
    print("\n=== Phase 6: 整理数据文件 ===")
    
    # 移动核心数据
    move_file("papers/all_papers_fulltext.json", "data/processed/all_papers_fulltext.json", dry_run)
    move_file("papers/books_processed.json", "data/processed/books_processed.json", dry_run)
    
    # 移动缓存目录
    if (PROJECT_ROOT / "papers/books_cache").exists():
        log_operation("MOVE", "papers/books_cache/", "data/cache/books/")
        if not dry_run:
            shutil.move(str(PROJECT_ROOT / "papers/books_cache"), 
                       str(PROJECT_ROOT / "data/cache/books"))
    
    if (PROJECT_ROOT / "papers/pdfs_cache").exists():
        log_operation("MOVE", "papers/pdfs_cache/", "data/cache/pdfs/")
        if not dry_run:
            shutil.move(str(PROJECT_ROOT / "papers/pdfs_cache"),
                       str(PROJECT_ROOT / "data/cache/pdfs"))
    
    if (PROJECT_ROOT / "papers/pdfs").exists():
        log_operation("MOVE", "papers/pdfs/", "data/cache/pdfs_fulltext/")
        if not dry_run:
            shutil.move(str(PROJECT_ROOT / "papers/pdfs"),
                       str(PROJECT_ROOT / "data/cache/pdfs_fulltext"))
    
    # 归档备份文件
    print("\n  归档备份文件:")
    archive_file("papers/all_papers_fulltext.backup.json", "data/archives", dry_run)
    archive_file("papers/all_papers_fulltext.backup2.json", "data/archives", dry_run)
    archive_file("papers/books_all_merged.json", "data/archives", dry_run)
    
    # 归档中间产物
    print("\n  归档中间产物:")
    archive_file("papers/all_papers.json", "data/archives", dry_run)
    archive_file("papers/all_papers_clean.json", "data/archives", dry_run)
    archive_file("papers/books_big.json", "data/archives", dry_run)
    archive_file("papers/books_test.json", "data/archives", dry_run)
    
    # 归档track分类文件
    print("\n  归档track分类文件:")
    track_files = [
        "psychological_science.json",
        "cognitive_neuroscience.json", 
        "cognitive_modeling_AI.json",
        "linguistics.json",
        "social_sciences.json",
        "philosophy.json"
    ]
    for track_file in track_files:
        archive_file(f"papers/{track_file}", "data/archives/tracks", dry_run)


def archive_scripts(dry_run: bool = True):
    """归档临时脚本"""
    print("\n=== Phase 7: 归档临时脚本 ===")
    
    scripts_to_archive = [
        "process_missing_books.py",
        "process_big_books.py",
        "process_books_simple.py",
        "test_one_book.py",
        "fix_book_targets.py",
        "book_targets_backup.py",
    ]
    
    for script in scripts_to_archive:
        archive_file(script, "scripts/archived", dry_run)
    
    # 删除旧版处理器
    old_processor = PROJECT_ROOT / "book_processor.py"
    if old_processor.exists():
        log_operation("DELETE", "book_processor.py")
        if not dry_run:
            old_processor.unlink()


def move_docs(dry_run: bool = True):
    """移动文档"""
    print("\n=== Phase 8: 移动文档 ===")
    
    docs = [
        "ROADMAP.md",
        "REFACTOR_PLAN.md",
    ]
    
    for doc in docs:
        move_file(doc, f"docs/{doc}", dry_run)
    
    # 复制 README.md（保留一份在根目录）
    copy_file("README.md", "docs/README_FULL.md", dry_run)
    
    # 创建根目录简化版README
    simple_readme = '''# CogSci RAG - 认知科学知识库问答系统

基于RAG的认知科学论文+教材知识库，支持智能问答、入门导览、用户画像定制。

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动应用
```bash
# Web界面
streamlit run app.py

# 命令行
python cli.py
```

## 📚 完整文档

详细文档请查看：
- **使用指南**：[docs/README_FULL.md](docs/README_FULL.md)
- **优化路线图**：[docs/ROADMAP.md](docs/ROADMAP.md)
- **项目重构**：[docs/REFACTOR_PLAN.md](docs/REFACTOR_PLAN.md)

## 📁 项目结构

```
cogsci_llm/
├── src/              # 核心代码
│   ├── rag/          # RAG引擎
│   ├── crawlers/     # 数据爬取
│   ├── processors/   # 数据处理
│   └── config/       # 配置
├── data/             # 数据文件
│   ├── processed/    # 处理后的数据
│   ├── cache/        # 缓存文件
│   └── archives/     # 历史归档
├── docs/             # 文档
├── scripts/          # 工具脚本
├── app.py            # Web入口
└── cli.py            # 命令行入口（重构后）
```

## 📊 知识库规模

- **论文**：213篇（高引用经典+近5年新论文）
- **全文**：30篇完整论文
- **书籍**：14本核心教材

## 🙏 致谢

Semantic Scholar · arXiv · OpenRouter
'''
    
    readme_path = PROJECT_ROOT / "README.md"
    if not dry_run:
        log_operation("CREATE", "README.md (新简化版)")
        readme_path.write_text(simple_readme, encoding='utf-8')
    else:
        log_operation("CREATE", "README.md (新简化版)")


def cleanup_empty_dirs(dry_run: bool = True):
    """清理空目录"""
    print("\n=== Phase 9: 清理空目录 ===")
    
    papers_dir = PROJECT_ROOT / "papers"
    if papers_dir.exists() and not any(papers_dir.iterdir()):
        log_operation("RMDIR", "papers/")
        if not dry_run:
            papers_dir.rmdir()


def generate_summary():
    """生成操作摘要"""
    print("\n" + "="*60)
    print("操作摘要")
    print("="*60)
    
    op_types = {}
    for op_type, source, target in operations:
        op_types[op_type] = op_types.get(op_type, 0) + 1
    
    for op_type, count in sorted(op_types.items()):
        print(f"{op_type}: {count} 个操作")
    
    print(f"\n总计: {len(operations)} 个操作")


def main():
    parser = argparse.ArgumentParser(description="CogSci RAG 项目重构脚本")
    parser.add_argument(
        "--execute", 
        action="store_true",
        help="真正执行操作（不带此参数只预览）"
    )
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        print("\n" + "="*60)
        print("预览模式 - 不会真正执行操作")
        print("如需执行，请运行: python refactor.py --execute")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("执行模式 - 将真正执行所有操作！")
        print("="*60)
        response = input("确认继续？(yes/no): ")
        if response.lower() != "yes":
            print("已取消")
            return
    
    # 执行重构步骤
    create_directories(dry_run)
    refactor_code_files(dry_run)
    move_crawlers(dry_run)
    move_processors(dry_run)
    move_config(dry_run)
    move_data_files(dry_run)
    archive_scripts(dry_run)
    move_docs(dry_run)
    cleanup_empty_dirs(dry_run)
    
    # 生成摘要
    generate_summary()
    
    if dry_run:
        print("\n提示：这只是预览。使用 --execute 参数真正执行重构。")
    else:
        print("\n✅ 重构完成！")
        print("\n下一步:")
        print("1. 验证 app.py 和 cli.py 能正常启动")
        print("2. 更新所有导入路径（参考 REFACTOR_PLAN.md Phase 6）")
        print("3. 测试所有核心功能")
        print("4. 如遇问题，可从Git恢复")


if __name__ == "__main__":
    main()
