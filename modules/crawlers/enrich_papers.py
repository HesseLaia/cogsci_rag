import json
import time
import requests
from pathlib import Path

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── 可以直接从Semantic Scholar拉的论文 ──────────────────────────
CORE_PAPERS_SS = [
    {
        "id": "c2a06f095a81f5f979ffe5aa664c175a625fba0c",
        "track": "philosophy"
    },  # Chalmers 1995 - Facing Up to the Problem of Consciousness
    {
        "id": "ef9a2d274b5dba2e13403e93ab545ccfdfd28c3d",
        "track": "linguistics"
    },  # Boroditsky 2001 - Does Language Shape Thought
    {
        "id": "dbe79abbbc1fc7df6ce90d263a363d99fabd3489",
        "track": "linguistics"
    },  # Pinker & Bloom 1990 - Natural Language and Natural Selection
    {
        "id": "83040001210751239553269727b9ea53e152af71",
        "track": "cognitive_modeling_AI"
    },  # Lake et al. 2017 - Building Machines That Learn and Think Like People
    {
        "id": "1ed6a4a10589618d4f26350f1a296ee767ceff6b",
        "track": "cognitive_neuroscience"
    },  # Friston 2010 - The Free-Energy Principle
]

# ── 需要你手动放PDF进来的论文（放在 papers/pdfs/ 目录下）──────────
# 格式：文件名，track，作者年份备注
PDF_PAPERS = [
    ("nagel_1974_what_is_it_like_to_be_a_bat.pdf", "philosophy"),
    ("anderson_1996_act_r.pdf", "cognitive_modeling_AI"),
    ("dehaene_2006_global_workspace.pdf", "cognitive_neuroscience"),
]


def fetch_from_ss(paper_id):
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
    params = {"fields": "title,authors,year,citationCount,abstract,url"}

    for attempt in range(3):  # 最多重试3次
        try:
            time.sleep(2 + attempt * 3)  # 第1次等2秒，第2次5秒，第3次8秒
            resp = requests.get(url, params=params, timeout=20, verify=False)  # verify=False跳过SSL验证
            if resp.status_code == 429:
                wait = 10 + attempt * 10
                print(f"  限速，等{wait}秒后重试...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.SSLError:
            print(f"  SSL错误，重试中（{attempt + 1}/3）...")
            continue
        except Exception as e:
            print(f"  请求失败：{e}")
            return None
    return None

def ss_to_record(data, track):
    return {
        "title":          data.get("title", ""),
        "authors":        [a["name"] for a in data.get("authors", [])],
        "year":           data.get("year"),
        "abstract":       data.get("abstract", "") or "",
        "citation_count": data.get("citationCount", 0),
        "track":          track,
        "url":            data.get("url", ""),
        "tier":           "core"
    }

def extract_pdf_abstract(pdf_path):
    """从PDF提取前2000字作为摘要替代"""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages[:4]:  # 只读前4页
                text += page.extract_text() or ""
                if len(text) > 2000:
                    break
        return text[:2000].strip()
    except ImportError:
        print("  提示：pip install pdfplumber 可以解析PDF全文")
        return ""
    except Exception as e:
        print(f"  PDF解析失败：{e}")
        return ""

# ── 主流程 ──────────────────────────────────────────────────────
with open("papers/all_papers_clean.json", "r", encoding="utf-8") as f:
    papers = json.load(f)

existing_titles = {p["title"].lower() for p in papers}
added = []

# 第一批：从Semantic Scholar拉
print("── 从Semantic Scholar拉取核心论文 ──")
for item in CORE_PAPERS_SS:
    data = fetch_from_ss(item["id"])
    if not data:
        print(f"❌ 找不到ID：{item['id']}")
        continue

    title = data.get("title", "")
    if title.lower() in existing_titles:
        print(f"⚠  已存在：{title[:55]}")
        continue

    if not data.get("abstract"):
        print(f"⚠  无摘要：{title[:55]}（仍会添加）")

    record = ss_to_record(data, item["track"])
    papers.append(record)
    existing_titles.add(title.lower())
    added.append(title)
    print(f"✓  {title[:55]}（{record['citation_count']}引用）")
    time.sleep(0.5)

# 第二批：本地PDF
if PDF_PAPERS:
    print("\n── 处理本地PDF ──")
    pdf_dir = Path("papers/pdfs")
    for filename, track in PDF_PAPERS:
        pdf_path = pdf_dir / filename
        if not pdf_path.exists():
            print(f"❌ 找不到文件：{filename}")
            continue
        abstract = extract_pdf_abstract(pdf_path)
        # 文件名当标题（你可以手动改json里的title）
        title = filename.replace("_", " ").replace(".pdf", "")
        record = {
            "title":          title,
            "authors":        [],
            "year":           None,
            "abstract":       abstract,
            "citation_count": 999,   # 手动标记为核心文献
            "track":          track,
            "url":            "",
            "tier":           "core"
        }
        papers.append(record)
        added.append(title)
        print(f"✓  {title[:55]}（PDF，{len(abstract)}字）")

# ── 保存并报告 ───────────────────────────────────────────────────
with open("papers/all_papers_clean.json", "w", encoding="utf-8") as f:
    json.dump(papers, f, ensure_ascii=False, indent=2)

print(f"\n── 完成 ──")
print(f"新增：{len(added)}篇")
print(f"总计：{len(papers)}篇")
print("\n新增列表：")
for t in added:
    print(f"  · {t[:60]}")