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

## 方向三：用户认知建模（第二次迭代再讨论）
目前已有用户画像问卷了，这是个很好的起点。往深了做可以记录用户问过什么、卡在哪里、对哪类解释反应好，动态更新画像，让引擎越用越懂这个人。本质上是在做一个关于"人如何学习和理解"的数据飞轮。

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