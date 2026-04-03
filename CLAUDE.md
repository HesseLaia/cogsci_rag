# CLAUDE.md — Cursor 代码优化规则

## 核心原则：最小化修改

- **改动范围最小化**：只修改与任务直接相关的代码，不顺手重构
- **不改变接口**：函数签名、参数名、返回值结构保持不变，除非任务明确要求
- **不改变文件结构**：不移动函数位置、不拆分/合并文件
- **不改变变量命名**：哪怕现有命名不够好，保持一致性优先
- **禁止未经要求的格式化**：不自动调整缩进风格、引号风格、import排序

---

## 改动前必须确认

- 明确这次任务的**边界**：哪个函数/模块，做什么，不做什么
- 如果一个改动会影响超过3个函数，先说明影响范围，等确认再动
- 涉及 `cogsci_rag.py` 核心逻辑（retrieve、ask_openrouter、build_or_load_vectorstore）时，改动前说明理由

---

## 项目特定规则

### 数据文件（只读，不得修改）
- `papers/all_papers_fulltext.json` — 主知识库，禁止在代码里覆写
- `papers/all_papers_clean.json` — 原始清洗数据，禁止修改
- `chroma_db/` — 向量库目录，不得手动删除或修改内容

### 向量库重建触发条件
- 只有在 `PAPERS_PATH` 指向的数据文件发生实质变化时才删除 `chroma_db/` 重建
- 不得因为代码优化触发重建

### 配置区（`cogsci_rag.py` 顶部）
- `TOP_K`、`MIN_CITATIONS`、`EMBED_MODEL` 等参数不得在任务范围外调整
- API key 不得出现在任何日志输出或注释中

### Streamlit（`app.py`）
- `@st.cache_resource` 装饰器不得移除
- session state 的 key 名不得改变（会破坏用户会话）

---

## 输出规范

- 每次改动后说明：**改了什么、为什么、没改什么**
- 如果发现任务范围外的问题，**只报告，不自动修复**
- 不生成示例用法、测试代码，除非明确要求

---

## 禁止行为

- 禁止在没有要求的情况下添加 logging、try/except、类型注解
- 禁止将现有函数拆成更小的函数（除非任务要求）
- 禁止添加任何新依赖（pip install）而不说明理由
- 禁止修改 system prompt 内容（`SYSTEM_PROMPT`、`INTRO_SYSTEM_PROMPT`）
- 禁止在 `spider.py` 里修改 `BLOCKED_DOMAINS` 列表