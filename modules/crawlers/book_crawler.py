"""
书籍获取爬虫
支持：LibGen API, OpenLibrary, Archive.org

运行前：
  pip install requests beautifulsoup4 PyPDF2 pdfplumber
"""

import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, List
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from book_targets import CORE_BOOKS

# ── 配置 ──────────────────────────────────────────────────────
BOOKS_DIR = Path("data/books_cache")
BOOKS_DIR.mkdir(parents=True, exist_ok=True)

LIBGEN_SEARCH_API = "http://libgen.rs/json.php"
# 备用：http://libgen.is/json.php

OPENLIBRARY_API = "https://openlibrary.org/api/books"
ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 代理配置（如果需要代理，取消注释）
USE_PROXY = False  # 改为 True 启用代理

if USE_PROXY:
    PROXIES = {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890",
    }
else:
    PROXIES = None  # 直连

# 超时配置（秒）
TIMEOUT_SHORT = 30   # 搜索API
TIMEOUT_LONG = 180   # 下载PDF


# ── LibGen 搜索 ────────────────────────────────────────────────
def search_libgen(title: str = None, author: str = None, isbn: str = None) -> List[Dict]:
    """
    通过 LibGen API 搜索书籍
    返回: [{"title", "author", "md5", "extension", "filesize", "download_link"}]
    """
    params = {"fields": "title,author,md5,extension,filesize,year,publisher"}

    if isbn:
        params["isbn"] = isbn
    elif title:
        params["title"] = title
    if author:
        params["author"] = author

    params["mode"] = "newer"  # 优先返回新版本

    try:
        print(f"  搜索 LibGen: {title or isbn}")
        resp = requests.get(LIBGEN_SEARCH_API, params=params,
                          headers=HEADERS, timeout=TIMEOUT_SHORT,
                          proxies=PROXIES, verify=False)
        if resp.status_code != 200:
            print(f"    LibGen返回 {resp.status_code}")
            return []

        results = resp.json()
        if not results:
            print(f"    LibGen未找到")
            return []

        # 处理结果，添加下载链接
        books = []
        for item in results[:5]:  # 只取前5个结果
            md5 = item.get("md5", "")
            if not md5:
                continue

            # LibGen 下载链接构造（多个镜像）
            # 镜像1: http://library.lol/main/{md5}
            # 镜像2: http://libgen.rs/book/index.php?md5={md5}

            books.append({
                "title": item.get("title", ""),
                "author": item.get("author", ""),
                "year": item.get("year", ""),
                "publisher": item.get("publisher", ""),
                "extension": item.get("extension", "pdf"),
                "filesize": item.get("filesize", ""),
                "md5": md5,
                "download_url": f"http://library.lol/main/{md5}",
                "backup_url": f"http://libgen.rs/book/index.php?md5={md5}",
                "source": "libgen"
            })

        print(f"    找到 {len(books)} 个结果")
        return books

    except Exception as e:
        print(f"    LibGen搜索失败: {e}")
        return []


# ── OpenLibrary 搜索 ───────────────────────────────────────────
def search_openlibrary(isbn: str) -> Optional[Dict]:
    """
    通过 OpenLibrary API 搜索（主要用于获取章节目录和预览）
    """
    try:
        print(f"  搜索 OpenLibrary: ISBN {isbn}")
        params = {
            "bibkeys": f"ISBN:{isbn}",
            "format": "json",
            "jscmd": "data"
        }
        resp = requests.get(OPENLIBRARY_API, params=params,
                          headers=HEADERS, timeout=TIMEOUT_SHORT,
                          proxies=PROXIES)
        if resp.status_code != 200:
            return None

        data = resp.json()
        key = f"ISBN:{isbn}"
        if key not in data:
            print(f"    OpenLibrary未找到")
            return None

        book = data[key]
        result = {
            "title": book.get("title", ""),
            "authors": [a["name"] for a in book.get("authors", [])],
            "publish_date": book.get("publish_date", ""),
            "number_of_pages": book.get("number_of_pages", 0),
            "url": book.get("url", ""),
            "preview_url": book.get("preview_url", ""),
            "source": "openlibrary"
        }

        # 检查是否有借阅链接
        if "lending" in book.get("availability", {}):
            result["borrowable"] = True

        print(f"    找到: {result['title']}")
        return result

    except Exception as e:
        print(f"    OpenLibrary搜索失败: {e}")
        return None


# ── Archive.org 搜索 ───────────────────────────────────────────
def search_archive_org(title: str, author: str = None) -> List[Dict]:
    """
    搜索 Archive.org 的书籍（很多学术书籍的合法扫描版）
    """
    try:
        print(f"  搜索 Archive.org: {title}")
        # 提取核心关键词（去掉副标题）
        core_title = title.split(':')[0].strip()
        query = f'title:"{core_title}"'

        if author:
            # 提取作者姓氏
            author_last = author.split()[-1]
            query += f' AND creator:"{author_last}"'

        params = {
            "q": query,
            "fl[]": ["identifier", "title", "creator", "year", "mediatype"],
            "rows": 20,  # 增加结果数
            "page": 1,
            "output": "json",
            "mediatype": "texts"
        }

        resp = requests.get(ARCHIVE_SEARCH, params=params,
                          headers=HEADERS, timeout=TIMEOUT_SHORT,
                          proxies=PROXIES)
        if resp.status_code != 200:
            return []

        data = resp.json()
        docs = data.get("response", {}).get("docs", [])

        if not docs:
            print(f"    Archive.org未找到")
            return []

        results = []
        for doc in docs:
            identifier = doc.get("identifier", "")
            if not identifier:
                continue

            results.append({
                "title": doc.get("title", ""),
                "creator": doc.get("creator", ""),
                "year": doc.get("year", ""),
                "identifier": identifier,
                "url": f"https://archive.org/details/{identifier}",
                "pdf_url": f"https://archive.org/download/{identifier}/{identifier}.pdf",
                "source": "archive_org"
            })

        print(f"    找到 {len(results)} 个结果")
        return results

    except Exception as e:
        print(f"    Archive.org搜索失败: {e}")
        return []


# ── 下载文件 ───────────────────────────────────────────────────
def download_book(url: str, save_path: Path) -> bool:
    """下载书籍文件"""
    if save_path.exists():
        print(f"    已缓存: {save_path.name}")
        return True

    try:
        print(f"    下载中: {url[:70]}")
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_LONG,
                          stream=True, proxies=PROXIES, verify=False)
        resp.raise_for_status()

        # 检查是否是PDF
        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type and not url.endswith(".pdf"):
            print(f"    警告: 非PDF文件 ({content_type})")

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # 验证文件头
        with open(save_path, "rb") as f:
            header = f.read(5)

        if header != b"%PDF-":
            save_path.unlink()
            print(f"    下载失败: 不是有效的PDF")
            return False

        print(f"    ✓ 下载成功: {save_path.name} ({save_path.stat().st_size / 1024 / 1024:.1f}MB)")
        return True

    except Exception as e:
        print(f"    下载失败: {e}")
        if save_path.exists():
            save_path.unlink()
        return False


# ── 主流程：批量搜索和下载 ──────────────────────────────────────
def crawl_books():
    """批量搜索和下载核心教材"""

    results_log = []

    for track, books in CORE_BOOKS.items():
        print(f"\n{'='*60}")
        print(f"Track: {track}")
        print(f"{'='*60}")

        for book_info in books:
            title = book_info["title"]
            author = book_info["author"]
            isbn = book_info.get("isbn", "")
            priority = book_info.get("priority", "medium")

            print(f"\n[{priority.upper()}] {title} - {author}")

            # 准备保存路径
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_"
                               for c in title)[:50]
            save_path = BOOKS_DIR / f"{track}_{safe_title}.pdf"

            # 如果已下载，跳过
            if save_path.exists():
                print(f"  已存在，跳过")
                results_log.append({
                    "track": track,
                    "book": title,
                    "status": "cached",
                    "path": str(save_path)
                })
                continue

            # 搜索顺序：LibGen → Archive.org → OpenLibrary
            found = False

            # 1. LibGen（最全面）
            libgen_results = search_libgen(title=title, author=author, isbn=isbn)
            if libgen_results:
                # 优先选PDF格式
                pdf_results = [r for r in libgen_results if r["extension"].lower() == "pdf"]
                target = pdf_results[0] if pdf_results else libgen_results[0]

                # 尝试主链接
                if download_book(target["download_url"], save_path):
                    found = True
                    results_log.append({
                        "track": track,
                        "book": title,
                        "status": "success",
                        "source": "libgen",
                        "path": str(save_path)
                    })
                # 尝试备用链接
                elif download_book(target["backup_url"], save_path):
                    found = True
                    results_log.append({
                        "track": track,
                        "book": title,
                        "status": "success",
                        "source": "libgen_backup",
                        "path": str(save_path)
                    })

            # 2. Archive.org
            if not found:
                time.sleep(2)
                archive_results = search_archive_org(title, author)
                if archive_results:
                    target = archive_results[0]
                    if download_book(target["pdf_url"], save_path):
                        found = True
                        results_log.append({
                            "track": track,
                            "book": title,
                            "status": "success",
                            "source": "archive_org",
                            "path": str(save_path)
                        })

            # 3. OpenLibrary（通常只有预览，不是完整PDF）
            if not found and isbn:
                time.sleep(1)
                ol_result = search_openlibrary(isbn)
                if ol_result and ol_result.get("preview_url"):
                    print(f"  ℹ OpenLibrary有预览: {ol_result['preview_url']}")
                    results_log.append({
                        "track": track,
                        "book": title,
                        "status": "preview_only",
                        "source": "openlibrary",
                        "url": ol_result["preview_url"]
                    })

            if not found:
                print(f"  ✗ 未找到可下载的PDF")
                results_log.append({
                    "track": track,
                    "book": title,
                    "status": "not_found"
                })

            time.sleep(3)  # 礼貌等待

    # 保存结果日志
    log_path = BOOKS_DIR / "crawl_results.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(results_log, f, ensure_ascii=False, indent=2)

    # 统计
    success = sum(1 for r in results_log if r["status"] == "success")
    cached = sum(1 for r in results_log if r["status"] == "cached")
    failed = sum(1 for r in results_log if r["status"] == "not_found")

    print(f"""
{'='*60}
爬取完成！
  成功下载: {success} 本
  已有缓存: {cached} 本
  未找到:   {failed} 本

详细日志: {log_path}
{'='*60}
    """)


if __name__ == "__main__":
    crawl_books()
