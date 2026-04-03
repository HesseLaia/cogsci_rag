"""
认知科学核心教材清单
每本书标注：优先级、重点章节、预期用途
"""

CORE_BOOKS = {
    "philosophy": [
        {
            "title": "The Conscious Mind",
            "author": "David Chalmers",
            "isbn": "0195117891",
            "priority": "high",
            "target_chapters": [
                "The Hard Problem of Consciousness",
                "Consciousness and Cognition",
                "Absent Qualia, Fading Qualia"
            ],
            "extraction_strategy": "精读模式 - 完整章节+summary"
        },
        {
            "title": "Philosophy of Mind",
            "author": "Jaegwon Kim",
            "isbn": "0813344581",
            "priority": "medium",
            "target_chapters": ["Mental Causation", "Functionalism", "Eliminativism"],
            "extraction_strategy": "要点模式 - chapter summary + key sections"
        },
        {
            "title": "Consciousness Explained",
            "author": "Daniel Dennett",
            "isbn": "0316180661",
            "priority": "medium",
            "target_chapters": ["Multiple Drafts Model", "Consciousness as Virtual Machine"],
            "extraction_strategy": "要点模式"
        }
    ],

    "cognitive_neuroscience": [
        {
            "title": "Principles of Neural Science",
            "author": "Kandel et al.",
            "isbn": "0071390111",
            "priority": "high",
            "target_chapters": [
                "Cognition",
                "Learning and Memory",
                "Prefrontal Cortex and Executive Functions",
                "Emotional States and Feelings"
            ],
            "extraction_strategy": "章节级 - 只取认知相关章节，跳过纯解剖学部分"
        },
        {
            "title": "Cognitive Neuroscience: The Biology of the Mind",
            "author": "Gazzaniga et al.",
            "isbn": "0393603105",
            "priority": "high",
            "target_chapters": "all_cognitive",  # 整本都相关
            "extraction_strategy": "精读模式 - 每章summary+case studies"
        },
        {
            "title": "The Cognitive Neurosciences",
            "author": "Gazzaniga (ed.)",
            "isbn": "0262072548",
            "priority": "medium",
            "target_chapters": "selected_papers",  # 论文集，按主题筛选
            "extraction_strategy": "精选论文 - 只取高引用章节"
        }
    ],

    "cognitive_modeling_AI": [
        {
            "title": "The Computational Brain",
            "author": "Churchland & Sejnowski",
            "isbn": "0262531208",
            "priority": "high",
            "target_chapters": [
                "Computational Approaches to Neural Modeling",
                "Learning and Synaptic Modification",
                "Neural Networks for Perception"
            ],
            "extraction_strategy": "精读模式 - 理论章节完整保留"
        },
        {
            "title": "Artificial Intelligence: A Modern Approach",
            "author": "Russell & Norvig",
            "isbn": "0136042597",
            "priority": "medium",
            "target_chapters": [
                "Intelligent Agents",
                "Learning from Examples",
                "Probabilistic Reasoning",
                "Natural Language Processing"
            ],
            "extraction_strategy": "章节级 - 只取认知相关部分"
        },
        {
            "title": "How to Build a Brain",
            "author": "Chris Eliasmith",
            "isbn": "0199794545",
            "priority": "high",
            "target_chapters": "all",
            "extraction_strategy": "精读模式 - 神经工程学核心文本"
        }
    ],

    "linguistics": [
        {
            "title": "The Language Instinct",
            "author": "Steven Pinker",
            "isbn": "0061336467",
            "priority": "high",
            "target_chapters": [
                "Language Acquisition",
                "Universal Grammar",
                "Words and Rules"
            ],
            "extraction_strategy": "精读模式 - 科普但深度足够"
        },
        {
            "title": "Foundations of Language",
            "author": "Ray Jackendoff",
            "isbn": "0198270127",
            "priority": "medium",
            "target_chapters": ["Semantics", "Conceptual Structure"],
            "extraction_strategy": "章节级 - 理论部分"
        },
        {
            "title": "Psycholinguistics",
            "author": "Jean Aitchison",
            "isbn": "1444332961",
            "priority": "high",
            "target_chapters": "all_cognitive",
            "extraction_strategy": "精读模式 - 直接对应心理语言学"
        }
    ],

    "psychological_science": [
        {
            "title": "Thinking, Fast and Slow",
            "author": "Daniel Kahneman",
            "isbn": "0374533555",
            "priority": "high",
            "target_chapters": [
                "The Two Systems",
                "Heuristics and Biases",
                "Overconfidence",
                "Availability and Representativeness"
            ],
            "extraction_strategy": "精读模式 - 经典实验完整保留"
        },
        {
            "title": "Cognitive Psychology",
            "author": "Michael Eysenck",
            "isbn": "1848724160",
            "priority": "high",
            "target_chapters": [
                "Attention and Performance",
                "Learning and Memory",
                "Problem Solving and Expertise"
            ],
            "extraction_strategy": "教材模式 - chapter summary + key studies"
        },
        {
            "title": "Memory: From Mind to Molecules",
            "author": "Squire & Kandel",
            "isbn": "0981519407",
            "priority": "medium",
            "target_chapters": ["Working Memory", "Long-term Memory", "Forgetting"],
            "extraction_strategy": "章节级"
        }
    ],

    "social_sciences": [
        {
            "title": "Social Cognition: From Brains to Culture",
            "author": "Fiske & Taylor",
            "isbn": "1446269582",
            "priority": "high",
            "target_chapters": [
                "Social Neuroscience",
                "Schemas and Memory",
                "Attribution and Social Perception"
            ],
            "extraction_strategy": "精读模式 - 社会认知核心教材"
        },
        {
            "title": "The Cultural Origins of Human Cognition",
            "author": "Michael Tomasello",
            "isbn": "0674005821",
            "priority": "high",
            "target_chapters": "all",
            "extraction_strategy": "精读模式 - 薄书（200+页），全本有价值"
        },
        {
            "title": "Mindreading: An Integrative Account",
            "author": "Alvin Goldman",
            "isbn": "0199230692",
            "priority": "medium",
            "target_chapters": ["Theory of Mind", "Simulation Theory"],
            "extraction_strategy": "章节级"
        }
    ]
}


# 提取策略定义
EXTRACTION_STRATEGIES = {
    "精读模式": {
        "description": "完整章节 + 每章summary + case studies/examples",
        "chunk_size": 2000,  # 字符
        "overlap": 200,
        "include_elements": ["chapter_text", "summaries", "case_studies", "key_concepts"]
    },
    "章节级": {
        "description": "只提取chapter summary + key sections（跳过冗余部分）",
        "chunk_size": 1500,
        "overlap": 150,
        "include_elements": ["summaries", "key_sections", "definitions"]
    },
    "要点模式": {
        "description": "只提取summary/conclusion/key points/highlighted boxes",
        "chunk_size": 1000,
        "overlap": 100,
        "include_elements": ["summaries", "key_points", "definitions", "highlighted_boxes"]
    }
}


# Metadata模板
def build_book_metadata(book_info, chapter_title, chunk_index):
    """构建书籍chunk的metadata"""
    return {
        "source_type": "book",
        "book_title": book_info["title"],
        "author": book_info["author"],
        "isbn": book_info.get("isbn", ""),
        "track": book_info.get("track", ""),
        "chapter": chapter_title,
        "chunk_index": chunk_index,
        "tier": "core_textbook",
        "citation_count": 999,  # 教材标记为核心权重
        "extraction_strategy": book_info.get("extraction_strategy", "章节级")
    }
