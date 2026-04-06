# 模型底座与产品侧之间的承接层：“引擎”
---

## 方向一：概念地图 / 知识图谱
用户问一个概念，不只是给答案，而是返回"这个概念和哪些概念相关、争议在哪、代表人物是谁"的结构化视图。对学习者来说比单次问答价值高很多，也更容易做成可视化产品。
本质是改输出结构，在现有 `ask_openrouter` 基础上加一个新 mode。知识库已经够用，不需要改检索逻辑。

### 触发方式
用户输入以 `"地图 "` 开头（如 `"地图 预测编码"`）。

---

### 实现步骤

#### 1. 在 `cogsci_rag.py` 中新增（放在 `INTRO_SYSTEM_PROMPT` 后）

```python
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
```

#### 2. 新增函数 `ask_concept_map`（放在 `ask_openrouter` 函数后）

```python
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
        
        # 尝试解析 JSON
        parsed = json.loads(content)
        return parsed
    except json.JSONDecodeError:
        return {"error": "JSON解析失败", "raw": content}
    except Exception as e:
        return {"error": str(e)}
```

#### 3. 在 `app.py` 中修改（第193行附近）

**扩展模式判断**：
```python
# 原代码：
is_intro = user_input.startswith("入门")
topic = user_input[2:].strip() if is_intro else user_input

# 改为：
is_intro = user_input.startswith("入门")
is_concept_map = user_input.startswith("地图")
topic = user_input[2:].strip() if (is_intro or is_concept_map) else user_input
```

**扩展 mode 判断**（第205行附近）：
```python
# 原代码：
mode = "intro" if is_intro else "qa"

# 改为：
if is_concept_map:
    mode = "concept_map"
elif is_intro:
    mode = "intro"
else:
    mode = "qa"
```

**在生成回答分支中加入概念地图渲染**（第212-218行之间插入）：
```python
if mode == "concept_map":
    from cogsci_rag import ask_concept_map
    result = ask_concept_map(topic, docs, st.session_state.user_profile)
    
    if "error" not in result:
        st.markdown(f"### 核心定义\n{result['core']}")
        st.divider()
        
        st.markdown("### 相关概念")
        cols = st.columns(min(len(result['related']), 3))
        for i, rel in enumerate(result['related']):
            with cols[i % len(cols)]:
                st.info(f"**{rel['concept']}**\n\n{rel['relation']}")
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 争议点")
            st.warning(result['debate'])
        with col2:
            st.markdown("### 入门推荐")
            st.success(result['entry_point'])
        
        st.divider()
        st.markdown("### 代表人物")
        st.caption("、".join(result['key_figures']))
        
        answer = f"概念地图已生成（{topic}）"
    else:
        st.error(f"生成失败：{result.get('error')}")
        answer = result.get("raw", "生成失败")
else:
    # 原有的 ask_openrouter 逻辑
    with st.spinner("生成回答..."):
        answer = ask_openrouter(...)
```

#### 4. 更新侧边栏使用说明（`app.py` 第72行附近）

```python
st.markdown("""
- 直接输入问题 → 普通问答
- 以 **`入门`** 开头 → 方向导览  
  例：`入门 预测编码`
- 以 **`地图`** 开头 → 概念地图  
  例：`地图 工作记忆`
""")
```

---

### 改动清单
- ✅ 新增 `CONCEPT_MAP_PROMPT` 常量
- ✅ 新增 `ask_concept_map()` 函数
- ✅ `app.py` 扩展模式判断和渲染逻辑
- ❌ 不修改现有函数
- ❌ 不修改全局配置

---

## 方向二：文献综述自动生成
给定一个 topic，自动从知识库里拉相关论文，生成一份结构化综述（背景→主要发现→争议→未解问题）。这个对做研究的人很实用，也是知识引擎最直接的 B 端价值。
检索量要加大（TOP_K 临时调到 10-12），输出结构比问答更长更正式。

### 触发方式
用户输入以 `"综述 "` 开头（如 `"综述 工作记忆"`）。

---

### 实现步骤

#### 1. 在 `cogsci_rag.py` 顶部声明全局变量（第382行 `_embedder = None` 下方）

```python
_embedder = None
_collection_global = None  # 新增：供 ask_survey 使用
```

#### 2. 在 `build_or_load_vectorstore` 函数末尾添加（第458行 `return col` 前）

```python
def build_or_load_vectorstore(papers):
    global _collection_global  # 新增
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    # ... 原有逻辑 ...
    
    _collection_global = col  # 新增：赋值给全局变量
    return col
```

#### 3. 新增 `SURVEY_PROMPT` 常量（放在 `CONCEPT_MAP_PROMPT` 后）

```python
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
```

#### 4. 新增函数 `ask_survey`（放在 `ask_concept_map` 函数后）

```python
def ask_survey(topic, docs, user_profile=""):
    """
    生成文献综述（检索量扩大到12篇）
    返回: (回答文本, 扩展后的docs列表)
    """
    global _collection_global
    if _collection_global is None:
        return "综述功能初始化失败", docs
    
    # 临时扩大检索量到12篇
    embedder = get_embedder()
    q_emb = embedder.encode([topic]).tolist()
    raw = _collection_global.query(query_embeddings=q_emb, n_results=36)
    
    # 筛选逻辑复用 retrieve 的逻辑
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
    
    # 兜底：不够12篇则放宽引用限制
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
```

#### 5. 在 `app.py` 中修改

**扩展模式判断**（第193行附近）：
```python
is_intro = user_input.startswith("入门")
is_concept_map = user_input.startswith("地图")
is_survey = user_input.startswith("综述")  # 新增
topic = user_input[2:].strip() if (is_intro or is_concept_map or is_survey) else user_input
```

**扩展 mode 判断**（第205行附近）：
```python
if is_concept_map:
    mode = "concept_map"
elif is_survey:  # 新增
    mode = "survey"
elif is_intro:
    mode = "intro"
else:
    mode = "qa"
```

**在生成回答分支中加入综述模式**（在 `concept_map` 分支后插入）：
```python
elif mode == "survey":
    from cogsci_rag import ask_survey
    st.warning("⚠️ 综述基于知识库现有文献，不保证覆盖最新进展")
    with st.spinner("生成综述中（检索扩展到12篇）..."):
        answer, docs = ask_survey(topic, docs, st.session_state.user_profile)
    st.markdown(answer)
```

#### 6. 更新侧边栏使用说明（`app.py` 第72行附近）

```python
st.markdown("""
- 直接输入问题 → 普通问答
- 以 **`入门`** 开头 → 方向导览  
  例：`入门 预测编码`
- 以 **`地图`** 开头 → 概念地图  
  例：`地图 工作记忆`
- 以 **`综述`** 开头 → 文献综述  
  例：`综述 注意力机制`
""")
```

---

### 改动清单
- ✅ 新增 `_collection_global` 全局变量
- ✅ 在 `build_or_load_vectorstore` 中赋值给全局变量
- ✅ 新增 `SURVEY_PROMPT` 常量
- ✅ 新增 `ask_survey()` 函数（检索量临时12篇）
- ✅ `app.py` 扩展模式判断和渲染逻辑
- ❌ 不修改全局 `TOP_K`
- ❌ 不修改现有函数

---

## 方向三：用户认知建模
目前已有用户画像问卷了，这是个很好的起点。往深了做可以记录用户问过什么、卡在哪里、对哪类解释反应好，动态更新画像，让引擎越用越懂这个人。本质上是在做一个关于"人如何学习和理解"的数据飞轮。

### 核心思路

现有 `user_memory.json` 是对话历史日志，记录"问了什么、回答了什么"，本质是计数器。

**认知建模需要的是**：从日志提炼出结构化的用户认知状态
- ❌ 不是"他问过预测编码"
- ✅ 而是"他对预测编码的理解停留在直觉层面，对数学形式化还不适应，倾向于从神经科学角度类比"

需要补齐两层能力：
1. **理解深度标注**：从对话推断用户对每个概念的掌握程度
2. **认知状态摘要**：周期性生成自然语言摘要，注入 system prompt

---

### 实现步骤

#### 第一步：扩展 JSON 结构

修改 `user_memory.json` 的数据结构，不改变现有的读写逻辑，只扩展字段。

**新结构定义**：

```json
{
  "interests": {
    "topics": {
      "预测编码": {
        "mentions": 2,
        "last_asked": "2026-04-06",
        "understanding_level": "intuitive",
        "preferred_angle": "神经科学",
        "stuck_points": ["数学形式化"]
      }
    },
    "track_weights": {
      "cognitive_neuroscience": 0.4,
      "philosophy": 0.3,
      "cognitive_modeling_AI": 0.2,
      "linguistics": 0.1
    }
  },
  "cognitive_summary": "",
  "interaction_stats": {
    "total_questions": 11,
    "last_summary_at": 0
  }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `understanding_level` | string | 理解深度四档：`heard_of`（听说过）/ `intuitive`（直觉理解）/ `can_explain`（能解释）/ `critical`（批判性理解） |
| `preferred_angle` | string | 用户倾向从哪个角度理解这个概念（如"神经科学"、"计算模型"、"哲学"） |
| `stuck_points` | list | 用户明显回避或反复问的子问题（如"数学形式化"、"与XX的区别"） |
| `track_weights` | dict | 动态更新的方向权重，反映真实兴趣比问卷更准 |
| `cognitive_summary` | string | 每5次对话后自动生成的自然语言摘要，注入 system prompt |
| `last_summary_at` | int | 上次生成摘要时的 `total_questions` 值 |

**改动位置**：
- 在 `cogsci_rag.py` 的 `UserMemory._load()` 中扩展默认值（第313-320行）
- 保持现有读写逻辑不变，只修改初始化

```python
def _load(self):
    if os.path.exists(self.memory_file):
        with open(self.memory_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 向后兼容：为已有数据补充缺失字段
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
                data["interaction_stats"]["last_summary_at"] = 0
            return data
    return {
        "interests": {"topics": {}, "track_weights": {}},
        "cognitive_summary": "",
        "interaction_stats": {"total_questions": 0, "last_summary_at": 0},
    }
```

---

#### 第二步：生成回答时顺手打标

在 `ask_openrouter` 生成回答之后，新增一个 `update_concept_understanding()` 函数，用独立的 API 调用让模型分析这次对话。

**函数定义**（放在 `UserMemory` 类之后）：

```python
CONCEPT_ANALYSIS_PROMPT = """分析这次对话，判断用户对主要概念的理解状态。

【输出要求】
返回严格的 JSON 格式，不要额外文字：
{{
  "concept": "主要涉及的概念名（中文，不超过10字）",
  "understanding_level": "heard_of或intuitive或can_explain或critical",
  "preferred_angle": "用户倾向的角度（如神经科学/计算模型/哲学/语言学，可为空）",
  "stuck_points": ["用户明显不理解或回避的子问题，没有则为空数组"]
}}

【判断标准】
- heard_of: 初次接触，问"是什么"
- intuitive: 能理解类比，但问不出深层问题
- can_explain: 能提出机制性问题，追问细节
- critical: 质疑理论、比较不同观点

【对话内容】
用户问题：{user_question}
助手回答：{assistant_answer}"""


def update_concept_understanding(user_question, assistant_answer, user_memory):
    """
    异步分析对话，更新概念理解状态
    调用失败时静默跳过，不影响主流程
    """
    prompt = CONCEPT_ANALYSIS_PROMPT.format(
        user_question=user_question[:200],
        assistant_answer=assistant_answer[:500]
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
        
        # 解析 JSON
        result = json.loads(content)
        concept = result.get("concept", "")
        if not concept:
            return
        
        # 更新 user_memory
        topics = user_memory.data.setdefault("interests", {}).setdefault("topics", {})
        if concept not in topics:
            topics[concept] = {
                "mentions": 1,
                "last_asked": datetime.now().strftime("%Y-%m-%d"),
                "understanding_level": "intuitive",
                "preferred_angle": "",
                "stuck_points": []
            }
        
        # 更新字段
        topics[concept]["understanding_level"] = result.get("understanding_level", "intuitive")
        angle = result.get("preferred_angle", "")
        if angle:
            topics[concept]["preferred_angle"] = angle
        
        stuck = result.get("stuck_points", [])
        if stuck:
            existing = set(topics[concept].get("stuck_points", []))
            existing.update(stuck)
            topics[concept]["stuck_points"] = list(existing)[:5]  # 最多保留5个
        
        user_memory.save()
    
    except Exception as e:
        # 静默失败，不影响主流程
        pass
```

**调用位置**：
- 在 `main()` 的回答生成后（第891行附近）
- 在 `app.py` 的回答生成后（第247行附近）

```python
# main() 中（第891行附近）
ans = ask_openrouter(user_input, docs, mode="qa", session_memory=session_mem)
print(ans)
topics = session_mem.add_turn(user_input, ans, docs)
user_mem.record_turn_after(topics)

# 新增：异步分析概念理解状态
update_concept_understanding(user_input, ans, user_mem)  # 新增这一行
```

```python
# app.py 中（第247行附近）
topics = st.session_state.session_memory.add_turn(user_input, answer, docs)
st.session_state.user_memory.record_turn_after(topics)

# 新增：异步分析概念理解状态
from cogsci_rag import update_concept_understanding
update_concept_understanding(user_input, answer, st.session_state.user_memory)  # 新增这一行
```

---

#### 第三步：认知摘要生成与注入

新增 `generate_cognitive_summary()` 函数，触发条件：`total_questions` 是 5 的倍数，且比 `last_summary_at` 大。

**函数定义**（放在 `update_concept_understanding` 之后）：

```python
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
    
    # 检查触发条件
    if total % 5 != 0 or total <= last_gen:
        return
    
    # 整理用户数据
    topics = user_memory.data.get("interests", {}).get("topics", {})
    if not topics:
        return
    
    # 按理解深度分组
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
    
    # 调用模型生成摘要
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
        summary = resp.json()["choices"][0]["message"]["content"].strip()
        
        # 写入 user_memory
        user_memory.data["cognitive_summary"] = summary
        user_memory.data["interaction_stats"]["last_summary_at"] = total
        user_memory.save()
    
    except Exception as e:
        # 静默失败
        pass
```

**注入 System Prompt**：

修改 `main()` 和 `app.py` 中构建 system prompt 的逻辑：

```python
# main() 中（第836行附近）
user_profile = run_profile_questionnaire()

# 新增：注入认知摘要
cognitive_summary = user_mem.data.get("cognitive_summary", "")
if cognitive_summary:
    user_profile += f"\n\n【用户近期认知状态】\n{cognitive_summary}"

active_system_prompt = SYSTEM_PROMPT.replace("{user_profile}", user_profile)
active_intro_prompt = INTRO_SYSTEM_PROMPT.replace("{user_profile}", user_profile)
```

```python
# app.py 中（第197-198行附近）
sys_qa = SYSTEM_PROMPT.replace("{user_profile}", st.session_state.user_profile)
sys_intro = INTRO_SYSTEM_PROMPT.replace("{user_profile}", st.session_state.user_profile)

# 改为：
base_profile = st.session_state.user_profile
cognitive_summary = st.session_state.user_memory.data.get("cognitive_summary", "")
if cognitive_summary:
    base_profile += f"\n\n【用户近期认知状态】\n{cognitive_summary}"

sys_qa = SYSTEM_PROMPT.replace("{user_profile}", base_profile)
sys_intro = INTRO_SYSTEM_PROMPT.replace("{user_profile}", base_profile)
```

**调用时机**：

```python
# main() 中（第891行后）
topics = session_mem.add_turn(user_input, ans, docs)
user_mem.record_turn_after(topics)
update_concept_understanding(user_input, ans, user_mem)
generate_cognitive_summary(user_mem)  # 新增：检查是否需要生成摘要
```

```python
# app.py 中（第247行后）
topics = st.session_state.session_memory.add_turn(user_input, answer, docs)
st.session_state.user_memory.record_turn_after(topics)
update_concept_understanding(user_input, answer, st.session_state.user_memory)
from cogsci_rag import generate_cognitive_summary
generate_cognitive_summary(st.session_state.user_memory)  # 新增
```

---

### 改动清单

| 位置 | 改动内容 | 说明 |
|------|---------|------|
| `UserMemory._load()` | 扩展 JSON 结构初始化 | 向后兼容，为旧数据补充缺失字段 |
| `UserMemory` 类后 | 新增 `CONCEPT_ANALYSIS_PROMPT` 常量 | 概念理解分析 prompt |
| `UserMemory` 类后 | 新增 `update_concept_understanding()` 函数 | 异步分析对话，更新理解状态 |
| `update_concept_understanding` 后 | 新增 `COGNITIVE_SUMMARY_PROMPT` 常量 | 认知摘要生成 prompt |
| `update_concept_understanding` 后 | 新增 `generate_cognitive_summary()` 函数 | 每5次对话生成摘要 |
| `main()` 第836行 | 注入认知摘要到 system prompt | 扩展用户画像 |
| `main()` 第891行 | 调用两个新函数 | 打标 + 摘要 |
| `app.py` 第197行 | 注入认知摘要到 system prompt | 扩展用户画像 |
| `app.py` 第247行 | 调用两个新函数 | 打标 + 摘要 |

---

### 核心设计原则

✅ **非阻塞**：理解状态分析和摘要生成都在回答返回后异步执行，不影响用户体验

✅ **静默失败**：API 调用失败时不报错，不影响主流程

✅ **向后兼容**：旧 `user_memory.json` 数据自动补充缺失字段，不需要手动迁移

✅ **渐进增强**：
- 前5次对话：仅累计数据
- 第5次对话后：开始注入认知摘要到 system prompt
- 持续对话：每5次更新一次摘要，让 AI 越来越懂用户

---

### 预期效果

**初次使用**（第1-4次对话）：
- 系统仅依赖问卷画像
- 后台默默记录概念理解状态

**第5次对话后**：
- 生成第一份认知摘要，例如：  
  _"用户对预测编码有兴趣但停留在直觉层，倾向从神经科学角度类比；对自由能原理频繁提问，可适当深入贝叶斯推断基础；对数学形式化有回避倾向"_
- 此后所有回答都基于这份动态画像，自动调整解释策略

**长期使用**：
- 画像越来越精准，反映真实学习轨迹
- 可基于 `stuck_points` 主动推荐针对性内容
- 可基于 `understanding_level` 自动调整解释深度

---

## 方向四：研究假设生成器
给定一个研究问题，引擎从知识库里找相关理论和实验范式，帮研究者生成可检验的假设和实验设计思路。这个偏工具向，对学术用户价值高。
纯 prompt 工程，检索逻辑不变。

### 触发方式
用户输入以 `"假设 "` 开头（如 `"假设 双语者工作记忆"`）。

---

### 实现步骤

#### 1. 新增 `HYPOTHESIS_PROMPT` 常量（放在 `SURVEY_PROMPT` 后）

```python
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
```

#### 2. 新增函数 `ask_hypothesis`（放在 `ask_survey` 函数后）

```python
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
```

#### 3. 在 `app.py` 中修改

**扩展模式判断**（第193行附近）：
```python
is_intro = user_input.startswith("入门")
is_concept_map = user_input.startswith("地图")
is_survey = user_input.startswith("综述")
is_hypothesis = user_input.startswith("假设")  # 新增
topic = user_input[2:].strip() if (is_intro or is_concept_map or is_survey or is_hypothesis) else user_input
```

**扩展 mode 判断**（第205行附近）：
```python
if is_concept_map:
    mode = "concept_map"
elif is_survey:
    mode = "survey"
elif is_hypothesis:  # 新增
    mode = "hypothesis"
elif is_intro:
    mode = "intro"
else:
    mode = "qa"
```

**在生成回答分支中加入假设生成模式**（在 `survey` 分支后插入）：
```python
elif mode == "hypothesis":
    from cogsci_rag import ask_hypothesis
    with st.spinner("生成研究假设..."):
        answer = ask_hypothesis(topic, docs, st.session_state.user_profile)
    st.markdown(answer)
```

**修改来源面板的 expanded 参数**（第224行附近）：
```python
# 原代码：
with st.expander("📄 检索到的来源", expanded=False):

# 改为（根据模式动态调整）：
expanded_sources = (mode == "hypothesis")  # 假设模式下默认展开
with st.expander("📄 检索到的来源", expanded=expanded_sources):
```

#### 4. 更新侧边栏使用说明（`app.py` 第72行附近）

```python
st.markdown("""
- 直接输入问题 → 普通问答
- 以 **`入门`** 开头 → 方向导览  
  例：`入门 预测编码`
- 以 **`地图`** 开头 → 概念地图  
  例：`地图 工作记忆`
- 以 **`综述`** 开头 → 文献综述  
  例：`综述 注意力机制`
- 以 **`假设`** 开头 → 研究假设生成  
  例：`假设 双语者工作记忆优势`
""")
```

---

### 改动清单
- ✅ 新增 `HYPOTHESIS_PROMPT` 常量
- ✅ 新增 `ask_hypothesis()` 函数
- ✅ `app.py` 扩展模式判断和渲染逻辑
- ✅ 假设模式下来源面板默认展开
- ❌ 不修改现有函数
- ❌ 不修改检索逻辑（使用默认 TOP_K）

---

## 整体架构总结

### 新增文件结构
无新增文件，所有改动均在现有 `cogsci_rag.py` 和 `app.py` 中。

### `cogsci_rag.py` 新增内容清单

| 位置 | 新增内容 | 说明 |
|------|---------|------|
| 第382行下方 | `_collection_global = None` | 全局变量，供综述模式使用 |
| 第458行 | `_collection_global = col` | 在 `build_or_load_vectorstore` 中赋值 |
| `INTRO_SYSTEM_PROMPT` 后 | `CONCEPT_MAP_PROMPT` | 概念地图 system prompt |
| `CONCEPT_MAP_PROMPT` 后 | `SURVEY_PROMPT` | 综述 system prompt |
| `SURVEY_PROMPT` 后 | `HYPOTHESIS_PROMPT` | 假设生成 system prompt |
| `ask_openrouter` 函数后 | `ask_concept_map()` | 概念地图生成函数 |
| `ask_concept_map` 函数后 | `ask_survey()` | 综述生成函数（检索12篇） |
| `ask_survey` 函数后 | `ask_hypothesis()` | 假设生成函数 |

### `app.py` 改动点清单

| 行号区间 | 改动内容 | 说明 |
|---------|---------|------|
| 72行附近 | 侧边栏使用说明 | 增加地图/综述/假设三种模式说明 |
| 193行附近 | 模式判断扩展 | 新增 `is_concept_map`、`is_survey`、`is_hypothesis` |
| 194行附近 | topic 提取扩展 | 支持四种前缀模式 |
| 205行附近 | mode 分支扩展 | 新增 `concept_map`、`survey`、`hypothesis` 三个 mode |
| 212-218行之间 | 渲染逻辑扩展 | 为三种新模式添加对应的渲染逻辑 |
| 224行附近 | 来源面板展开逻辑 | 假设模式下默认展开 |

### 触发关键词映射

| 用户输入前缀 | mode 值 | 调用函数 | 检索量 |
|------------|---------|---------|-------|
| `入门` | `intro` | `ask_openrouter(mode="intro")` | TOP_K (6篇) |
| `地图` | `concept_map` | `ask_concept_map()` | TOP_K (6篇) |
| `综述` | `survey` | `ask_survey()` | 12篇 |
| `假设` | `hypothesis` | `ask_hypothesis()` | TOP_K (6篇) |
| 其他 | `qa` | `ask_openrouter(mode="qa")` | TOP_K (6篇) |

### 遵守的 CLAUDE.md 规则

✅ **最小化修改**
- 只新增代码，不修改现有函数签名
- 不改变 `retrieve`、`ask_openrouter`、`build_or_load_vectorstore` 的逻辑
- 不修改 `SYSTEM_PROMPT`、`INTRO_SYSTEM_PROMPT`

✅ **不触碰核心配置**
- 全局 `TOP_K` 保持 6（综述模式的 12 是函数内临时变量）
- 全局 `MIN_CITATIONS` 不变
- session state key 名不变

✅ **不触碰数据**
- 不修改 `papers/all_papers_fulltext.json`
- 不触发向量库重建

### 测试建议

完成代码编写后，建议按以下顺序测试：

1. **概念地图模式**  
   输入：`地图 预测编码`  
   预期：返回 JSON 结构化内容，包含核心定义、相关概念、争议、代表人物、入门推荐

2. **综述模式**  
   输入：`综述 工作记忆`  
   预期：返回四段式综述（背景/发现/争议/未解问题），引用12篇文献

3. **假设生成模式**  
   输入：`假设 双语者工作记忆优势`  
   预期：返回理论基础/可检验假设/混淆变量/实验范式，来源面板默认展开

4. **原有模式兼容性**  
   - 普通问答：`注意力和工作记忆的关系`  
   - 入门模式：`入门 心智哲学`  
   预期：功能正常，不受新代码影响

---

## 后续迭代方向（暂不实施）

- 概念地图可视化（使用 pyvis 或 cytoscape.js）
- 综述导出为 Markdown/PDF
- 假设生成支持多轮对话（细化实验设计）
- 方向三：用户认知建模（记录学习路径，动态调整解释策略）