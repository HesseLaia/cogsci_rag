# CogSci RAG - 认知科学论文问答系统

基于 RAG（检索增强生成）的认知科学知识库问答系统，支持智能问答、入门导览、用户画像定制。

## 🎯 核心特性

- **智能问答**：基于213篇论文+30篇全文的语义检索
- **入门导览**：输入"入门 XX"获得方向介绍
- **用户画像**：根据背景、经验自动调整回答风格
- **六大Track**：心理科学、认知神经、建模AI、语言学、社会科学、心智哲学
- **对话风格**：苏格拉底式追问 + 学术翻译官 + 学者朋友

## 📊 知识库规模

- **论文**：213篇（高引用经典 + 近5年新论文）
- **全文**：30篇综述论文完整全文
- **书籍**：18本核心教材章节（待爬取）
- **数据源**：Semantic Scholar + arXiv + Unpaywall

## 🚀 快速开始

### 安装依赖

```bash
pip install streamlit chromadb sentence-transformers requests pdfplumber
```

### 启动应用

```bash
streamlit run app.py
```

### 命令行版本

```bash
python cogsci_rag.py
```

## 📁 项目结构

```
cogsci_llm/
├── app.py                      # Streamlit Web界面
├── cogsci_rag.py               # RAG核心逻辑（检索+生成）
├── env.example / .env          # 环境变量配置
│
├── modules/                    # 模块化代码
│   ├── config/
│   │   └── book_targets.py     # 书籍清单配置
│   ├── crawlers/               # 数据爬取
│   │   ├── paper_crawler.py    # 论文爬虫统一入口
│   │   ├── cogsci_crawler.py   # 论文元数据爬虫
│   │   ├── spider.py           # 全文PDF爬虫
│   │   ├── book_crawler.py     # 书籍爬虫
│   │   └── enrich_papers.py    # 核心论文补充
│   └── processors/             # 数据处理
│       ├── book_processor_enhanced.py  # 书籍章节处理
│       └── merge_books.py      # 数据合并
│
├── data/                       # 数据目录
│   ├── all_papers_fulltext.json        # 主数据集
│   ├── books_processed.json            # 书籍数据
│   ├── books_cache/                    # 书籍PDF缓存
│   ├── pdfs_cache/                     # 论文PDF缓存
│   └── archives/                       # 归档(备份/中间文件)
│       ├── backups/
│       ├── intermediate/
│       └── tracks/
│
├── chroma_db/                  # 向量数据库
└── docs/                       # 文档
    ├── ROADMAP.md              # 优化路线图
    ├── REFACTOR_PLAN.md        # 重构计划
    └── manual_books_guide.md   # 书籍手册
```

## 🔧 数据处理流程

### 论文数据

```bash
# 方式1：统一入口（推荐）
python -m modules.crawlers.paper_crawler --mode all

# 方式2：分步执行
python -m modules.crawlers.paper_crawler --mode metadata    # 1. 爬取元数据
python -m modules.crawlers.paper_crawler --mode fulltext    # 2. 获取全文PDF
python -m modules.crawlers.paper_crawler --mode enrich      # 3. 补充核心论文
```

### 书籍数据

```bash
# 第1步：爬取书籍PDF
python -m modules.crawlers.book_crawler

# 第2步：处理PDF并提取章节
python -m modules.processors.book_processor_enhanced

# 第3步：合并到主数据集
python -m modules.processors.merge_books

# 第4步：重建向量库
# 删除 chroma_db 目录，重启 app.py 会自动重建
```

## 📚 书籍清单

已收录18本认知科学核心教材：

### 心智哲学
- The Conscious Mind (Chalmers)
- Philosophy of Mind (Kim)
- Consciousness Explained (Dennett)

### 认知神经科学
- Principles of Neural Science (Kandel)
- Cognitive Neuroscience (Gazzaniga)
- The Cognitive Neurosciences

### 认知建模与AI
- The Computational Brain (Churchland & Sejnowski)
- AI: A Modern Approach (Russell & Norvig)
- How to Build a Brain (Eliasmith)

### 语言学
- The Language Instinct (Pinker)
- Foundations of Language (Jackendoff)
- Psycholinguistics (Aitchison)

### 心理科学
- Thinking, Fast and Slow (Kahneman)
- Cognitive Psychology (Eysenck)
- Memory: From Mind to Molecules (Squire & Kandel)

### 社会科学
- Social Cognition (Fiske & Taylor)
- Cultural Origins of Human Cognition (Tomasello)
- Mindreading (Goldman)

## ⚙️ 配置

### OpenRouter API

使用环境变量配置（推荐，不要把 key 写进代码）：

- Windows PowerShell 临时设置：

```powershell
$env:OPENROUTER_API_KEY="your-openrouter-api-key"
$env:OPENROUTER_MODEL="deepseek/deepseek-chat"
```

- 或者复制 `env.example` 为 `.env`，填入你自己的 key：

```bash
cp env.example .env  # Windows 可手动复制重命名
```

> 注意：项目不会自动加载 `.env`，你可以用 IDE / 终端插件加载，或在 shell 里自行导出环境变量。

### Semantic Scholar API（可选）

同样使用环境变量配置：

```powershell
$env:SS_API_KEY="your-semanticscholar-api-key"
```


### 代理设置（如需要）

在相关爬虫文件中添加：

```python
proxies = {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890",
}
```

## 🎨 对话风格

系统采用三位一体的对话设计：

1. **苏格拉底式追问**：每次回答末尾留挑战性问题
2. **学术翻译官**：术语首次出现给英文，清晰引用论文
3. **学者朋友**：平等、幽默、用括号动作描写增强对话感

**输出结构**：
```
**结论**
一句话核心答案（≤40字）

**展开**
3-5段深度解释，每段包含：观点+机制+例子

**和你聊聊**
一个苏格拉底式追问
```

## 📈 数据统计

运行 `cogsci_rag.py` 后输入 `统计` 查看知识库分布：

```
  心理科学           102篇  ███████████
  认知神经科学        98篇  ██████████
  认知建模与AI        87篇  █████████
  语言学             76篇  ████████
  社会科学与人文      54篇  ██████
  心智哲学           43篇  ████

  总计：213 篇
```

## 🚧 优化路线图

系统当前存在两个核心改进方向：

1. **混合检索优化**：书籍chunk和论文混排导致检索不稳定
2. **对话记忆系统**：缺乏多轮对话的上下文记忆

详细的问题分析、解决方案和实施计划请查看：**[ROADMAP.md](./docs/ROADMAP.md)**

## 🐛 故障排除

### 向量库损坏
```bash
# Windows PowerShell
Remove-Item -Recurse -Force chroma_db
streamlit run app.py  # 自动重建
```

### 编码错误
确保所有文件使用UTF-8编码：
```python
open(file, encoding='utf-8')
```

### PDF下载失败
- 检查网络连接
- 配置代理
- 查看 `data/books_cache/crawl_results.json` 日志

## 📝 许可

本项目仅用于学术研究和教育目的。论文和书籍版权归原作者所有。

## 🙏 致谢

- **Semantic Scholar** - 论文元数据
- **arXiv** - 开放获取预印本
- **LibGen / Archive.org** - 书籍资源
- **OpenRouter** - LLM API服务
