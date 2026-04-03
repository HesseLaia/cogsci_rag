"""
CogSci论文爬虫 v3 - 高引用经典 + 近5年新论文 混合策略
新增：自动重试机制，网络不稳定时自动等待重试

本地运行：
  pip install arxiv requests
  python cogsci_crawler_v3.py
"""

import arxiv
import requests
import json
import time
import os
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 自动重试的 requests session ──────────────────────────────────
def make_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,       # 失败后等 2s / 4s / 8s 递增
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

SESSION = make_session()

# ── 六个Track配置 ────────────────────────────────────────────────
TRACKS = {
    "psychological_science": {
        "label": "Psychological Science",
        "queries": [
            "working memory cognitive load",
            "attention control executive function",
            "emotion regulation cognitive reappraisal",
            "decision making behavioral psychology",
            "memory consolidation sleep",
        ],
        "arxiv_recent": [
            "cognitive psychology experimental",
            "behavioral psychology decision making",
        ]
    },
    "cognitive_neuroscience": {
        "label": "Cognitive Neuroscience",
        "queries": [
            "hippocampus memory consolidation fMRI",
            "prefrontal cortex working memory neural",
            "default mode network cognition",
            "neuroimaging cognitive control attention",
            "dopamine reward learning neuroscience",
        ],
        "arxiv_recent": [
            "cognitive neuroscience fMRI",
            "neural correlates cognition",
        ]
    },
    "cognitive_modeling_AI": {
        "label": "Cognitive Modeling, Neurotheory & AI",
        "queries": [
            "predictive coding free energy principle",
            "Bayesian brain inference perception",
            "reinforcement learning cognitive model",
            "computational psychiatry active inference",
            "neural network cognitive architecture",
        ],
        "arxiv_recent": [
            "computational cognitive model",
            "predictive processing brain",
        ]
    },
    "social_sciences": {
        "label": "Social Sciences & Humanities",
        "queries": [
            "theory of mind social cognition",
            "social learning cultural transmission",
            "embodied cognition social neuroscience",
            "collective behavior cognitive science",
            "moral psychology social brain",
        ],
        "arxiv_recent": [
            "social cognition computational",
            "cultural cognition social neuroscience",
        ]
    },
    "linguistics": {
        "label": "Linguistics",
        "queries": [
            "language acquisition neural basis",
            "syntax semantics cognitive neuroscience",
            "psycholinguistics reading comprehension",
            "large language models linguistic cognition",
            "bilingualism cognitive control brain",
        ],
        "arxiv_recent": [
            "computational linguistics cognitive",
            "language processing brain",
        ]
    },
    "philosophy": {
        "label": "Philosophy of Mind & Cognitive Science",
        "queries": [
            "consciousness neural correlates philosophy",
            "extended mind 4E cognition embodied",
            "enactivism phenomenology cognitive science",
            "qualia subjective experience philosophy mind",
            "free will agency cognitive neuroscience",
        ],
        "arxiv_recent": [
            "philosophy of mind consciousness",
            "embodied cognition enactivism",
        ]
    }
}


# ── Semantic Scholar 通用请求（带手动重试）───────────────────────
def _fetch_s2(params: dict, track_key: str, query: str, tier: str,
              max_manual_retries: int = 3) -> list[dict]:
    headers = {"User-Agent": "CogSciRAG/3.0 (research project)"}
    for attempt in range(1, max_manual_retries + 1):
        try:
            resp = SESSION.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params=params, headers=headers, timeout=20
            )
            if resp.status_code == 200:
                results = []
                for paper in resp.json().get("data", []):
                    if not paper.get("abstract"):
                        continue
                    results.append({
                        "source": "semantic_scholar",
                        "tier": tier,
                        "track": track_key,
                        "title": paper.get("title", ""),
                        "authors": [a["name"] for a in paper.get("authors", [])[:5]],
                        "abstract": paper.get("abstract", "").replace("\n", " "),
                        "year": str(paper.get("year", "")),
                        "citation_count": paper.get("citationCount", 0),
                        "url": paper.get("url", ""),
                        "fields": paper.get("fieldsOfStudy", []),
                        "query_used": query
                    })
                return results
            elif resp.status_code == 429:
                wait = 15 * attempt
                print(f"    ⚠ 限速，等待 {wait}s... (第{attempt}次)")
                time.sleep(wait)
            else:
                print(f"    S2状态码 {resp.status_code}，跳过")
                return []
        except Exception as e:
            wait = 5 * attempt
            print(f"    S2连接错误 (第{attempt}次)，等待{wait}s: {str(e)[:60]}")
            time.sleep(wait)
    print(f"    S2 [{query[:40]}] 重试耗尽，跳过")
    return []


def fetch_s2_classic(query, track_key, max_results=12):
    return _fetch_s2({
        "query": query, "limit": max_results,
        "fields": "title,authors,abstract,year,citationCount,url,fieldsOfStudy",
        "sort": "citationCount"
    }, track_key, query, tier="classic")


def fetch_s2_recent(query, track_key, max_results=8):
    current_year = datetime.now().year
    return _fetch_s2({
        "query": query, "limit": max_results,
        "fields": "title,authors,abstract,year,citationCount,url,fieldsOfStudy",
        "year": f"{current_year - 5}-{current_year}"
    }, track_key, query, tier="recent")


# ── arXiv（带手动重试）──────────────────────────────────────────
def fetch_arxiv_recent(query, track_key, max_results=8,
                       max_manual_retries=3) -> list[dict]:
    for attempt in range(1, max_manual_retries + 1):
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query, max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            results = []
            for paper in client.results(search):
                results.append({
                    "source": "arxiv",
                    "tier": "recent",
                    "track": track_key,
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors[:5]],
                    "abstract": paper.summary.replace("\n", " "),
                    "year": paper.published.strftime("%Y"),
                    "published_date": paper.published.strftime("%Y-%m-%d"),
                    "citation_count": None,
                    "url": paper.entry_id,
                    "pdf_url": paper.pdf_url,
                    "categories": paper.categories,
                    "query_used": query
                })
            return results
        except Exception as e:
            wait = 10 * attempt
            print(f"    arXiv错误 (第{attempt}次)，等待{wait}s: {str(e)[:60]}")
            time.sleep(wait)
    print(f"    arXiv [{query[:40]}] 重试耗尽，跳过")
    return []


# ── 去重 ─────────────────────────────────────────────────────────
def deduplicate(papers):
    seen, unique = set(), []
    for p in papers:
        key = p["title"].lower().strip()
        if key not in seen and len(key) > 5:
            seen.add(key)
            unique.append(p)
    return unique


# ── 主流程 ───────────────────────────────────────────────────────
def crawl_all():
    all_papers = []
    summary = {}

    for track_key, cfg in TRACKS.items():
        label = cfg["label"]
        print(f"\n{'='*52}")
        print(f"  {label}")
        print(f"{'='*52}")
        track_papers = []

        print("  [经典] S2 高引用论文...")
        for query in cfg["queries"]:
            print(f"    → {query[:50]}")
            track_papers.extend(fetch_s2_classic(query, track_key))
            time.sleep(3)   # v3加长等待，减少被限速概率

        print("  [近期] S2 近5年论文...")
        for query in cfg["queries"][:3]:
            print(f"    → {query[:50]}")
            track_papers.extend(fetch_s2_recent(query, track_key))
            time.sleep(3)

        print("  [最新] arXiv 最新论文...")
        for query in cfg["arxiv_recent"]:
            print(f"    → {query[:50]}")
            track_papers.extend(fetch_arxiv_recent(query, track_key))
            time.sleep(4)   # arXiv限速更严，多等一秒

        track_papers = deduplicate(track_papers)
        track_papers.sort(key=lambda x: x.get("citation_count") or 0, reverse=True)

        classic_n = sum(1 for p in track_papers if p.get("tier") == "classic")
        recent_n  = len(track_papers) - classic_n
        summary[track_key] = {"total": len(track_papers), "classic": classic_n, "recent": recent_n}

        out_path = os.path.join(OUTPUT_DIR, f"{track_key}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(track_papers, f, ensure_ascii=False, indent=2)
        print(f"  ✓ {len(track_papers)} 篇（经典:{classic_n} 近期:{recent_n}）")

        all_papers.extend(track_papers)

    all_papers = deduplicate(all_papers)
    all_papers.sort(key=lambda x: x.get("citation_count") or 0, reverse=True)

    summary_path = os.path.join(OUTPUT_DIR, "all_papers.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_papers, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*52}")
    print("爬取完成！")
    for k, v in summary.items():
        label = TRACKS[k]['label'][:35]
        print(f"  {label:<35} {v['total']:>4}篇  (经典:{v['classic']} 近期:{v['recent']})")
    print(f"  去重后总计: {len(all_papers)} 篇 → {summary_path}")


if __name__ == "__main__":
    print("CogSci论文爬虫 v3 启动")
    print(f"策略：高引用经典 + 近5年新论文 + 自动重试")
    print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    crawl_all()