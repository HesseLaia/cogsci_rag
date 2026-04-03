# CogSci RAG 优化路线图

## 📋 当前问题诊断

### 问题1：检索策略不合理 - 书籍与论文混排导致结果不稳定

**现象**：
- TOP_K=6 将书籍chunk和论文混在一起按向量相似度排序
- 有时6个结果全是书籍chunk，有时全是论文，完全看运气
- 无法保证"概念背景+具体证据"的知识组合

**根本原因**：
书籍和论文在知识库中承担的角色不同：
- **书籍chunk**：适合回答"X是什么"、"机制是什么"等概念性问题，提供系统性背景知识
- **论文**：适合回答"关于X有什么具体发现"、"哪个实验证明了什么"，提供具体证据和前沿进展

当前单一向量检索无法区分这两类知识的功能差异。

---

### 问题2：缺乏对话记忆 - 无法进行连续对话

**现象**：
- 同一对话框内的多轮问答互不连贯
- 用户问"详细展开一下"，系统不知道"一下"指的是什么
- 无法基于上文追问或深化讨论

**根本原因**：
- 当前每次问答都是独立的单次调用
- `st.session_state.messages` 只用于展示历史，没有传入LLM
- 缺乏记忆存储和上下文管理机制

---

## 🎯 解决方案设计

### 方案1：分层混合检索（Hybrid Retrieval）

#### 1.1 核心设计理念

**分层检索架构**：
```
用户问题
    ↓
Query分类器（判断问题类型）
    ↓
┌─────────────┬─────────────┐
│  书籍检索层  │  论文检索层  │
│  (概念背景)  │  (具体证据)  │
└─────────────┴─────────────┘
    ↓           ↓
固定配额合并（而非按分数混排）
    ↓
[书籍chunk × 2-3] + [论文 × 2-3]
    ↓
传入LLM生成
```

#### 1.2 数据层改造

**方案A：双Collection架构（推荐）**

```python
# 构建两个独立的向量库
collection_books  = client.get_or_create_collection("cogsci_books")
collection_papers = client.get_or_create_collection("cogsci_papers")

# metadata字段区分
books: {
    "source_type": "book",
    "book_title": "Principles of Neural Science",
    "chapter": "Learning and Memory",
    "page_range": "1227-1246",
    ...
}

papers: {
    "source_type": "paper",
    "title": "...",
    "citation_count": 342,
    "tier": "classic" / "recent",
    ...
}
```

**方案B：单Collection + metadata过滤**
```python
# 保持单一collection，通过where条件分别检索
results_books = collection.query(
    query_embeddings=q_emb,
    n_results=10,
    where={"source_type": "book"}
)

results_papers = collection.query(
    query_embeddings=q_emb,
    n_results=10,
    where={"source_type": "paper"}
)
```

**对比**：
- 方案A性能更好（索引分离），重建成本高
- 方案B改动最小，性能稍差，推荐作为第一阶段实现

#### 1.3 Query分类器设计

**轻量级规则分类器（Phase 1）**：

```python
import re

def classify_query_intent(query: str) -> dict:
    """
    返回：{
        "intent": "concept" / "evidence" / "mixed",
        "book_weight": 0.0-1.0,
        "paper_weight": 0.0-1.0
    }
    """
    # 1. 优先级规则：句尾模式直接决定意图
    if re.search(r'(是什么|定义|怎么理解|如何理解)[\?？]?$', query):
        return {"intent": "concept", "book_weight": 0.7, "paper_weight": 0.3}
    
    if re.search(r'(哪些实验|哪些研究|哪些论文|有什么证据)[\?？]?$', query):
        return {"intent": "evidence", "book_weight": 0.2, "paper_weight": 0.8}
    
    # 2. 加权计分：不同关键词权重不同
    concept_keywords = {
        "是什么": 3, "定义": 3, "机制": 2, 
        "原理": 2, "如何工作": 2, "入门": 3,
        "概念": 2, "理论": 2
    }
    
    evidence_keywords = {
        "实验": 2, "研究发现": 3, "研究": 1.5,
        "数据": 2, "哪些论文": 4, "证明": 2,
        "结果": 1.5, "发现": 2
    }
    
    frontier_keywords = {
        "最新": 3, "近年": 2, "2020": 2, 
        "2025": 2, "前沿": 3, "趋势": 2
    }
    
    # 3. 计算加权分数
    concept_score = sum(weight for kw, weight in concept_keywords.items() if kw in query)
    evidence_score = sum(weight for kw, weight in evidence_keywords.items() if kw in query)
    frontier_score = sum(weight for kw, weight in frontier_keywords.items() if kw in query)
    
    # 4. 位置加权：句首的关键词权重×1.5
    first_10_chars = query[:10]
    if any(kw in first_10_chars for kw in concept_keywords):
        concept_score *= 1.5
    if any(kw in first_10_chars for kw in evidence_keywords):
        evidence_score *= 1.5
    
    # 5. 前沿性强制调整为证据类（需要查最新论文）
    if frontier_score > 2:
        evidence_score += frontier_score
    
    # 6. 判定意图
    if concept_score > evidence_score * 1.5:  # 概念明显占优
        return {"intent": "concept", "book_weight": 0.7, "paper_weight": 0.3}
    elif evidence_score > concept_score * 1.5:  # 证据明显占优
        return {"intent": "evidence", "book_weight": 0.2, "paper_weight": 0.8}
    else:  # 混合型问题
        return {"intent": "mixed", "book_weight": 0.5, "paper_weight": 0.5}
```

**基于LLM的分类器（Phase 2，可选）**：

```python
def classify_query_intent_llm(query: str) -> dict:
    """用小模型（如gemini-flash）做意图分类"""
    prompt = f"""判断这个问题是：
A. 概念解释（适合查教材）
B. 证据查找（适合查论文）
C. 混合型

问题：{query}

只返回A/B/C："""
    
    # 调用fast模型（如OpenRouter的gemini-flash）
    result = call_fast_llm(prompt)
    
    mapping = {
        "A": {"intent": "concept", "book_weight": 0.7, "paper_weight": 0.3},
        "B": {"intent": "evidence", "book_weight": 0.2, "paper_weight": 0.8},
        "C": {"intent": "mixed", "book_weight": 0.5, "paper_weight": 0.5}
    }
    return mapping.get(result.strip(), mapping["C"])
```

#### 1.4 检索函数重构

```python
def hybrid_retrieve(query: str, collection) -> dict:
    """
    返回：{
        "books": [...],    # 书籍chunks
        "papers": [...],   # 论文列表
        "intent": "concept" / "evidence" / "mixed"
    }
    """
    embedder = get_embedder()
    q_emb = embedder.encode([query]).tolist()
    
    # 1. 问题分类
    intent_info = classify_query_intent(query)
    intent = intent_info["intent"]
    
    # 2. 动态分配检索数量
    if intent == "concept":
        n_books, n_papers = 3, 2
    elif intent == "evidence":
        n_books, n_papers = 2, 4
    else:  # mixed
        n_books, n_papers = 2, 3
    
    # 3. 分别检索
    # 书籍检索
    raw_books = collection.query(
        query_embeddings=q_emb,
        n_results=n_books * 2,  # 检索2倍候选
        where={"source_type": "book"}
    )
    books = _parse_book_results(raw_books)[:n_books]
    
    # 论文检索（保留原有的引用数过滤逻辑）
    raw_papers = collection.query(
        query_embeddings=q_emb,
        n_results=n_papers * 3,
        where={"source_type": "paper"}
    )
    papers = _filter_papers_by_citation(raw_papers, min_citations=10)[:n_papers]
    
    # 4. 【保底策略】如果某类检索结果不足，动态补充
    book_shortage = n_books - len(books)
    paper_shortage = n_papers - len(papers)
    
    if book_shortage > 0 and intent == "concept":
        # 概念类问题书籍不足，补充论文
        extra_papers = collection.query(
            query_embeddings=q_emb,
            n_results=(n_papers + book_shortage) * 3,
            where={"source_type": "paper"}
        )
        papers = _filter_papers_by_citation(extra_papers, min_citations=10)[:n_papers + book_shortage]
        print(f"[保底] 书籍不足，补充{book_shortage}篇论文")
    
    if paper_shortage > 0 and intent == "evidence":
        # 证据类问题论文不足，降低引用数阈值重试
        extra_papers = collection.query(
            query_embeddings=q_emb,
            n_results=n_papers * 3,
            where={"source_type": "paper"}
        )
        papers_low_threshold = _filter_papers_by_citation(extra_papers, min_citations=5)[:n_papers]
        if len(papers_low_threshold) > len(papers):
            papers = papers_low_threshold
            print(f"[保底] 论文不足，降低引用数阈值至5")
    
    # 5. 如果混合问题两边都不足，补充总量到最低限
    total_results = len(books) + len(papers)
    if total_results < 4:  # 至少保证4个结果
        print(f"[警告] 检索结果不足({total_results}个)，放宽条件重新检索")
        # 不区分类型，直接检索top相关的
        fallback = collection.query(
            query_embeddings=q_emb,
            n_results=6
        )
        # 合并结果并去重
        all_results = books + papers + _parse_mixed_results(fallback)
        books = [r for r in all_results if r.get("source_type") == "book"][:2]
        papers = [r for r in all_results if r.get("source_type") == "paper"][:3]
    
    return {
        "books": books,
        "papers": papers,
        "intent": intent
    }
```

#### 1.5 Context构造优化

```python
def build_context(retrieved: dict) -> str:
    """区分书籍和论文的展示方式"""
    context_parts = []
    
    # 概念背景部分
    if retrieved["books"]:
        context_parts.append("=== 教材知识 ===")
        for i, book in enumerate(retrieved["books"], 1):
            context_parts.append(
                f"[书{i}] {book['book_title']} - {book['chapter']}\n"
                f"内容：{book['content'][:800]}..."
            )
    
    # 研究证据部分
    if retrieved["papers"]:
        context_parts.append("\n=== 研究论文 ===")
        for i, paper in enumerate(retrieved["papers"], 1):
            context_parts.append(
                f"[文{i}] {paper['title']} ({paper['year']}, 引用:{paper['citations']})\n"
                f"摘要：{paper['abstract'][:500]}..."
            )
    
    return "\n\n".join(context_parts)
```

#### 1.6 System Prompt调整

在system prompt中增加引导：

```python
SYSTEM_PROMPT_HYBRID = """你是一位认知科学学者...

【知识库说明】
你会收到两类知识：
1. **教材知识**（标记为[书N]）：来自经典教材，适合用于解释概念、机制、理论框架
2. **研究论文**（标记为[文N]）：来自学术论文，适合用于引用具体实验、数据、前沿发现

引用时请区分：
- 概念解释时优先引用教材：如"根据Kandel的《神经科学原理》[书1]..."
- 具体证据时引用论文：如"Kahneman等人的实验发现[文1]..."

...
"""
```

---

### 方案2：对话记忆系统（Conversation Memory）

#### 2.1 架构设计

**多层记忆架构**：

```
┌─────────────────────────────────────┐
│   短期记忆（Session State）          │  ← 当前会话的最近3-5轮
│   - 最新的用户画像                   │
│   - 近期提问的主题                   │
│   - 待追问的悬念                    │
└─────────────────────────────────────┘
            ↓
┌─────────────────────────────────────┐
│   长期记忆（Memory.json）            │  ← 跨会话的知识积累
│   - 用户感兴趣的主题列表             │
│   - 重复出现的问题模式               │
│   - 明确表达的偏好                  │
└─────────────────────────────────────┘
```

#### 2.2 数据结构设计

**session_memory.json（短期记忆）**：
```json
{
  "session_id": "20260403_143022",
  "user_profile": "用户有心理学背景，刚刚入门...",
  "conversation_history": [
    {
      "turn": 1,
      "user": "预测编码是什么？",
      "assistant_summary": "解释了预测编码的核心机制",
      "retrieved_papers": ["paper_id_1", "paper_id_2"],
      "timestamp": "2026-04-03T14:30:45"
    },
    {
      "turn": 2,
      "user": "能详细展开一下误差信号吗？",
      "context_reference": "turn_1",  // 关联到第1轮
      "assistant_summary": "深入解释了预测误差的计算...",
      "timestamp": "2026-04-03T14:32:10"
    }
  ],
  "current_topics": ["预测编码", "误差信号", "贝叶斯大脑"],
  "pending_questions": [
    "那预测编码在情绪中是怎么工作的呢？"
  ]
}
```

**user_memory.json（长期记忆）**：
```json
{
  "user_id": "default",  // 多用户时可扩展
  "profile": {
    "background": "心理学",
    "level": "刚开始",
    "preferences": {
      "explanation_style": "先用类比",
      "math_tolerance": "避免公式"
    }
  },
  "interests": {
    "topics": {
      "预测编码": {"mentions": 8, "last_asked": "2026-04-03"},
      "意识": {"mentions": 5, "last_asked": "2026-03-28"},
      "注意力": {"mentions": 3, "last_asked": "2026-03-25"}
    }
  },
  "interaction_stats": {
    "total_sessions": 12,
    "total_questions": 87,
    "favorite_tracks": ["认知神经科学", "心智哲学"]
  }
}
```

#### 2.3 核心功能实现

**2.3.1 短期记忆管理**

```python
class SessionMemory:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history = []
        self.current_topics = []
        self.max_history = 10  # 最多保留10轮对话
        
    def add_turn(self, user_input: str, assistant_response: str, 
                 retrieved_docs: list):
        """添加一轮对话"""
        # 提取主题词（简单实现：TF-IDF或关键词提取）
        topics = self._extract_topics(user_input)
        self.current_topics.extend(topics)
        self.current_topics = list(set(self.current_topics))[-5:]  # 保留最近5个主题
        
        turn = {
            "turn": len(self.history) + 1,
            "user": user_input,
            "assistant_summary": self._summarize(assistant_response),
            "retrieved_docs": [d.get("title") for d in retrieved_docs],
            "topics": topics,
            "timestamp": datetime.now().isoformat()
        }
        
        self.history.append(turn)
        
        # 限制历史长度
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def get_recent_context(self, n: int = 3) -> str:
        """获取最近n轮对话的摘要"""
        if not self.history:
            return ""
        
        recent = self.history[-n:]
        context_parts = [
            f"第{t['turn']}轮 - 用户问：{t['user']}，你回答了：{t['assistant_summary']}"
            for t in recent
        ]
        return "\n".join(context_parts)
    
    def detect_follow_up(self, user_input: str) -> bool:
        """检测是否是追问（包含"这个"、"详细"等指代词）"""
        follow_up_signals = ["这个", "详细", "展开", "继续", "那么", "那", "它"]
        return any(sig in user_input for sig in follow_up_signals)
    
    def _extract_topics(self, text: str) -> list:
        """简单的主题提取（可用jieba分词+TF-IDF优化）"""
        # 临时实现：提取认知科学常见术语
        cogsci_terms = ["预测编码", "注意力", "工作记忆", "意识", "镜像神经元", 
                        "贝叶斯", "自由能", "神经网络", "强化学习"]
        return [term for term in cogsci_terms if term in text]
    
    def _summarize(self, response: str) -> str:
        """生成摘要：优先用关键句提取，避免截断丢失信息"""
        if len(response) < 150:
            return response
        
        # 简单但有效的方法：提取第一段和最后一句
        lines = response.strip().split('\n')
        non_empty = [l for l in lines if l.strip()]
        
        if len(non_empty) <= 2:
            return response[:100] + "..."
        
        # 提取"结论"部分（如果有）
        for i, line in enumerate(non_empty):
            if "**结论**" in line or "**展开**" in line:
                if i + 1 < len(non_empty):
                    return non_empty[i + 1][:150]
        
        # 否则返回首句
        return non_empty[0][:150] + "..."
```

**2.3.2 长期记忆管理**

```python
class UserMemory:
    def __init__(self, memory_file: str = "user_memory.json"):
        self.memory_file = memory_file
        self.data = self._load()
    
    def _load(self) -> dict:
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "profile": {},
            "interests": {"topics": {}},
            "interaction_stats": {"total_sessions": 0, "total_questions": 0}
        }
    
    def save(self):
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def update_interests(self, topics: list):
        """更新兴趣主题统计"""
        for topic in topics:
            if topic not in self.data["interests"]["topics"]:
                self.data["interests"]["topics"][topic] = {
                    "mentions": 0,
                    "last_asked": None
                }
            self.data["interests"]["topics"][topic]["mentions"] += 1
            self.data["interests"]["topics"][topic]["last_asked"] = \
                datetime.now().strftime("%Y-%m-%d")
        self.save()
    
    def get_top_interests(self, n: int = 5) -> list:
        """获取最感兴趣的前n个主题"""
        topics = self.data["interests"]["topics"]
        sorted_topics = sorted(topics.items(), 
                              key=lambda x: x[1]["mentions"], 
                              reverse=True)
        return [t[0] for t in sorted_topics[:n]]
```

#### 2.4 集成到RAG流程

**修改后的ask_openrouter函数**：

```python
def ask_openrouter_with_memory(
    question: str, 
    docs: list, 
    session_memory: SessionMemory,
    user_memory: UserMemory,
    mode: str = "qa"
) -> str:
    """带记忆的生成"""
    
    # 1. 检测是否为追问
    is_follow_up = session_memory.detect_follow_up(question)
    
    # 2. 构造上下文
    context = build_context(docs)
    
    # 3. 如果是追问，添加短期记忆
    memory_context = ""
    if is_follow_up:
        memory_context = f"\n\n=== 对话历史 ===\n{session_memory.get_recent_context(3)}\n"
    
    # 4. 构造messages
    sys_prompt = SYSTEM_PROMPT.replace("{user_profile}", user_memory.data["profile"])
    
    if is_follow_up:
        sys_prompt += "\n\n【重要】用户的问题是对之前对话的追问，请基于对话历史理解指代内容。"
    
    user_msg = f"{memory_context}=== 知识库 ===\n{context}\n\n问题：{question}"
    
    # 5. 调用LLM
    response = call_openrouter(sys_prompt, user_msg)
    
    # 6. 保存到记忆
    session_memory.add_turn(question, response, docs)
    user_memory.update_interests(session_memory.current_topics)
    
    return response
```

**Streamlit集成**：

```python
# app.py 修改

# 初始化记忆系统
if "session_memory" not in st.session_state:
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.session_memory = SessionMemory(session_id)

if "user_memory" not in st.session_state:
    st.session_state.user_memory = UserMemory()

# 在生成回答时传入记忆
answer = ask_openrouter_with_memory(
    question=topic,
    docs=docs,
    session_memory=st.session_state.session_memory,
    user_memory=st.session_state.user_memory,
    mode=mode
)
```

#### 2.5 记忆展示功能

**侧边栏增加记忆面板**：

```python
# app.py 侧边栏增加
with st.sidebar:
    st.divider()
    st.markdown("### 💭 对话记忆")
    
    # 当前话题
    if st.session_state.session_memory.current_topics:
        st.markdown("**当前话题**")
        for topic in st.session_state.session_memory.current_topics:
            st.caption(f"• {topic}")
    
    # 长期兴趣
    st.markdown("**你最常问的**")
    top_interests = st.session_state.user_memory.get_top_interests(3)
    for interest in top_interests:
        mentions = st.session_state.user_memory.data["interests"]["topics"][interest]["mentions"]
        st.caption(f"• {interest} ({mentions}次)")
    
    # 清除记忆按钮
    if st.button("🗑️ 清除本次对话记忆"):
        st.session_state.session_memory = SessionMemory(...)
        st.rerun()
```

---

## 🚀 实施计划

### Phase 1：混合检索（优先级：高）

**工作量**：2-3天

**步骤**：
1. ✅ 给现有数据添加`source_type`字段（书籍/论文）
2. ✅ 实现规则型Query分类器
3. ✅ 重构`retrieve()`函数为`hybrid_retrieve()`
4. ✅ 修改context构造逻辑
5. ✅ 更新system prompt
6. ✅ 测试并对比改进前后的检索质量

**验收标准**：
- 概念性问题（如"预测编码是什么"）能稳定返回2-3个书籍chunk
- 证据性问题（如"有哪些实验证明了预测编码"）能稳定返回3-4篇论文
- 混合问题能合理分配资源

---

### Phase 2：对话记忆（优先级：高）

**工作量**：3-4天

**步骤**：
1. ✅ 实现`SessionMemory`类（短期记忆）
2. ✅ 实现`UserMemory`类（长期记忆）
3. ✅ 集成到RAG生成流程
4. ✅ 实现追问检测逻辑
5. ✅ 在Streamlit界面展示记忆状态
6. ✅ 测试多轮对话连贯性

**验收标准**：
- 用户问"详细展开一下"时，系统能正确理解上文
- 跨会话能记住用户的兴趣偏好
- 侧边栏能显示当前话题和历史兴趣

---

### Phase 3：实时检索集成（优先级：中）

**前置条件**：Phase 1完成

**功能描述**：
- 对于"前沿"类问题（包含"最新"、"2024"、"近年"等关键词），触发实时检索
- 调用Semantic Scholar API或arXiv API实时获取最新论文
- 根据query分类器的结果，动态分配本地知识库和实时检索的比重

**实现思路**：
```python
def enhanced_retrieve(query: str) -> dict:
    intent = classify_query_intent(query)
    
    # 检测是否需要实时检索
    if intent["requires_realtime"]:
        # 实时检索占60%，本地知识库占40%
        realtime_papers = search_semantic_scholar(query, n=3)
        local_results = hybrid_retrieve(query, n_papers=2, n_books=1)
        return merge_results(realtime_papers, local_results)
    else:
        # 完全使用本地知识库
        return hybrid_retrieve(query)
```

---

### Phase 4：高级Query分类器（优先级：低）

**前置条件**：Phase 1验证规则分类器效果后

**可选方案**：
- 使用小型LLM（gemini-flash/gpt-4o-mini）做意图分类
- 训练一个轻量级分类器（基于embedding + logistic regression）
- 用分类结果优化检索配额分配

**ROI评估**：
- 规则分类器如果已经足够好，可以不做这一步
- 如果发现误分类影响体验，再考虑升级

---

## 📊 效果评估指标

### 自动化指标（开发阶段持续监控）

#### 检索稳定性
- **书籍/论文分布一致性**：同一问题连续3次检索，书籍/论文比例波动<10%
- **响应时间**：P95延迟<2秒（检索<300ms，生成<1.8s）

#### 记忆系统
- **追问关键词召回**：追问中90%能从历史中找到上文提及的关键词
- **session_memory文件大小**：<500KB（10轮对话）

### 人工评估（Phase验收时执行）

#### 抽样方案
- **样本来源**：每个Phase完成后，收集20个真实用户问题（或构造典型问题）
- **评分维度**（1-5分制）：
  - 相关性：检索结果是否切题
  - 连贯性：多轮对话是否流畅
  - 有用性：回答是否解决了问题
- **目标**：平均分>4.0

#### Phase 1 验收标准
- 概念性问题（如"预测编码是什么"）能稳定返回2-3个书籍chunk
- 证据性问题（如"有哪些实验证明了预测编码"）能稳定返回3-4篇论文
- 混合问题能合理分配资源
- **测试用例**：准备10个concept + 10个evidence + 5个mixed问题

#### Phase 2 验收标准
- 用户问"详细展开一下"时，系统能正确理解上文（10个追问测试，成功率>8/10）
- 跨会话能记住用户的兴趣偏好
- 侧边栏能显示当前话题和历史兴趣

---

## 🔧 技术债务与注意事项

### 向量库重建
- 添加`source_type`字段需要重建整个向量库
- 建议保留原有数据作为备份：`chroma_db_backup/`
- 重建时间约3-5分钟（取决于数据量）

### 内存管理
- `SessionMemory`保留最近10轮对话，避免内存溢出
- `user_memory.json`文件大小需监控，超过10MB时考虑归档

### 兼容性
- 新的检索接口需保证向后兼容
- 现有的`retrieve()`函数可保留，添加新的`hybrid_retrieve()`

---

## ⚠️ 风险评估与缓解方案

### 风险1：向量库重建失败

**概率**：中  
**影响**：高（系统完全不可用）  

**缓解措施**：
- 重建前自动备份到 `chroma_db_backup_YYYYMMDD/`
- 增量测试：先用10条数据测试重建流程
- 提供一键回滚脚本：
  ```bash
  # rollback_vectorstore.ps1
  Remove-Item -Recurse -Force chroma_db
  Copy-Item -Recurse chroma_db_backup chroma_db
  ```

### 风险2：Query分类器误判率过高

**概率**：中  
**影响**：中（检索结果不理想，但不影响系统运行）

**缓解措施**：
- 开发阶段记录分类日志：`{"query": "...", "intent": "...", "confidence": 0.8}`
- 每50个query人工抽查10个，误判率>20%则调整规则
- 保留fallback机制：分类不确定时使用mixed模式

### 风险3：记忆系统内存/存储泄漏

**概率**：低  
**影响**：中（长时间运行后变慢或磁盘占满）

**缓解措施**：
- SessionMemory强制限制：最多10轮，超过则自动丢弃最早的
- user_memory.json定期清理：30天未活跃的topic归档
- 监控文件大小：每次save时检查，>10MB则触发警告

### 风险4：Phase 1/2 改动破坏现有功能

**概率**：低  
**影响**：高（用户无法正常使用）

**缓解措施**：
- 每个Phase开始前打tag：`git tag before-phase-1`
- 保留原有函数：`retrieve()`改名为`retrieve_legacy()`，不删除
- 回归测试清单：
  ```
  ✓ 基础问答能否正常返回结果
  ✓ 向量库加载是否成功
  ✓ LLM调用是否正常
  ✓ Streamlit界面是否正常渲染
  ```

---

## 🔄 回滚策略

### Phase 1 回滚清单

**触发条件**：
- 重建向量库后检索结果明显变差
- 分类器误判率>30%
- 系统崩溃或无法启动

**回滚步骤**：
1. 代码回滚：`git reset --hard before-phase-1`
2. 数据回滚：`Copy-Item -Recurse chroma_db_backup chroma_db -Force`
3. 验证：运行5个测试问题，确认恢复正常
4. 记录问题：在issue中说明回滚原因和复现步骤

### Phase 2 回滚清单

**触发条件**：
- 对话记忆功能导致回答错误
- session_memory文件增长过快（>1MB）
- 追问功能理解错误率>50%

**回滚步骤**：
1. 代码回滚：`git reset --hard before-phase-2`
2. 清理记忆文件：`Remove-Item user_memory.json, session_*.json`
3. 重启Streamlit：`streamlit run app.py`

---

## 📚 参考资料

### 混合检索相关
- [Hybrid Search in Vector Databases](https://www.pinecone.io/learn/hybrid-search-intro/)
- [RAG Fusion: Better than Traditional RAG](https://arxiv.org/abs/2402.03367)

### 对话记忆相关
- [LangChain Memory Modules](https://python.langchain.com/docs/modules/memory/)
- [ConversationBufferMemory vs ConversationSummaryMemory](https://medium.com/@myscale/advanced-rag-06-exploring-contextual-compression-and-filtering-b0b0516f7cd0)

### 认知科学RAG实践
- [Building a Scientific QA System](https://arxiv.org/abs/2305.14456)
- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)

---

## 💡 未来展望

### 多模态支持
- 论文中的图表检索和理解
- 对论文中的公式、图表进行OCR并索引

### 个性化推荐
- 基于长期记忆，主动推荐相关论文
- "你可能感兴趣的主题"功能

### 协作式学习
- 多用户知识图谱构建
- 问题-回答对的复用与优化

---

**文档版本**：v1.0  
**最后更新**：2026-04-03  
**维护者**：CogSci RAG Team
