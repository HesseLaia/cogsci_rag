# 项目重构计划

## 📊 当前问题分析

### 1. 文件过多且分散（根目录17个Python文件）

**核心应用文件**：
- `app.py` - Streamlit Web界面
- `cogsci_rag.py` - RAG核心逻辑

**数据爬取文件（8个，功能重复/临时）**：
- `paper_crawler.py` - 论文爬虫统一入口 ✅ **保留**
- `cogsci_crawler.py` - 论文元数据爬虫 ✅ **保留**
- `spider.py` - 全文PDF爬虫 ✅ **保留**
- `enrich_papers.py` - 核心论文补充 ✅ **保留**
- `book_crawler.py` - 书籍爬虫 ✅ **保留**
- `book_processor.py` - 书籍处理器（旧版） ❌ **已被增强版替代**
- `book_processor_enhanced.py` - 书籍处理器增强版 ✅ **保留，重命名**
- `merge_books.py` - 合并书籍到主数据集 ✅ **保留**

**临时测试/实验文件（6个，可删除）**：
- `process_missing_books.py` - 处理缺失的2本书 ❌ **临时脚本，已完成任务**
- `process_big_books.py` - 处理大文件书籍 ❌ **临时脚本，已完成任务**
- `process_books_simple.py` - 简化版测试 ❌ **临时脚本，已完成任务**
- `test_one_book.py` - 单本书测试 ❌ **临时脚本，已完成任务**
- `fix_book_targets.py` - 修复配置文件 ❌ **一次性脚本，已完成任务**
- `book_targets_backup.py` - 配置文件备份 ❌ **备份文件**

**配置文件**：
- `book_targets.py` - 书籍清单配置 ✅ **保留，移动到config/**

### 2. 数据文件冗余（papers/目录多个备份和临时文件）

**核心数据文件**：
- `all_papers_fulltext.json` - 主数据集 ✅
- `books_processed.json` - 书籍处理结果 ✅

**备份文件（可清理）**：
- `all_papers_fulltext.backup.json` ❌
- `all_papers_fulltext.backup2.json` ❌
- `books_all_merged.json` ❌ 已合并到主数据集

**中间产物（可清理）**：
- `all_papers.json` ❌ 清洗前的原始数据
- `all_papers_clean.json` ❌ 中间产物
- `books_big.json` ❌ 临时处理结果
- `books_test.json` ❌ 测试数据

**Track分类文件（可选保留）**：
- `psychological_science.json` ⚠️ 如果不再单独使用，可删
- `cognitive_neuroscience.json`
- `cognitive_modeling_AI.json`
- `linguistics.json`
- `social_sciences.json`
- `philosophy.json`

### 3. 目录结构不清晰

当前结构：
```
cogsci_llm/
├── 17个py文件（混在一起）
├── 3个md文件
├── papers/
│   ├── 14个json文件（核心+备份+临时混杂）
│   ├── books_cache/
│   ├── pdfs/
│   └── pdfs_cache/
├── chroma_db/
└── .venv/
```

---

## 🎯 重构目标

### 目标1：清晰的模块化结构
```
cogsci_llm/
├── src/                        # 核心代码
│   ├── rag/                    # RAG引擎
│   │   ├── __init__.py
│   │   ├── retriever.py        # 检索逻辑
│   │   ├── generator.py        # 生成逻辑
│   │   └── memory.py           # 对话记忆（未来）
│   ├── crawlers/               # 数据爬取
│   │   ├── __init__.py
│   │   ├── paper_crawler.py
│   │   ├── book_crawler.py
│   │   └── fulltext_spider.py
│   ├── processors/             # 数据处理
│   │   ├── __init__.py
│   │   ├── book_processor.py
│   │   └── data_merger.py
│   └── config/                 # 配置文件
│       ├── __init__.py
│       ├── settings.py
│       └── book_targets.py
├── app.py                      # Web入口（保留在根目录）
├── cli.py                      # 命令行入口（重命名自cogsci_rag.py）
├── data/                       # 数据目录（重命名自papers/）
│   ├── processed/              # 处理后的数据
│   │   └── all_papers_fulltext.json
│   ├── cache/                  # 缓存
│   │   ├── books/
│   │   └── pdfs/
│   └── archives/               # 归档（备份、中间产物）
├── chroma_db/                  # 向量库
├── docs/                       # 文档
│   ├── README.md
│   ├── ROADMAP.md
│   └── REFACTOR_PLAN.md
├── scripts/                    # 工具脚本（一次性任务）
│   └── archived/               # 已完成的临时脚本
└── tests/                      # 测试（可选）
```

### 目标2：统一的入口点
- **用户使用**：`streamlit run app.py` 或 `python cli.py`
- **数据爬取**：`python -m src.crawlers.paper_crawler --mode all`
- **数据处理**：`python -m src.processors.book_processor`

### 目标3：清理冗余文件
- 删除6个临时测试脚本
- 归档3个备份文件和4个中间产物
- 保留track分类文件到archives（可能未来有用）

---

## 📋 具体操作步骤

### Phase 1：创建新目录结构（不影响现有功能）

```bash
# 创建新目录
mkdir src src/rag src/crawlers src/processors src/config
mkdir data data/processed data/cache data/archives
mkdir docs scripts scripts/archived

# 创建__init__.py
touch src/__init__.py
touch src/rag/__init__.py
touch src/crawlers/__init__.py
touch src/processors/__init__.py
touch src/config/__init__.py
```

### Phase 2：移动核心代码

#### 2.1 RAG模块
```bash
# 拆分 cogsci_rag.py 到 src/rag/
# - retriever.py: retrieve(), build_or_load_vectorstore()
# - generator.py: ask_openrouter(), system prompts
# - __init__.py: 导出主要接口

# 创建新的命令行入口
cp cogsci_rag.py cli.py
# cli.py 改为导入 src.rag 模块
```

#### 2.2 爬虫模块
```bash
mv cogsci_crawler.py src/crawlers/paper_metadata_crawler.py
mv spider.py src/crawlers/fulltext_spider.py
mv enrich_papers.py src/crawlers/paper_enricher.py
mv book_crawler.py src/crawlers/book_crawler.py
mv paper_crawler.py src/crawlers/unified_crawler.py
```

#### 2.3 处理器模块
```bash
mv book_processor_enhanced.py src/processors/book_processor.py
mv merge_books.py src/processors/data_merger.py
```

#### 2.4 配置模块
```bash
mv book_targets.py src/config/book_targets.py
# 新建 src/config/settings.py 统一管理配置
```

### Phase 3：移动数据文件

#### 3.1 保留核心数据
```bash
# 保留在 data/processed/
mv papers/all_papers_fulltext.json data/processed/
mv papers/books_processed.json data/processed/

# 保留缓存
mv papers/books_cache data/cache/books
mv papers/pdfs_cache data/cache/pdfs
mv papers/pdfs data/cache/pdfs_fulltext
```

#### 3.2 归档备份和中间产物
```bash
# 归档到 data/archives/
mv papers/*.backup*.json data/archives/
mv papers/all_papers.json data/archives/
mv papers/all_papers_clean.json data/archives/
mv papers/books_*.json data/archives/
mv papers/*_science.json data/archives/tracks/
mv papers/philosophy.json data/archives/tracks/
mv papers/linguistics.json data/archives/tracks/
```

### Phase 4：归档临时脚本

```bash
mv process_missing_books.py scripts/archived/
mv process_big_books.py scripts/archived/
mv process_books_simple.py scripts/archived/
mv test_one_book.py scripts/archived/
mv fix_book_targets.py scripts/archived/
mv book_targets_backup.py scripts/archived/
rm book_processor.py  # 已被增强版替代，直接删除
```

### Phase 5：移动文档

```bash
mv README.md docs/
mv ROADMAP.md docs/
mv REFACTOR_PLAN.md docs/
mv manual_books_guide.md docs/

# 在根目录创建简化版README
# 指向 docs/README.md
```

### Phase 6：更新导入路径

需要更新所有导入路径：

**app.py**：
```python
# 原来：
from cogsci_rag import load_papers, retrieve, ask_openrouter

# 改为：
from src.rag import load_papers, retrieve, ask_openrouter
from src.config import TRACK_NAMES, SYSTEM_PROMPT
```

**cli.py**：
```python
# 重构为使用 src.rag 模块的薄封装
from src.rag import RAGSystem

def main():
    rag = RAGSystem()
    rag.run_interactive()
```

**爬虫模块**：
```python
# src/crawlers/unified_crawler.py
from src.crawlers.paper_metadata_crawler import crawl_metadata
from src.crawlers.fulltext_spider import crawl_fulltext
from src.crawlers.paper_enricher import enrich_papers
```

### Phase 7：更新配置路径

**src/config/settings.py**（新建）：
```python
"""统一配置管理"""
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 数据路径
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
ARCHIVES_DIR = DATA_DIR / "archives"

# 主数据文件
PAPERS_JSON = PROCESSED_DIR / "all_papers_fulltext.json"
BOOKS_JSON = PROCESSED_DIR / "books_processed.json"

# 缓存路径
BOOKS_CACHE_DIR = CACHE_DIR / "books"
PDFS_CACHE_DIR = CACHE_DIR / "pdfs"

# 向量库路径
CHROMA_DIR = PROJECT_ROOT / "chroma_db"

# API配置（通过环境变量提供，示例见 env.example）
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# 检索配置
TOP_K = 6
MIN_CITATIONS = 10
EMBED_MODEL = "all-MiniLM-L6-v2"
```

所有模块改为：
```python
from src.config.settings import PAPERS_JSON, CHROMA_DIR, OPENROUTER_API_KEY
```

### Phase 8：根目录简化版README

**根目录新建 README.md**（指向详细文档）：
```markdown
# CogSci RAG - 认知科学知识库问答系统

基于RAG的认知科学论文+教材知识库，支持智能问答、入门导览、用户画像定制。

## 🚀 快速开始

### 安装依赖
\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 启动应用
\`\`\`bash
# Web界面
streamlit run app.py

# 命令行
python cli.py
\`\`\`

## 📚 完整文档

详细文档请查看：
- **使用指南**：[docs/README.md](docs/README.md)
- **优化路线图**：[docs/ROADMAP.md](docs/ROADMAP.md)
- **项目重构**：[docs/REFACTOR_PLAN.md](docs/REFACTOR_PLAN.md)

## 📁 项目结构

\`\`\`
cogsci_llm/
├── src/              # 核心代码
│   ├── rag/          # RAG引擎
│   ├── crawlers/     # 数据爬取
│   ├── processors/   # 数据处理
│   └── config/       # 配置
├── data/             # 数据文件
├── docs/             # 文档
├── app.py            # Web入口
└── cli.py            # 命令行入口
\`\`\`

## 📊 知识库规模

- **论文**：213篇（高引用经典+近5年新论文）
- **全文**：30篇完整论文
- **书籍**：14本核心教材

## 🙏 致谢

Semantic Scholar · arXiv · OpenRouter
```

---

## 🔧 重构后的优势

### 1. 清晰的代码组织
- **模块化**：按功能分离（RAG、爬虫、处理器）
- **单一职责**：每个模块职责明确
- **易扩展**：添加新功能只需在对应模块新增文件

### 2. 简洁的根目录
```
# 重构前：17个py文件 + 3个md
# 重构后：2个入口文件 + 1个简短README
```

### 3. 统一的配置管理
- 所有配置集中在 `src/config/settings.py`
- API key、路径、参数都统一管理
- 避免重复定义

### 4. 清晰的数据管理
```
data/
├── processed/     # 生产数据（定期备份）
├── cache/         # 可随时重建
└── archives/      # 历史备份（不参与运行）
```

### 5. 可测试性提升
- 代码模块化后便于单元测试
- 可以在 `tests/` 目录添加测试用例

---

## ⚠️ 注意事项

### 迁移风险
1. **导入路径变化**：所有 `from cogsci_rag import xxx` 需改为 `from src.rag import xxx`
2. **相对路径失效**：硬编码的相对路径（如 `"papers/xx.json"` ）需改为使用 `settings.py` 中的常量
3. **向量库重建**：如果移动了数据文件路径，可能需要重建 `chroma_db`

### 兼容性保留
- 重构期间保留原文件，验证新结构无误后再删除
- 在 `scripts/archived/` 保留所有临时脚本，万一需要可以回溯

### 回滚方案
- Git创建新分支 `refactor`
- 保留完整的原项目备份
- 分阶段重构，每阶段验证功能正常

---

## 📅 实施时间表

### 第1天：准备工作（1小时）
- [ ] Git创建 `refactor` 分支
- [ ] 创建新目录结构
- [ ] 备份现有项目

### 第2天：代码重构（3-4小时）
- [ ] 拆分 `cogsci_rag.py` 到 `src/rag/`
- [ ] 移动爬虫文件到 `src/crawlers/`
- [ ] 移动处理器到 `src/processors/`
- [ ] 创建统一配置 `src/config/settings.py`

### 第3天：路径更新（2-3小时）
- [ ] 更新 `app.py` 导入路径
- [ ] 更新 `cli.py` 导入路径
- [ ] 更新所有爬虫和处理器的导入

### 第4天：数据整理（1小时）
- [ ] 移动核心数据到 `data/processed/`
- [ ] 归档备份文件到 `data/archives/`
- [ ] 归档临时脚本到 `scripts/archived/`

### 第5天：测试验证（2小时）
- [ ] 测试 Web 界面启动
- [ ] 测试命令行启动
- [ ] 测试检索功能
- [ ] 测试生成功能

### 第6天：文档更新（1小时）
- [ ] 移动文档到 `docs/`
- [ ] 创建根目录简化版 README
- [ ] 更新所有文档中的路径引用

---

## 🎯 验收标准

### 功能验收
- [ ] `streamlit run app.py` 启动正常
- [ ] `python cli.py` 启动正常
- [ ] 检索返回结果与重构前一致
- [ ] 生成回答质量无退化
- [ ] 所有爬虫脚本能正常运行

### 代码质量
- [ ] 无硬编码路径
- [ ] 导入路径统一使用 `src.xxx`
- [ ] 配置集中在 `src/config/`
- [ ] 每个模块有清晰的职责

### 文档完整性
- [ ] README清晰指向详细文档
- [ ] 所有路径在文档中已更新
- [ ] 重构计划文档已完成

---

## 💡 未来扩展

重构后，以下功能更容易实现：

1. **混合检索**：在 `src/rag/retriever.py` 添加 `hybrid_retrieve()`
2. **对话记忆**：在 `src/rag/memory.py` 实现记忆系统
3. **实时检索**：在 `src/crawlers/` 添加 `realtime_searcher.py`
4. **单元测试**：在 `tests/` 添加各模块测试用例
5. **多用户支持**：在 `src/config/` 添加用户管理
6. **插件系统**：在 `src/plugins/` 添加扩展机制

---

**文档版本**：v1.0  
**创建日期**：2026-04-03  
**维护者**：CogSci RAG Team
