"""
论文爬虫统一入口
整合三个功能：
1. 论文元数据爬取（Semantic Scholar + arXiv）
2. 全文PDF获取（支持OCR）
3. 核心论文补充

使用方式：
  python paper_crawler.py --mode metadata    # 爬取元数据
  python paper_crawler.py --mode fulltext    # 获取全文PDF
  python paper_crawler.py --mode enrich      # 补充核心论文
  python paper_crawler.py --mode all         # 全流程执行
"""

import argparse
import sys
from pathlib import Path

# 导入原有的三个模块功能
print("论文爬虫统一入口")
print("=" * 60)
print("本脚本整合了以下功能：")
print("  1. cogsci_crawler.py  - 论文元数据爬取")
print("  2. spider.py          - 全文PDF获取")
print("  3. enrich_papers.py   - 核心论文补充")
print("=" * 60)


def run_metadata_crawler():
    """运行元数据爬虫"""
    print("\n[1/3] 执行论文元数据爬取...")
    print("模块: cogsci_crawler.py")
    try:
        import cogsci_crawler
        cogsci_crawler.crawl_all()
        print("✓ 元数据爬取完成")
    except Exception as e:
        print(f"✗ 元数据爬取失败: {e}")
        return False
    return True


def run_fulltext_crawler():
    """运行全文PDF爬虫"""
    print("\n[2/3] 执行全文PDF获取...")
    print("模块: spider.py")
    try:
        import spider
        spider.main()
        print("✓ 全文获取完成")
    except Exception as e:
        print(f"✗ 全文获取失败: {e}")
        return False
    return True


def run_enrich():
    """运行核心论文补充"""
    print("\n[3/3] 执行核心论文补充...")
    print("模块: enrich_papers.py")

    # 检查输入文件
    if not Path("data/all_papers_clean.json").exists():
        print("✗ 找不到 data/all_papers_clean.json")
        print("  提示：请先运行 metadata 模式")
        return False

    try:
        import enrich_papers
        # enrich_papers 是直接执行的脚本，没有main函数
        print("✓ 核心论文补充完成")
    except Exception as e:
        print(f"✗ 核心论文补充失败: {e}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description="认知科学论文爬虫统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python paper_crawler.py --mode metadata    # 只爬元数据
  python paper_crawler.py --mode fulltext    # 只获取全文
  python paper_crawler.py --mode enrich      # 只补充核心论文
  python paper_crawler.py --mode all         # 全流程（推荐首次使用）
        """
    )

    parser.add_argument(
        "--mode",
        choices=["metadata", "fulltext", "enrich", "all"],
        default="all",
        help="运行模式（默认：all）"
    )

    args = parser.parse_args()

    print(f"\n运行模式: {args.mode}")
    print("=" * 60)

    if args.mode == "metadata":
        run_metadata_crawler()

    elif args.mode == "fulltext":
        run_fulltext_crawler()

    elif args.mode == "enrich":
        run_enrich()

    elif args.mode == "all":
        print("全流程执行（预计30-60分钟）\n")

        # 步骤1：元数据
        if not run_metadata_crawler():
            print("\n✗ 流程中断：元数据爬取失败")
            sys.exit(1)

        # 步骤2：全文（可选，失败不中断）
        run_fulltext_crawler()

        # 步骤3：补充（可选）
        run_enrich()

        print("\n" + "=" * 60)
        print("全流程完成！")
        print("输出文件：data/all_papers_fulltext.json")
        print("=" * 60)


if __name__ == "__main__":
    main()
