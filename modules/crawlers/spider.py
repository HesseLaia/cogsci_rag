"""
cogsci_fulltext_crawler.py

目标：爬取高引用综述类论文全文，处理PDF（含扫描版），
      输出为可直接替换 all_papers_clean.json 的增强版数据。

运行前确认：
  pip install requests pdfplumber pdf2image pillow pytesseract semanticscholar
  Tesseract引擎已安装（OCR扫描版PDF用）
"""

import json
import time
import os
import re
import requests
import pdfplumber
import pytesseract
import urllib3
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── 配置区 ──────────────────────────────────────────────────────

# Tesseract路径，Windows用户按实际安装位置修改
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

INPUT_JSON  = "data/all_papers_fulltext.json"
OUTPUT_JSON = "data/all_papers_fulltext.json"
PDF_DIR     = Path("data/pdfs_cache")   # PDF临时缓存目录
PDF_DIR.mkdir(parents=True, exist_ok=True)

# 综述类关键词，标题或摘要含这些词的优先处理
REVIEW_KEYWORDS = [
    "review", "survey", "overview", "tutorial", "introduction to",
    "handbook", "primer", "meta-analysis", "systematic review",
    "综述", "progress", "advances in", "a unified", "toward a",
    "framework for", "theory of", "principles of"
]

# 只处理引用量超过这个阈值的论文（控制质量）
MIN_CITATIONS_FOR_FULLTEXT = 50

# 每篇论文全文最多保留多少字（太长会撑爆向量库）
MAX_FULLTEXT_CHARS = 12000

import os

# Semantic Scholar API（API Key 从环境变量读取，可选）
SS_API = "https://api.semanticscholar.org/graph/v1"
SS_API_KEY = os.getenv("SS_API_KEY", "")
SS_HEADERS = {"x-api-key": SS_API_KEY} if SS_API_KEY else {}

# 期刊黑名单：这些域名即使有链接也必然403，直接跳过省时间
BLOCKED_DOMAINS = [
    "elsevier.com", "sciencedirect.com", "wiley.com", "onlinelibrary.wiley.com",
    "springer.com", "springerlink.com", "nature.com", "annualreviews.org",
    "royalsocietypublishing.org", "academic.oup.com", "oxfordjournals.org",
    "sagepub.com", "journals.sagepub.com", "tandfonline.com", "cell.com",
    "direct.mit.edu", "silverchair.com", "nyaspubs.onlinelibrary.wiley.com",
    "manuscript.elsevier.com", "europepmc.org",
]

# ── 工具函数 ────────────────────────────────────────────────────

def is_review_paper(title: str, abstract: str) -> bool:
    """判断是否是综述类论文"""
    text = (title + " " + abstract).lower()
    return any(kw in text for kw in REVIEW_KEYWORDS)

def is_blocked_url(url: str) -> bool:
    """判断URL是否在期刊黑名单中（必然403）"""
    for domain in BLOCKED_DOMAINS:
        if domain in url:
            return True
    return False

def is_valid_pdf(path: Path) -> bool:
    """检查文件头是否是真正的PDF（防止下载到HTML页面）"""
    try:
        with open(path, "rb") as f:
            header = f.read(5)
        return header == b"%PDF-"
    except Exception:
        return False

def download_pdf(url: str, save_path: Path) -> bool:
    """下载PDF到本地，返回是否成功"""
    if save_path.exists():
        # 已缓存，但要验证是否真的是PDF
        if is_valid_pdf(save_path):
            return True
        else:
            save_path.unlink()  # 删掉损坏的缓存重新下载

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/pdf,*/*",
        }
        resp = requests.get(url, headers=headers, timeout=30, verify=False, stream=True)
        resp.raise_for_status()

        # 检查Content-Type，如果是HTML说明被重定向到登录页了
        content_type = resp.headers.get("Content-Type", "")
        if "html" in content_type:
            print(f"    下载失败：返回HTML而非PDF（被重定向到登录页）")
            return False

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # 写完后再验证文件头
        if not is_valid_pdf(save_path):
            save_path.unlink()
            print(f"    下载失败：文件头不是PDF（可能是HTML登录页）")
            return False

        return True
    except Exception as e:
        print(f"    下载失败：{e}")
        return False

def extract_text_pdfplumber(pdf_path: Path) -> str:
    """数字版PDF提取文字（速度快，质量高）"""
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:20]:  # 最多读20页
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                if len(text) > MAX_FULLTEXT_CHARS:
                    break
        return text.strip()
    except Exception as e:
        print(f"    pdfplumber失败：{e}")
        return ""

def extract_text_ocr(pdf_path: Path) -> str:
    """扫描版PDF用OCR提取（慢，但能处理图片页）"""
    try:
        print("    检测到扫描版，启动OCR（较慢）...")
        images = convert_from_path(str(pdf_path), first_page=1, last_page=8, dpi=200)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img, lang="eng") + "\n"
            if len(text) > MAX_FULLTEXT_CHARS:
                break
        return text.strip()
    except Exception as e:
        print(f"    OCR失败：{e}")
        return ""

def extract_fulltext(pdf_path: Path) -> str:
    """
    主提取函数：先试数字提取，失败或文字太少则转OCR
    同时清洗掉参考文献部分
    """
    text = extract_text_pdfplumber(pdf_path)

    # 如果提取的文字太少（<200字），说明是扫描版
    if len(text) < 200:
        text = extract_text_ocr(pdf_path)

    if not text:
        return ""

    # 清洗：截断到参考文献之前
    for marker in ["References\n", "REFERENCES\n", "Bibliography\n",
                   "参考文献\n", "BIBLIOGRAPHY\n"]:
        idx = text.rfind(marker)
        if idx > len(text) * 0.5:  # 参考文献在后半部分才截断
            text = text[:idx]
            break

    # 清洗：去掉多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text[:MAX_FULLTEXT_CHARS].strip()

def get_arxiv_pdf_url(paper: dict) -> str:
    """从论文数据里提取arXiv PDF链接"""
    url = paper.get("url", "")
    if "arxiv.org" in url:
        arxiv_id = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
        if arxiv_id:
            return f"https://arxiv.org/pdf/{arxiv_id.group(1)}.pdf"
    return ""

def fetch_ss_fulltext_info(paper_id: str) -> dict:
    """从Semantic Scholar详情接口拉取完整的openAccessPdf和externalIds（含DOI）"""
    if not paper_id:
        return {}
    try:
        time.sleep(1.2)
        url = f"{SS_API}/paper/{paper_id}"
        params = {"fields": "title,openAccessPdf,externalIds"}
        resp = requests.get(url, params=params, headers=SS_HEADERS, timeout=15, verify=False)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}

def fetch_unpaywall_pdf(doi: str) -> str:
    """通过 Unpaywall API 查开放获取 PDF 链接，只需 DOI"""
    if not doi:
        return ""
    try:
        time.sleep(0.5)
        url = f"https://api.unpaywall.org/v2/{doi}?email=research@example.com"
        resp = requests.get(url, timeout=10, verify=False)
        if resp.status_code != 200:
            return ""
        data = resp.json()
        # 优先拿 best_oa_location 的 PDF，且不在黑名单里
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf", "")
        if pdf_url and not is_blocked_url(pdf_url):
            return pdf_url
        # fallback：遍历所有 oa_locations，找第一个不在黑名单的
        for loc in data.get("oa_locations", []):
            candidate = loc.get("url_for_pdf", "")
            if candidate and not is_blocked_url(candidate):
                return candidate
    except Exception as e:
        print(f"    Unpaywall查询失败：{e}")
    return ""

def search_ss_reviews(track_query: str, track_name: str,
                      min_citations: int = 50, limit: int = 30) -> list:
    """
    从Semantic Scholar搜索某个track的高引用综述论文
    返回论文列表
    """
    results = []
    try:
        time.sleep(1.2)
        url = f"{SS_API}/paper/search"
        params = {
            # ★ 加了 paperId 字段，后续用于 S2 详情查询
            "query":  track_query,
            "fields": "paperId,title,authors,year,citationCount,abstract,url,openAccessPdf,externalIds",
            "limit":  100,
        }
        resp = requests.get(url, params=params, headers=SS_HEADERS, timeout=15, verify=False)
        if resp.status_code != 200:
            print(f"  搜索失败 {resp.status_code}：{track_query}")
            return []

        data = resp.json().get("data", [])
        for p in data:
            cite = p.get("citationCount", 0) or 0
            if cite < min_citations:
                continue
            title    = p.get("title", "")
            abstract = p.get("abstract", "") or ""
            if not is_review_paper(title, abstract):
                continue
            results.append({
                "title":           title,
                "authors":         [a["name"] for a in p.get("authors", [])],
                "year":            p.get("year"),
                "abstract":        abstract,
                "citation_count":  cite,
                "track":           track_name,
                "url":             p.get("url", ""),
                "open_access_pdf": (p.get("openAccessPdf") or {}).get("url", ""),
                "external_ids":    p.get("externalIds", {}),
                "paper_id":        p.get("paperId", ""),   # ★ 新增
                "tier":            "review",
                "fulltext":        ""
            })

    except Exception as e:
        print(f"  搜索异常：{e}")

    results.sort(key=lambda x: x["citation_count"], reverse=True)
    return results[:limit]

# ── 主流程 ──────────────────────────────────────────────────────

def main():
    # 1. 载入现有数据
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        papers = json.load(f)

    existing_titles = {p["title"].lower() for p in papers}
    print(f"现有论文：{len(papers)}篇\n")

    # 2. 按track搜索综述论文
    TRACK_QUERIES = [
        ("consciousness philosophy of mind review",        "philosophy"),
        ("cognitive neuroscience predictive coding review","cognitive_neuroscience"),
        ("cognitive modeling computational review",        "cognitive_modeling_AI"),
        ("psycholinguistics language cognition review",    "linguistics"),
        ("social cognition psychology review",             "social_sciences"),
        ("cognitive psychology learning memory review",    "psychological_science"),
    ]

    new_papers = []
    print("── 第一阶段：搜索综述论文 ──────────────────────────────")
    for query, track in TRACK_QUERIES:
        print(f"\n搜索 [{track}]：{query}")
        found = search_ss_reviews(query, track,
                                  min_citations=MIN_CITATIONS_FOR_FULLTEXT)
        fresh = [p for p in found if p["title"].lower() not in existing_titles]
        for p in fresh:
            existing_titles.add(p["title"].lower())
        new_papers.extend(fresh)
        print(f"  找到{len(found)}篇综述，新增{len(fresh)}篇")
        time.sleep(1.2)

    papers.extend(new_papers)
    print(f"\n合并后总计：{len(papers)}篇")

    # 3. 对所有论文尝试获取全文
    print("\n── 第二阶段：下载全文PDF ───────────────────────────────")

    candidates = [
        p for p in papers
        if (p.get("citation_count", 0) or 0) >= MIN_CITATIONS_FOR_FULLTEXT
        and is_review_paper(p.get("title",""), p.get("abstract",""))
        and not p.get("fulltext")
    ]
    print(f"符合条件（引用≥{MIN_CITATIONS_FOR_FULLTEXT} + 综述类）：{len(candidates)}篇")

    success, failed = 0, 0
    for i, paper in enumerate(candidates, 1):
        title = paper["title"]
        print(f"\n[{i}/{len(candidates)}] {title[:55]}")

        # ── PDF来源查找（优先级从高到低）──────────────────────────

        # 1. S2搜索结果里的 openAccessPdf
        pdf_url = paper.get("open_access_pdf", "")
        if pdf_url and is_blocked_url(pdf_url):
            print(f"    S2链接在黑名单，跳过：{pdf_url[:60]}")
            pdf_url = ""

        # 2. URL字段里的 arXiv 链接
        if not pdf_url:
            pdf_url = get_arxiv_pdf_url(paper)

        # 3. externalIds 里的 ArXiv ID
        if not pdf_url:
            arxiv_id = (paper.get("external_ids") or {}).get("ArXiv", "")
            if arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        # 4. ★ 调 S2 详情接口补全（搜索结果的 externalIds 有时不含DOI）
        if not pdf_url:
            paper_id = paper.get("paper_id", "")
            if paper_id:
                print(f"    查询S2详情补全DOI/PDF...")
                detail = fetch_ss_fulltext_info(paper_id)
                if detail:
                    # 补充 openAccessPdf
                    oa = (detail.get("openAccessPdf") or {}).get("url", "")
                    if oa and not is_blocked_url(oa):
                        pdf_url = oa
                        print(f"    S2详情补充PDF：{pdf_url[:70]}")
                    # 补充 externalIds（含DOI），不管有没有找到PDF都更新
                    merged_ids = {**(paper.get("external_ids") or {}),
                                  **(detail.get("externalIds") or {})}
                    paper["external_ids"] = merged_ids

        # 5. ★ Unpaywall 用 DOI 查（现在 DOI 更完整了）
        if not pdf_url:
            doi = (paper.get("external_ids") or {}).get("DOI", "")
            pdf_url = fetch_unpaywall_pdf(doi)
            if pdf_url:
                print(f"    Unpaywall补充：{pdf_url[:70]}")

        # 所有来源都没有，放弃
        if not pdf_url:
            print("    无可用开放获取PDF，跳过")
            failed += 1
            continue

        # ── 下载 & 提取 ──────────────────────────────────────────

        safe_name = re.sub(r'[^\w]', '_', title[:40]) + ".pdf"
        pdf_path  = PDF_DIR / safe_name

        print(f"    来源：{pdf_url[:70]}")
        if not download_pdf(pdf_url, pdf_path):
            failed += 1
            continue

        fulltext = extract_fulltext(pdf_path)
        if fulltext and len(fulltext) > 300:
            paper["fulltext"] = fulltext
            success += 1
            print(f"    ✓ 提取{len(fulltext)}字")
        else:
            print(f"    ✗ 提取失败或内容太少")
            failed += 1

        time.sleep(1.2)

    # 4. 保存结果
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    # 5. 报告
    print(f"""
── 完成 ────────────────────────────────────────────────
输出文件：{OUTPUT_JSON}
总论文数：{len(papers)}篇
全文获取：成功{success}篇 / 失败或无PDF {failed}篇
有全文的论文数：{sum(1 for p in papers if p.get('fulltext'))}篇
────────────────────────────────────────────────────────
""")

if __name__ == "__main__":
    main()