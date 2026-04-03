"""
Compatibility wrapper.
Real implementation: modules/crawlers/book_crawler.py
"""

from modules.crawlers.book_crawler import *  # noqa: F401,F403


if __name__ == "__main__":
    crawl_books()

