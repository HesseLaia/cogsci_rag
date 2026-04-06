"""
CogSci RAG 问答系统 v3
- 生成层换成 OpenRouter API（告别小模型翻译腔）
- 对话风格：苏格拉底式追问 + 学术翻译官 + 学者朋友 + 结论先行

运行前：
  pip install chromadb sentence-transformers requests
  把下面的 OPENROUTER_API_KEY 换成你的真实key
"""

import json
import logging
import os
import re
from datetime import datetime
import chromadb
import requests
from sentence_transformers import SentenceTransformer

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
else:
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── 配置 ─────────────────────────────────────────────────────────
PAPERS_PATH = "data/all_papers_fulltext.json"
CHROMA_DIR        = "chroma_db"
COLLECTION        = "cogsci_papers"
EMBED_MODEL       = "all-MiniLM-L6-v2"
OLLAMA_URL        = "http://localhost:11434/api/generate"

# 从环境变量读取 OpenRouter API Key（含从项目根 .env 自动加载，需安装 python-dotenv）
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip().strip('"').strip("'")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"

TOP_K          = 6
MIN_CITATIONS  = 10

TRACK_NAMES = {
    "psychological_science":  "心理科学",
    "cognitive_neuroscience": "认知神经科学",
    "cognitive_modeling_AI":  "认知建模与AI",
    "social_sciences":        "社会科学与人文",
    "linguistics":            "语言学",
    "philosophy":             "心智哲学",
}

INTEREST_LETTER_TO_TRACK = {
    "A": "philosophy",
    "B": "cognitive_neuroscience",
    "C": "cognitive_modeling_AI",
    "D": "linguistics",
    "E": "social_sciences",
}


def _normalize_track_weights(weights):
    s = sum(weights.values())
    if s <= 0:
        return
    for k in list(weights.keys()):
        weights[k] = weights[k] / s


def _init_track_weights_from_questionnaire(weights, interest_letters):
    if not interest_letters:
        return
    for c in str(interest_letters).strip().upper():
        tr = INTEREST_LETTER_TO_TRACK.get(c)
        if tr:
            weights[tr] = weights.get(tr, 0) + 1.0
    if weights:
        _normalize_track_weights(weights)


def _update_track_weights_from_docs(weights, retrieved_docs):
    for d in retrieved_docs or []:
        tr = (d.get("track") or "").strip()
        if not tr:
            continue
        if tr not in weights:
            weights[tr] = 0.1
        weights[tr] += 0.1
    if weights:
        _normalize_track_weights(weights)


SYSTEM_PROMPT = """你是一位认知科学领域的学者，正在帮一位朋友学习认知科学。

【用户画像】
{user_profile}

【你的风格】
- 距离感：平等、亲切，像在研究室里喝咖啡聊天。会和对方一起吐槽某个实验设计的坑，用词现代，偶尔幽默，但不失专业。
- 每次回答开头可以用一句括号内的动作描写营造对话感，动作必须和内容有关，例如（在白板上画个箭头）、（翻到论文第三页）。不是每次都要加，但加了必须有意义。
- 专业术语第一次出现时用括号给英文原文，例如：预测编码（predictive coding）
- 引用论文时用[1][2]标注，引用时必须说清楚这篇论文做了什么、发现了什么，不能只写"研究发现[1]"这种空引用
- 如果知识库论文不足以回答，直接说"我知识库里关于这个的资料不多"，然后用通用知识补充
- 全程中文，不要寒暄，直接开始回答

【输出结构——每次必须严格按照以下四部分输出，不得省略】

**结论**
一句话直接回答问题核心，不超过40字。

**展开**
3-5段，每段聚焦一个角度，每段不少于100字。每段结构：
- 第一句：这个角度的核心观点
- 第二句：背后的机制或原理是什么
- 第三句：一个具体例子、实验发现或反例
跨概念问题必须解释两个概念之间的逻辑链条，不能分别介绍后就结束。
如有引用，说清楚论文做了什么实验、得出什么结论。

**和你聊聊**
一个苏格拉底式追问，必须和用户这次的问题直接相关，不能泛泛而谈。
追问本身要有一定挑战性，不是问"你觉得呢"这种开放到无边界的问题。

【你不是什么】
- 不是卑微的助手，不需要说"好的！我来帮你解答"
- 不是严肃教授，不需要每句话都引用文献
- 不要用"总的来说""综上所述"收尾"""


INTRO_SYSTEM_PROMPT = """你是认知科学领域的学者，正在给一个朋友介绍一个新方向。

【用户画像】
{user_profile}

风格：严谨但平等、结论先行、善用类比，末尾留一个苏格拉底式追问。
根据用户画像选择类比的来源领域——有心理学背景就从心理学概念类比，有计算机背景就从算法类比。

【输出结构——严格按照以下顺序，不得省略或合并】

**这个方向是干什么的**
一句话，类比优先，让完全不了解的人也能抓住核心。

**三个必须知道的概念**
每个概念：名称（英文）+ 一句大白话 + 一个生活中能碰到的例子。
不要只是定义，要说清楚为什么这个概念重要。

**从哪里开始最不痛苦**
推荐一篇论文或一个概念作为入口，说清楚为什么推荐这个而不是别的。
如果知识库里有合适的，优先推荐知识库内容并标注来源。

**让你想继续探索的问题**
一个追问，要有具体指向，不是"你对这个方向有什么想法"这种问题。

全程中文，300-500字。"""

CONCEPT_MAP_PROMPT = """你是认知科学领域的学者，现在需要对用户提供的概念生成一个结构化的概念地图。

【用户画像】
{user_profile}

【输出要求】
必须返回严格的 JSON 格式，不要任何额外文字。结构如下：
{{
  "core": "核心定义（一句话，不超过50字）",
  "related": [
    {{"concept": "相关概念1", "relation": "与核心概念的关系说明"}},
    {{"concept": "相关概念2", "relation": "与核心概念的关系说明"}}
  ],
  "debate": "主要争议点（一句话，如果没有争议就说"共识程度较高"）",
  "key_figures": ["代表人物1", "代表人物2"],
  "entry_point": "推荐入门论文或概念（优先推荐知识库中的内容）"
}}

基于以下知识库内容，生成上述 JSON："""

SURVEY_PROMPT = """你是认知科学领域的学者，现在需要生成一篇关于指定主题的文献综述。

【用户画像】
{user_profile}

【输出结构——严格按照以下四段输出】

## 背景与问题定义
这个 topic 研究的核心问题是什么，为什么重要。

## 主要发现
分3-5点，每点必须：
- 明确说这是什么发现
- 绑定具体论文引用（格式：XX等人[序号]在XX实验中发现...）
- 不能只写"研究发现[1]"这种空引用

## 现存争议
至少一个争议点。如果没有明显争议，说明共识程度高，并解释为什么达成共识。

## 未解问题与前沿方向
2-3个具体的未解问题，要有可操作性，不是泛泛而谈。

全程中文，800-1200字。引用时必须说清楚论文做了什么。"""

HYPOTHESIS_PROMPT = """你是认知科学领域的学者，现在需要帮研究者生成可检验的研究假设和实验设计思路。

【用户画像】
{user_profile}

【输出结构——严格按照以下四部分输出】

## 理论基础
基于检索到的论文，说明这个研究问题可以从哪些已有发现或理论出发。
每个理论基础必须绑定具体文献[序号]。

## 可检验假设
2-3个假设，每个格式为：
**假设N**：如果X（自变量），那么Y（因变量），可以通过Z实验/测量方法验证。

## 潜在混淆变量
需要控制什么变量，为什么。

## 相关实验范式
知识库里有没有类似的实验设计可以参考，如果有就标注来源[序号]。

全程中文，600-900字。"""

active_system_prompt = SYSTEM_PROMPT    # 默认值，main()里会覆盖
active_intro_prompt = INTRO_SYSTEM_PROMPT

# 用户画像问卷和生成逻辑
USER_PROFILE_QUESTIONS = [
    {
        "key": "background",
        "question": "你的知识背景最接近哪个？",
        "options": {
            "A": "心理学",
            "B": "神经科学",
            "C": "哲学",
            "D": "计算机 / AI",
            "E": "其他理科",
            "F": "人文社科"
        }
    },
    {
        "key": "level",
        "question": "你自学认知科学大概多久了？",
        "options": {
            "A": "刚开始，基本没基础",
            "B": "几个月，了解一些概念",
            "C": "一年以上，有一定系统认识"
        }
    },
    {
        "key": "style",
        "question": "遇到新概念，你更喜欢哪种解释方式？",
        "options": {
            "A": "先给个生活化比喻，再讲原理",
            "B": "直接讲机制，不需要比喻",
            "C": "先讲历史背景和这个概念是怎么来的，再讲内容"
        }
    },
    {
        "key": "math",
        "question": "你对数学 / 计算的接受程度？",
        "options": {
            "A": "尽量避免公式，讲直觉就好",
            "B": "可以有一点，但需要解释",
            "C": "没问题，可以直接用"
        }
    },
    {
        "key": "interest",
        "question": "你最感兴趣的方向是？（输入字母，可多选，如 ACD）",
        "options": {
            "A": "意识和主观体验",
            "B": "大脑的具体机制",
            "C": "AI 和认知的关系",
            "D": "语言和思维",
            "E": "社会认知和人际"
        }
    }
]

def build_user_profile(answers: dict) -> str:
    """把问卷答案转成注入prompt的画像文字"""
    bg_map = {
        "A": "心理学", "B": "神经科学", "C": "哲学",
        "D": "计算机/AI", "E": "理科", "F": "人文社科"
    }
    level_map = {
        "A": "刚刚入门，基本没有基础",
        "B": "自学几个月，了解一些概念",
        "C": "自学一年以上，有一定系统认识"
    }
    style_map = {
        "A": "先用生活类比，再讲原理",
        "B": "直接讲机制，不需要比喻",
        "C": "先讲历史背景，再讲内容"
    }
    math_map = {
        "A": "尽量避免公式",
        "B": "可以有公式但需要解释",
        "C": "可以直接用数学"
    }
    interest_map = {
        "A": "意识和主观体验",
        "B": "大脑机制",
        "C": "AI与认知的关系",
        "D": "语言与思维",
        "E": "社会认知"
    }

    bg = bg_map.get(answers.get("background", "A"), "心理学")
    level = level_map.get(answers.get("level", "A"), "刚刚入门")
    style = style_map.get(answers.get("style", "A"), "先用类比再讲原理")
    math = math_map.get(answers.get("math", "A"), "尽量避免公式")

    interest_raw = answers.get("interest", "A")
    interests = [interest_map[c] for c in interest_raw.upper() if c in interest_map]
    interest_str = "、".join(interests) if interests else "认知科学整体"

    profile = f"""用户有{bg}背景，{level}。
解释风格偏好：{style}。
数学接受度：{math}。
最感兴趣的方向：{interest_str}。
在解释概念时，优先从{bg}的已知概念出发做类比，帮助用户建立连接而不是从零开始。"""

    return profile


def build_system_prompt(questionnaire_profile, cognitive_summary=""):
    """拼出注入 SYSTEM_PROMPT / INTRO_SYSTEM_PROMPT 的 {user_profile} 全文。"""
    p = questionnaire_profile or ""
    cs = (cognitive_summary or "").strip()
    if not cs:
        return p
    p = p + "\n\n【用户近期认知状态】\n" + cs
    p += (
        "\n\n【如何使用以上认知状态】\n"
        "- understanding_level 是 heard_of 的概念：从类比开始，不要直接讲机制\n"
        "- understanding_level 是 intuitive 的：可以开始引入机制，用 preferred_angle "
        "对应的领域做桥梁\n"
        "- understanding_level 是 can_explain 的：直接讨论，可以挑战用户的理解\n"
        "- stuck_points 里的子问题：主动拆解，不要回避\n"
        "- 检测到用户在重复问同一个概念（mentions > 3）：说明上次没讲透，"
        "换一个角度重新解释，不要重复上次的类比"
    )
    return p


USER_MEMORY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "user_memory.json"
)


def load_memory():
    if not os.path.exists(USER_MEMORY_PATH):
        return {}
    with open(USER_MEMORY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    tw = data.get("interests", {}).get("track_weights")
    if not tw:
        return {}
    return tw


class SessionMemory:
    def __init__(self, session_id):
        self.session_id = session_id
        self.history = []
        self.current_topics = []
        self.max_history = 10

    def add_turn(self, user_input, assistant_response, retrieved_docs):
        topics = self._extract_topics(user_input)
        for t in topics:
            if t in self.current_topics:
                self.current_topics.remove(t)
            self.current_topics.append(t)
        self.current_topics = self.current_topics[-5:]

        turn = {
            "turn": len(self.history) + 1,
            "user": user_input,
            "assistant_summary": self._summarize(assistant_response),
            "retrieved_docs": [
                (d.get("book_title") or d.get("title", ""))
                for d in (retrieved_docs or [])
            ],
            "timestamp": datetime.now().isoformat(),
        }
        self.history.append(turn)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]
        return topics

    def get_recent_context(self, n=3):
        if not self.history:
            return ""
        recent = self.history[-n:]
        lines = []
        for t in recent:
            lines.append(
                "第{}轮 - 用户：{}；摘要：{}".format(
                    t["turn"], t["user"], t["assistant_summary"]
                )
            )
        return "\n".join(lines)

    def detect_follow_up(self, user_input):
        follow_up_signals = [
            "这个",
            "详细",
            "展开",
            "继续",
            "那么",
            "那",
            "它",
            "刚才",
            "上文",
            "前面说的",
        ]
        return any(sig in user_input for sig in follow_up_signals)

    def _extract_topics(self, text):
        cogsci_terms = [
            "预测编码",
            "注意力",
            "工作记忆",
            "意识",
            "镜像神经元",
            "贝叶斯",
            "自由能",
            "神经网络",
            "强化学习",
            "情绪",
            "双语",
        ]
        return [term for term in cogsci_terms if term in text]

    def _summarize(self, response):
        if len(response) < 150:
            return response
        lines = [ln for ln in response.strip().split("\n") if ln.strip()]
        if len(lines) <= 2:
            return response[:150] + "..."
        for i, line in enumerate(lines):
            if "**结论**" in line or "**展开**" in line:
                if i + 1 < len(lines):
                    return lines[i + 1][:150]
        return lines[0][:150] + "..."


class UserMemory:
    def __init__(self, memory_file=None):
        self.memory_file = memory_file or USER_MEMORY_PATH
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "cognitive_summary" not in data:
                    data["cognitive_summary"] = ""
                if "interests" in data and "track_weights" not in data["interests"]:
                    data["interests"]["track_weights"] = {}
                for topic, info in data.get("interests", {}).get("topics", {}).items():
                    if "understanding_level" not in info:
                        info["understanding_level"] = "intuitive"
                    if "preferred_angle" not in info:
                        info["preferred_angle"] = ""
                    if "stuck_points" not in info:
                        info["stuck_points"] = []
                if "last_summary_at" not in data.get("interaction_stats", {}):
                    data.setdefault("interaction_stats", {})["last_summary_at"] = 0
                return data
        return {
            "interests": {"topics": {}, "track_weights": {}},
            "cognitive_summary": "",
            "interaction_stats": {"total_questions": 0, "last_summary_at": 0},
        }

    def save(self):
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def record_turn_after(self, topics, retrieved_docs=None, interest_letters=None):
        stats = self.data.setdefault("interaction_stats", {})
        stats["total_questions"] = stats.get("total_questions", 0) + 1
        if topics:
            today = datetime.now().strftime("%Y-%m-%d")
            bucket = self.data.setdefault("interests", {}).setdefault("topics", {})
            for topic in topics:
                if topic not in bucket:
                    bucket[topic] = {"mentions": 0, "last_asked": None}
                bucket[topic]["mentions"] = bucket[topic].get("mentions", 0) + 1
                bucket[topic]["last_asked"] = today
        interests = self.data.setdefault("interests", {})
        weights = interests.setdefault("track_weights", {})
        if not weights and interest_letters:
            _init_track_weights_from_questionnaire(weights, interest_letters)
        _update_track_weights_from_docs(weights, retrieved_docs)
        self.save()

    def get_top_interests(self, n=5):
        topics = self.data.get("interests", {}).get("topics", {})
        if not topics:
            return []
        sorted_topics = sorted(
            topics.items(),
            key=lambda x: x[1].get("mentions", 0),
            reverse=True,
        )
        return [t[0] for t in sorted_topics[:n]]


CONCEPT_ANALYSIS_PROMPT = """分析以下对话，提取用户的认知状态。
用户问题：__QUESTION__
用户背景：__PROFILE__

只输出JSON，不要任何其他文字：
{
  "concept": "本次对话最核心的一个概念（中文，2-6字）",
  "understanding_level": "heard_of或intuitive或can_explain或critical之一",
  "preferred_angle": "用户用来理解这个概念的类比来源领域，如心理学/神经科学/哲学/计算机，没有明显倾向则填空字符串",
  "stuck_points": ["用户明显困惑或回避的子问题，没有则返回空数组"]
}

判断标准：
- heard_of：只是提到，没有展开追问
- intuitive：能用自己的话描述，但依赖类比
- can_explain：能问出机制层面的问题
- critical：能指出局限或提出反例"""


def update_concept_understanding(user_question, user_memory, user_profile_brief=""):
    """
    分析用户问题与背景，更新概念理解状态。
    JSON 解析失败时会在控制台打印模型原始输出；其它异常仍静默跳过。
    """
    q = (user_question or "")[:200]
    pb = (user_profile_brief or "")[:800]
    prompt = (
        CONCEPT_ANALYSIS_PROMPT.replace("__QUESTION__", q).replace("__PROFILE__", pb)
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cogsci-rag.local",
        "X-Title": "CogSci RAG"
    }
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": prompt}
        ],
        "temperature": 0,
        "max_tokens": 200
    }

    try:
        proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        resp = requests.post(OPENROUTER_URL, headers=headers, json=body,
                             timeout=30, proxies=proxies, verify=False)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            print("[update_concept_understanding] JSON 解析失败，模型原始输出：")
            print(content)
            return

        concept = result.get("concept", "")
        if not concept:
            return

        topics = user_memory.data.setdefault("interests", {}).setdefault("topics", {})
        if concept not in topics:
            topics[concept] = {
                "mentions": 1,
                "last_asked": datetime.now().strftime("%Y-%m-%d"),
                "understanding_level": "intuitive",
                "preferred_angle": "",
                "stuck_points": []
            }

        topics[concept]["understanding_level"] = result.get("understanding_level", "intuitive")
        angle = result.get("preferred_angle", "")
        if angle:
            topics[concept]["preferred_angle"] = angle

        stuck = result.get("stuck_points", [])
        if stuck:
            existing = set(topics[concept].get("stuck_points", []))
            existing.update(stuck)
            topics[concept]["stuck_points"] = list(existing)[:5]

        user_memory.save()

    except Exception:
        pass


def _clean_cognitive_summary_output(raw):
    s = raw
    while True:
        s = s.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            s = s[1:-1]
            continue
        if len(s) >= 4 and s.startswith('\\"') and s.endswith('\\"'):
            s = s[2:-2]
            continue
        break
    s = re.sub(r'（[^）]*字[^）]*）', '', s)
    return s.strip()


COGNITIVE_SUMMARY_PROMPT = """基于用户的对话历史数据，生成一段认知状态摘要。

【输出要求】
- 不超过150字的中文
- 格式："用户对X理解较深，倾向从Y角度切入；对Z概念有兴趣但停留在直觉层；最近频繁问A类问题，可以适当深入B方向"
- 突出理解深度差异、卡点、倾向的角度

【用户数据】
{user_data}"""


def generate_cognitive_summary(user_memory):
    """
    每5次对话后生成认知状态摘要
    触发条件：total_questions % 5 == 0 且 > last_summary_at
    """
    stats = user_memory.data.get("interaction_stats", {})
    total = stats.get("total_questions", 0)
    last_gen = stats.get("last_summary_at", 0)

    if total % 5 != 0 or total <= last_gen:
        return

    topics = user_memory.data.get("interests", {}).get("topics", {})
    if not topics:
        return

    level_map = {"heard_of": "初识", "intuitive": "直觉", "can_explain": "能解释", "critical": "批判性"}
    topic_lines = []
    for concept, info in sorted(topics.items(), key=lambda x: x[1].get("mentions", 0), reverse=True)[:8]:
        level = level_map.get(info.get("understanding_level", "intuitive"), "直觉")
        angle = info.get("preferred_angle", "")
        stuck = info.get("stuck_points", [])
        line = f"- {concept}（{level}层，{info.get('mentions', 0)}次）"
        if angle:
            line += f"，倾向{angle}角度"
        if stuck:
            line += f"，卡点：{'、'.join(stuck[:2])}"
        topic_lines.append(line)

    user_data_text = "\n".join(topic_lines)

    prompt = COGNITIVE_SUMMARY_PROMPT.format(user_data=user_data_text)
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cogsci-rag.local",
        "X-Title": "CogSci RAG"
    }
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 300
    }

    try:
        proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        resp = requests.post(OPENROUTER_URL, headers=headers, json=body,
                             timeout=30, proxies=proxies, verify=False)
        resp.raise_for_status()
        summary = _clean_cognitive_summary_output(
            resp.json()["choices"][0]["message"]["content"]
        )
        n = len(summary)
        if n < 20 or n > 200:
            logging.warning(
                "cognitive_summary 清洗后长度为 %d，不在 20–200 建议范围内，仍写入",
                n,
            )

        user_memory.data["cognitive_summary"] = summary
        user_memory.data["interaction_stats"]["last_summary_at"] = total
        user_memory.save()

    except Exception:
        pass


def run_profile_questionnaire() -> str:
    """运行问卷，返回用户画像字符串"""
    print("\n── 在开始之前，花30秒让我了解一下你 ──\n")
    answers = {}
    for q in USER_PROFILE_QUESTIONS:
        print(q["question"])
        for k, v in q["options"].items():
            print(f"  {k}. {v}")
        while True:
            ans = input("你的选择：").strip().upper()
            # 多选题允许多个字母
            if q["key"] == "interest":
                if all(c in q["options"] for c in ans) and len(ans) > 0:
                    answers[q["key"]] = ans
                    break
                else:
                    print("请输入选项中的字母，可多选")
            else:
                if ans in q["options"]:
                    answers[q["key"]] = ans
                    break
                else:
                    print("请输入选项中的字母")
        print()

    profile = build_user_profile(answers)
    print("── 好，我大概了解你了。开始吧 ──\n")
    return profile


# ── 全局embedder缓存 ─────────────────────────────────────────────
_embedder = None
_collection_global = None

def get_embedder():
    global _embedder
    if _embedder is None:
        print("加载向量模型（首次约10秒）...")
        _embedder = SentenceTransformer(EMBED_MODEL)
        print("[OK] 向量模型就绪")
    return _embedder


# ── 加载论文 ─────────────────────────────────────────────────────
def load_papers():
    with open(PAPERS_PATH, "r", encoding="utf-8") as f:
        papers = json.load(f)
    print(f"[OK] 论文知识库：{len(papers)} 篇")
    return papers


# ── 建/加载向量库 ────────────────────────────────────────────────
def build_or_load_vectorstore(papers):
    global _collection_global
    client   = chromadb.PersistentClient(path=CHROMA_DIR)
    existing = [c.name for c in client.list_collections()]

    if COLLECTION in existing:
        col = client.get_collection(COLLECTION)
        peek = col.get(limit=1, include=["metadatas"])
        m0 = (peek.get("metadatas") or [None])[0] or {}
        if not m0.get("source_type"):
            print(
                "[警告] 向量库元数据缺少 source_type，混合检索将回退为旧版检索。"
                "请删除 chroma_db 后重启以重建向量库。"
            )
        print(f"[OK] 向量库：{col.count()} 条")
        _collection_global = col
        return col

    print("首次构建向量库（约1-2分钟）...")
    embedder = get_embedder()
    ids, texts, metas = [], [], []

    for i, p in enumerate(papers):
        title = p.get("title", "")
        if not title:
            continue
        ids.append(str(i))
        content = p.get("fulltext") or p.get("abstract", "")
        texts.append(f"{title}\n\n{content}")
        src_type = p.get("source_type") or (
            "book" if p.get("source") == "book" else "paper"
        )
        bt = p.get("book_title") or ""
        ch = p.get("chapter") or ""
        metas.append({
            "title":          title,
            "authors":        ", ".join(p.get("authors", [])),
            "year":           str(p.get("year", "")),
            "track":          p.get("track", ""),
            "citation_count": str(p.get("citation_count") or "0"),
            "url":            p.get("url", ""),
            "tier":           p.get("tier", ""),
            "source_type":    src_type,
            "book_title":     bt,
            "chapter":        ch,
        })

    col = client.create_collection(COLLECTION)
    for s in range(0, len(texts), 50):
        e = min(s + 50, len(texts))
        col.add(
            ids=ids[s:e],
            embeddings=embedder.encode(texts[s:e]).tolist(),
            documents=texts[s:e],
            metadatas=metas[s:e],
        )
        print(f"  {e}/{len(texts)}")

    print(f"[OK] 向量库构建完成")
    _collection_global = col
    return col


def _meta_passes_citation(meta, min_cite):
    cite = int(meta.get("citation_count") or 0)
    tier = meta.get("tier", "")
    return cite >= min_cite or tier == "recent"


def _collection_has_source_type(collection):
    peek = collection.get(limit=1, include=["metadatas"])
    m0 = (peek.get("metadatas") or [None])[0] or {}
    return bool(m0.get("source_type"))


def classify_query_intent(query):
    if re.search(r"(是什么|定义|怎么理解|如何理解)[\?？]?$", query):
        return {"intent": "concept", "book_weight": 0.7, "paper_weight": 0.3}
    if re.search(r"(哪些实验|哪些研究|哪些论文|有什么证据)[\?？]?$", query):
        return {"intent": "evidence", "book_weight": 0.2, "paper_weight": 0.8}

    concept_keywords = {
        "是什么": 3,
        "定义": 3,
        "机制": 2,
        "原理": 2,
        "如何工作": 2,
        "入门": 3,
        "概念": 2,
        "理论": 2,
    }
    evidence_keywords = {
        "实验": 2,
        "研究发现": 3,
        "研究": 1.5,
        "数据": 2,
        "哪些论文": 4,
        "证明": 2,
        "结果": 1.5,
        "发现": 2,
    }
    frontier_keywords = {
        "最新": 3,
        "近年": 2,
        "2020": 2,
        "2025": 2,
        "前沿": 3,
        "趋势": 2,
    }

    concept_score = sum(
        w for kw, w in concept_keywords.items() if kw in query
    )
    evidence_score = sum(
        w for kw, w in evidence_keywords.items() if kw in query
    )
    frontier_score = sum(
        w for kw, w in frontier_keywords.items() if kw in query
    )

    first_10 = query[:10]
    if any(kw in first_10 for kw in concept_keywords):
        concept_score *= 1.5
    if any(kw in first_10 for kw in evidence_keywords):
        evidence_score *= 1.5
    if frontier_score > 2:
        evidence_score += frontier_score

    if concept_score > evidence_score * 1.5:
        return {"intent": "concept", "book_weight": 0.7, "paper_weight": 0.3}
    if evidence_score > concept_score * 1.5:
        return {"intent": "evidence", "book_weight": 0.2, "paper_weight": 0.8}
    return {"intent": "mixed", "book_weight": 0.5, "paper_weight": 0.5}


def _doc_from_chroma(meta, document):
    title = meta.get("title", "")
    body = document.split("\n\n", 1)[-1] if "\n\n" in document else document
    snippet = body[:500]
    cite = int(meta.get("citation_count") or 0)
    st = meta.get("source_type") or "paper"
    d = {
        "title": title,
        "authors": meta.get("authors", ""),
        "year": meta.get("year", ""),
        "track": meta.get("track", ""),
        "citations": cite,
        "url": meta.get("url", ""),
        "abstract": snippet,
        "source_type": st,
    }
    if st == "book":
        d["book_title"] = meta.get("book_title", "")
        d["chapter"] = meta.get("chapter", "")
    return d


# ── 检索 ─────────────────────────────────────────────────────────
def retrieve(query, collection):
    track_weights = load_memory()
    embedder    = get_embedder()
    q_emb       = embedder.encode([query]).tolist()
    raw         = collection.query(query_embeddings=q_emb, n_results=TOP_K * 3)
    dist_row = raw.get("distances")
    dists = dist_row[0] if dist_row else None

    def _vec_sim(i):
        if dists is None or i >= len(dists):
            return 1.0
        d0 = dists[i]
        if d0 is None:
            return 1.0
        return 1.0 / (1.0 + float(d0))

    scored, seen = [], set()

    for i in range(len(raw["ids"][0])):
        meta  = raw["metadatas"][0][i]
        title = meta.get("title", "")
        if title in seen:
            continue
        seen.add(title)
        cite = int(meta.get("citation_count") or 0)
        tier = meta.get("tier", "")
        if cite < MIN_CITATIONS and tier != "recent":
            continue
        st = meta.get("source_type") or "paper"
        doc = {
            "title":    title,
            "authors":  meta.get("authors", ""),
            "year":     meta.get("year", ""),
            "track":    meta.get("track", ""),
            "citations": cite,
            "url":      meta.get("url", ""),
            "abstract": raw["documents"][0][i].split("\n\n", 1)[-1][:500],
            "source_type": st,
        }
        if st == "book":
            doc["book_title"] = meta.get("book_title", "")
            doc["chapter"] = meta.get("chapter", "")
        tr = meta.get("track", "") or ""
        w = float(track_weights.get(tr, 0) or 0)
        adj = _vec_sim(i) * (1.0 + w * 0.5)
        scored.append((adj, doc))

    scored.sort(key=lambda x: -x[0])
    docs = [p[1] for p in scored[:TOP_K]]

    # 兜底：不够3篇则放宽引用限制
    if len(docs) < 3:
        for i in range(len(raw["ids"][0])):
            meta  = raw["metadatas"][0][i]
            title = meta.get("title", "")
            if title in seen:
                continue
            seen.add(title)
            st = meta.get("source_type") or "paper"
            doc = {
                "title":   title,
                "authors": meta.get("authors", ""),
                "year":    meta.get("year", ""),
                "track":   meta.get("track", ""),
                "citations": int(meta.get("citation_count") or 0),
                "url":     meta.get("url", ""),
                "abstract": raw["documents"][0][i].split("\n\n", 1)[-1][:500],
                "source_type": st,
            }
            if st == "book":
                doc["book_title"] = meta.get("book_title", "")
                doc["chapter"] = meta.get("chapter", "")
            docs.append(doc)
            if len(docs) >= 3:
                break
    return docs


def hybrid_retrieve(query, collection):
    if not _collection_has_source_type(collection):
        return retrieve(query, collection)

    embedder = get_embedder()
    q_emb = embedder.encode([query]).tolist()
    intent = classify_query_intent(query)["intent"]
    if intent == "concept":
        n_books, n_papers = 3, 2
    elif intent == "evidence":
        n_books, n_papers = 2, 4
    else:
        n_books, n_papers = 2, 3

    def pull_books(raw, cap, seen):
        out = []
        for i in range(len(raw["ids"][0])):
            meta = raw["metadatas"][0][i]
            title = meta.get("title", "")
            if title in seen:
                continue
            seen.add(title)
            out.append(_doc_from_chroma(meta, raw["documents"][0][i]))
            if len(out) >= cap:
                break
        return out

    def pull_papers(raw, cap, min_cite, seen):
        out = []
        for i in range(len(raw["ids"][0])):
            meta = raw["metadatas"][0][i]
            if meta.get("source_type") == "book":
                continue
            title = meta.get("title", "")
            if title in seen:
                continue
            if not _meta_passes_citation(meta, min_cite):
                continue
            seen.add(title)
            out.append(_doc_from_chroma(meta, raw["documents"][0][i]))
            if len(out) >= cap:
                break
        return out

    seen = set()
    raw_books = collection.query(
        query_embeddings=q_emb,
        n_results=max(n_books * 2, 6),
        where={"source_type": "book"},
    )
    books = pull_books(raw_books, n_books, seen)

    raw_papers = collection.query(
        query_embeddings=q_emb,
        n_results=max(n_papers * 3, 9),
        where={"source_type": "paper"},
    )
    papers = pull_papers(raw_papers, n_papers, MIN_CITATIONS, seen)

    if intent == "concept" and len(books) < n_books:
        extra = n_books - len(books)
        raw_p2 = collection.query(
            query_embeddings=q_emb,
            n_results=max((n_papers + extra) * 3, 12),
            where={"source_type": "paper"},
        )
        papers = pull_papers(raw_p2, n_papers + extra, MIN_CITATIONS, seen)

    if intent == "evidence" and len(papers) < n_papers:
        seen_ev = set(b["title"] for b in books)
        papers = pull_papers(raw_papers, n_papers, 5, seen_ev)

    if len(books) + len(papers) < 4:
        return retrieve(query, collection)

    return books + papers


def _build_library_context(docs):
    books = [d for d in docs if d.get("source_type") == "book"]
    papers = [d for d in docs if d.get("source_type") != "book"]
    if not books:
        return "\n\n".join([
            f"[{i+1}] {d['title']} ({d['year']}, 引用:{d['citations']})\n摘要：{d['abstract']}..."
            for i, d in enumerate(docs)
        ])

    parts = []
    idx = 1
    parts.append("=== 教材知识 ===")
    for d in books:
        bt = d.get("book_title") or d["title"]
        ch = d.get("chapter") or ""
        head = f"{bt}" + (f" — {ch}" if ch else "")
        parts.append(
            f"[{idx}] {head}\n{d['title']}\n摘录：{d['abstract']}..."
        )
        idx += 1
    parts.append("=== 研究论文 ===")
    for d in papers:
        parts.append(
            f"[{idx}] {d['title']} ({d['year']}, 引用:{d['citations']})\n摘要：{d['abstract']}..."
        )
        idx += 1
    return "\n\n".join(parts)


# ── OpenRouter生成 ────────────────────────────────────────────────
def ask_openrouter(question, docs, mode="qa", session_memory=None):
    context = _build_library_context(docs)

    if mode == "intro":
        user_msg  = f"请帮我介绍「{question}」这个认知科学方向。"
        sys_prompt = active_intro_prompt
    else:
        user_msg  = f"问题：{question}"
        sys_prompt = active_system_prompt

    hybrid_hint = ""
    if any(d.get("source_type") == "book" for d in docs):
        hybrid_hint = (
            "【知识库说明】下文分「教材知识」与「研究论文」；概念框架可优先依据教材，"
            "实验与实证可依据论文。引用时请对应序号并写出具体文献做了什么。\n\n"
        )

    memory_block = ""
    follow_hint = ""
    if session_memory and session_memory.history:
        if session_memory.detect_follow_up(question):
            mc = session_memory.get_recent_context(3)
            if mc:
                memory_block = "=== 对话历史 ===\n" + mc + "\n\n"
                follow_hint = (
                    "【说明】用户这句话可能延续上一轮话题，请结合对话历史理解指代。\n\n"
                )

    full_user = (
        f"{memory_block}{follow_hint}{hybrid_hint}"
        f"=== 知识库 ===\n{context}\n\n{user_msg}"
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://cogsci-rag.local",
        "X-Title":       "CogSci RAG"
    }
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system",  "content": sys_prompt},
            {"role": "user",    "content": full_user}
        ],
        "temperature": 0.7,
        "max_tokens":  1800
    }

    try:
        proxies = {
            "http": "http://127.0.0.1:7890",
            "https": "http://127.0.0.1:7890",
        }
        resp = requests.post(OPENROUTER_URL, headers=headers,
                             json=body, timeout=60, proxies=proxies, verify=False)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        return f"API错误 {resp.status_code}：{resp.text[:200]}"
    except Exception as e:
        return f"请求失败：{e}"


def ask_concept_map(topic, docs, user_profile=""):
    """
    生成概念地图（JSON格式）
    返回: dict 或 {"error": ..., "raw": ...}
    """
    context = _build_library_context(docs)
    sys_prompt = CONCEPT_MAP_PROMPT.replace("{user_profile}", user_profile)
    user_msg = f"=== 知识库 ===\n{context}\n\n请生成关于「{topic}」的概念地图 JSON。"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cogsci-rag.local",
        "X-Title": "CogSci RAG"
    }
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.3,
        "max_tokens": 1000
    }

    try:
        proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        resp = requests.post(OPENROUTER_URL, headers=headers, json=body,
                             timeout=60, proxies=proxies, verify=False)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        parsed = json.loads(content)
        return parsed
    except json.JSONDecodeError:
        return {"error": "JSON解析失败", "raw": content}
    except Exception as e:
        return {"error": str(e)}


def ask_survey(topic, docs, user_profile=""):
    """
    生成文献综述（检索量扩大到12篇）
    返回: (回答文本, 扩展后的docs列表)
    """
    global _collection_global
    if _collection_global is None:
        return "综述功能初始化失败", docs

    embedder = get_embedder()
    q_emb = embedder.encode([topic]).tolist()
    raw = _collection_global.query(query_embeddings=q_emb, n_results=36)

    enhanced_docs = []
    seen = set()
    for i in range(len(raw["ids"][0])):
        meta = raw["metadatas"][0][i]
        title = meta.get("title", "")
        if title in seen:
            continue
        seen.add(title)
        if not _meta_passes_citation(meta, MIN_CITATIONS):
            continue
        enhanced_docs.append(_doc_from_chroma(meta, raw["documents"][0][i]))
        if len(enhanced_docs) >= 12:
            break

    if len(enhanced_docs) < 12:
        for i in range(len(raw["ids"][0])):
            meta = raw["metadatas"][0][i]
            title = meta.get("title", "")
            if title in seen:
                continue
            seen.add(title)
            enhanced_docs.append(_doc_from_chroma(meta, raw["documents"][0][i]))
            if len(enhanced_docs) >= 12:
                break

    context = _build_library_context(enhanced_docs)
    sys_prompt = SURVEY_PROMPT.replace("{user_profile}", user_profile)
    user_msg = f"=== 知识库 ===\n{context}\n\n请生成关于「{topic}」的文献综述。"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cogsci-rag.local",
        "X-Title": "CogSci RAG"
    }
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.6,
        "max_tokens": 2000
    }

    try:
        proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        resp = requests.post(OPENROUTER_URL, headers=headers, json=body,
                             timeout=90, proxies=proxies, verify=False)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"], enhanced_docs
    except Exception as e:
        return f"综述生成失败：{e}", enhanced_docs


def ask_hypothesis(topic, docs, user_profile=""):
    """
    生成研究假设和实验设计思路
    返回: 回答文本
    """
    context = _build_library_context(docs)
    sys_prompt = HYPOTHESIS_PROMPT.replace("{user_profile}", user_profile)
    user_msg = f"=== 知识库 ===\n{context}\n\n研究问题：{topic}"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cogsci-rag.local",
        "X-Title": "CogSci RAG"
    }
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.7,
        "max_tokens": 1500
    }

    try:
        proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        resp = requests.post(OPENROUTER_URL, headers=headers, json=body,
                             timeout=60, proxies=proxies, verify=False)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"假设生成失败：{e}"


# ── 打印来源 ─────────────────────────────────────────────────────
def print_sources(docs):
    print("\n─── 检索到的来源 ──────────────────────────────────────")
    for i, d in enumerate(docs, 1):
        track_cn = TRACK_NAMES.get(d["track"], d["track"])
        cite_str = f"  {d['citations']}次引用" if d.get("citations") else ""
        if d.get("source_type") == "book":
            bt = d.get("book_title") or d["title"]
            ch = d.get("chapter") or ""
            extra = f" · {ch}" if ch else ""
            print(f"[{i}] [教材] {bt}{extra}")
        else:
            print(f"[{i}] {d['title']}")
        print(f"     {d['authors']} · {d['year']} · {track_cn}{cite_str}")
        if d.get("url"):
            print(f"     {d['url']}")
    print("────────────────────────────────────────────────────────")


HELP = """
命令：
  直接输入问题       普通问答
  入门 <方向>        例：入门 心智哲学
  统计               知识库论文分布
  帮助 / quit
"""


# ── 主循环 ───────────────────────────────────────────────────────
def main():
    print("=" * 56)
    print("  CogSci RAG v3  |  OpenRouter 驱动")
    print("  输入「帮助」查看命令")
    print("=" * 56)

    if not OPENROUTER_API_KEY:
        print("\n⚠ 未找到 OPENROUTER_API_KEY 环境变量，请先在系统中设置。\n")

    papers     = load_papers()
    collection = build_or_load_vectorstore(papers)
    get_embedder()

    user_profile = run_profile_questionnaire()

    user_mem = UserMemory()

    global active_system_prompt, active_intro_prompt

    def refresh_active_prompts():
        global active_system_prompt, active_intro_prompt
        p = build_system_prompt(
            user_profile, user_mem.data.get("cognitive_summary", "")
        )
        active_system_prompt = SYSTEM_PROMPT.replace("{user_profile}", p)
        active_intro_prompt = INTRO_SYSTEM_PROMPT.replace("{user_profile}", p)

    refresh_active_prompts()

    session_mem = SessionMemory(datetime.now().strftime("%Y%m%d_%H%M%S"))

    while True:
        print()
        user_input = input("你：").strip()
        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("拜拜～")
            break

        elif user_input in ("帮助", "help"):
            print(HELP)

        elif user_input == "统计":
            counts = {}
            for p in papers:
                k = TRACK_NAMES.get(p.get("track", ""), p.get("track", ""))
                counts[k] = counts.get(k, 0) + 1
            print()
            for k, n in sorted(counts.items(), key=lambda x: -x[1]):
                print(f"  {k:<12} {n:>4}篇  {'█' * (n // 3)}")
            print(f"\n  总计：{len(papers)} 篇")

        elif user_input.startswith("入门 "):
            topic = user_input[3:].strip()
            print(f"\n检索「{topic}」相关论文...")
            docs = hybrid_retrieve(topic, collection)
            print_sources(docs)
            print("\n生成入门指南中...\n")
            print("─── 入门指南 ────────────────────────────────────────")
            refresh_active_prompts()
            ans = ask_openrouter(
                topic, docs, mode="intro", session_memory=session_mem
            )
            print(ans)
            topics = session_mem.add_turn(user_input, ans, docs)
            user_mem.record_turn_after(topics, docs)
            update_concept_understanding(user_input, user_mem, user_profile)
            generate_cognitive_summary(user_mem)
            print("─────────────────────────────────────────────────────")

        else:
            print("\n检索相关论文...")
            docs = hybrid_retrieve(user_input, collection)
            print_sources(docs)
            print("\n回答中...\n")
            print("─── 回答 ────────────────────────────────────────────")
            refresh_active_prompts()
            ans = ask_openrouter(
                user_input, docs, mode="qa", session_memory=session_mem
            )
            print(ans)
            topics = session_mem.add_turn(user_input, ans, docs)
            user_mem.record_turn_after(topics, docs)
            update_concept_understanding(user_input, user_mem, user_profile)
            generate_cognitive_summary(user_mem)
            print("─────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()