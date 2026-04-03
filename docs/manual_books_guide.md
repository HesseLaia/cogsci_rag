# 手动获取书籍指南

自动爬取可能受网络限制，这里提供手动获取方案。

## 🎯 推荐来源（按优先级）

### 1. Z-Library (最全)
- 网址: https://zh.zlibrary-global.se/
- 注册后免费下载
- 搜索书名或ISBN即可

### 2. Library Genesis (LibGen)
- 镜像1: https://libgen.is/
- 镜像2: https://libgen.rs/
- 直接搜索，无需注册

### 3. Anna's Archive
- 网址: https://annas-archive.org/
- 整合了多个来源，成功率高

### 4. Internet Archive
- 网址: https://archive.org/
- 部分书籍可借阅（1小时）

---

## 📚 18本核心教材下载清单

### 哲学 (Philosophy)
- [ ] **The Conscious Mind** by David Chalmers (ISBN: 0195117891)
- [ ] **Philosophy of Mind** by Jaegwon Kim (ISBN: 0813344581)
- [ ] **Consciousness Explained** by Daniel Dennett (ISBN: 0316180661)

### 认知神经科学 (Cognitive Neuroscience)
- [ ] **Principles of Neural Science** by Kandel et al. (ISBN: 0071390111)
- [ ] **Cognitive Neuroscience** by Gazzaniga et al. (ISBN: 0393603105)
- [ ] **The Cognitive Neurosciences** by Gazzaniga (ISBN: 0262072548)

### 认知建模与AI (Cognitive Modeling & AI)
- [ ] **The Computational Brain** by Churchland & Sejnowski (ISBN: 0262531208)
- [ ] **AI: A Modern Approach** by Russell & Norvig (ISBN: 0136042597)
- [ ] **How to Build a Brain** by Chris Eliasmith (ISBN: 0199794545)

### 语言学 (Linguistics)
- [ ] **The Language Instinct** by Steven Pinker (ISBN: 0061336467)
- [ ] **Foundations of Language** by Ray Jackendoff (ISBN: 0198270127)
- [ ] **Psycholinguistics** by Jean Aitchison (ISBN: 1444332961)

### 心理科学 (Psychological Science)
- [ ] **Thinking, Fast and Slow** by Daniel Kahneman (ISBN: 0374533555)
- [ ] **Cognitive Psychology** by Michael Eysenck (ISBN: 1848724160)
- [ ] **Memory: From Mind to Molecules** by Squire & Kandel (ISBN: 0981519407)

### 社会科学 (Social Sciences)
- [ ] **Social Cognition** by Fiske & Taylor (ISBN: 1446269582)
- [ ] **Cultural Origins of Human Cognition** by Tomasello (ISBN: 0674005821)
- [ ] **Mindreading** by Alvin Goldman (ISBN: 0199230692)

---

## 📂 下载后的处理

### 0. 支持的格式（按优先级）
- ✅ **PDF** - 最佳，优先下载
- ✅ **EPUB** - 支持，自动提取章节
- ⚠️ **MOBI** - 部分支持（需转换）
- ❌ **DJVU/TXT** - 不推荐

### 1. 文件命名规则
```
{track}_{书名前50字符}.{格式}
```

例如：
```
philosophy_The_Conscious_Mind.pdf
philosophy_The_Conscious_Mind.epub        ← EPUB也可以
cognitive_neuroscience_Principles_of_Neural_Science.pdf
```

### 2. 保存位置
```
papers/books_cache/
```

### 3. 安装依赖（首次）
```bash
# PDF支持（可能已安装）
pip install pdfplumber

# EPUB支持（如果下载了EPUB格式）
pip install ebooklib beautifulsoup4
```

### 4. 继续处理
下载完成后，直接运行：
```bash
python book_processor_enhanced.py   # 增强版，支持PDF+EPUB
python merge_books.py               # 合并数据
```

---

## 💡 搜索技巧

### Z-Library
1. 先用 **ISBN** 搜索（最精确）
2. 如果没有，用 **书名 + 作者** 搜索
3. 选择 **PDF** 格式（避免 EPUB/MOBI）

### LibGen
1. 切换到 **Scientific articles** 标签页
2. 搜索框输入书名
3. 按 **Year** 排序，选最新版

### Anna's Archive
1. 直接输入 ISBN 或书名
2. 看 **文件大小**（太小可能是扫描版）
3. 优先选 **libgen** 来源的

---

## ⚠️ 注意事项

1. **版权问题**：仅用于学习研究，不要传播
2. **文件质量**：
   - 优先选 **非扫描版**（可复制文字）
   - 文件大小 5-50MB 为宜
   - 避免 DRM 加密的
3. **版本选择**：
   - 教材选最新版（内容更新）
   - 经典著作无所谓版本

---

## 🚀 快速开始

如果完全手动下载，推荐这个优先级：

### Tier 1 (必下，7本)
这些书最容易找到，且对RAG系统提升最大：
1. Thinking, Fast and Slow (Kahneman)
2. The Language Instinct (Pinker)
3. The Conscious Mind (Chalmers)
4. Cognitive Neuroscience (Gazzaniga)
5. AI: A Modern Approach (Russell & Norvig)
6. How to Build a Brain (Eliasmith)
7. Cultural Origins of Human Cognition (Tomasello)

### Tier 2 (推荐，7本)
有了更好，但可以晚点补：
8. Social Cognition (Fiske & Taylor)
9. Cognitive Psychology (Eysenck)
10. Philosophy of Mind (Kim)
11. Psycholinguistics (Aitchison)
12. The Computational Brain (Churchland)
13. Foundations of Language (Jackendoff)
14. Consciousness Explained (Dennett)

### Tier 3 (可选，4本)
巨著，可以只下载关键章节：
15. Principles of Neural Science (Kandel) - 1500页，只要认知相关章节
16. The Cognitive Neurosciences (Gazzaniga) - 论文集
17. Memory: From Mind to Molecules (Squire)
18. Mindreading (Goldman)

---

下载完成后告诉我，我帮你运行处理脚本！
