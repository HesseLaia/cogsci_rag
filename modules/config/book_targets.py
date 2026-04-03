"""
认知科学核心教材清单（已更新为实际下载的文件名）
"""

CORE_BOOKS = {
    "philosophy": [
        {
            "title": "The_Conscious_Mind",
            "author": "David Chalmers",
            "isbn": "0195117891",
            "priority": "high",
            "target_chapters": [
                "The Hard Problem of Consciousness",
                "Consciousness and Cognition",
                "Absent Qualia, Fading Qualia"
            ],
            "extraction_strategy": "精读模式"
        },
        {
            "title": "Philosophy_of_Mind",
            "author": "Jaegwon Kim",
            "isbn": "0813344581",
            "priority": "medium",
            "target_chapters": ["Mental Causation", "Functionalism", "Eliminativism"],
            "extraction_strategy": "要点模式"
        },
        {
            "title": "Consciousness_Explained",
            "author": "Daniel Dennett",
            "isbn": "0316180661",
            "priority": "medium",
            "target_chapters": ["Multiple Drafts Model", "Consciousness as Virtual Machine"],
            "extraction_strategy": "要点模式"
        }
    ],

    "cognitive_neuroscience": [
        {
            "title": "Principles_of_Neural_Science",
            "author": "Kandel et al.",
            "isbn": "0071390111",
            "priority": "high",
            "target_chapters": [
                "Cognition",
                "Learning and Memory",
                "Prefrontal Cortex and Executive Functions",
                "Emotional States and Feelings"
            ],
            "extraction_strategy": "章节级"
        },
        {
            "title": "The_Cognitive_Neurosciences",
            "author": "Gazzaniga (ed.)",
            "isbn": "0262072548",
            "priority": "medium",
            "target_chapters": "selected_papers",
            "extraction_strategy": "精选论文"
        }
    ],

    "cognitive_modeling_AI": [
        {
            "title": "The_Computational_Brain",
            "author": "Churchland & Sejnowski",
            "isbn": "0262531208",
            "priority": "high",
            "target_chapters": [
                "Computational Approaches to Neural Modeling",
                "Learning and Synaptic Modification",
                "Neural Networks for Perception"
            ],
            "extraction_strategy": "精读模式"
        },
        {
            "title": "AI_A_Modern_Approach",
            "author": "Russell & Norvig",
            "isbn": "0136042597",
            "priority": "medium",
            "target_chapters": [
                "Intelligent Agents",
                "Learning from Examples",
                "Probabilistic Reasoning",
                "Natural Language Processing"
            ],
            "extraction_strategy": "章节级"
        },
        {
            "title": "How_to_Build_a_Brain",
            "author": "Chris Eliasmith",
            "isbn": "0199794545",
            "priority": "high",
            "target_chapters": "all",
            "extraction_strategy": "精读模式"
        }
    ],

    "linguistics": [
        {
            "title": "The_Language_Instinct",
            "author": "Steven Pinker",
            "isbn": "0061336467",
            "priority": "high",
            "target_chapters": [
                "Language Acquisition",
                "Universal Grammar",
                "Words and Rules"
            ],
            "extraction_strategy": "精读模式"
        },
        {
            "title": "Foundations_of_Language",
            "author": "Ray Jackendoff",
            "isbn": "0198270127",
            "priority": "medium",
            "target_chapters": ["Semantics", "Conceptual Structure"],
            "extraction_strategy": "章节级"
        },
        {
            "title": "Psycholinguistics",
            "author": "Jean Aitchison",
            "isbn": "1444332961",
            "priority": "high",
            "target_chapters": "all_cognitive",
            "extraction_strategy": "精读模式"
        }
    ],

    "psychological_science": [
        {
            "title": "Thinking_Fast_and_Slow",
            "author": "Daniel Kahneman",
            "isbn": "0374533555",
            "priority": "high",
            "target_chapters": [
                "The Two Systems",
                "Heuristics and Biases",
                "Overconfidence",
                "Availability and Representativeness"
            ],
            "extraction_strategy": "精读模式"
        },
        {
            "title": "Memory_From_Mind_to_Molecules",
            "author": "Squire & Kandel",
            "isbn": "0981519407",
            "priority": "medium",
            "target_chapters": ["Working Memory", "Long-term Memory", "Forgetting"],
            "extraction_strategy": "章节级"
        }
    ],

    "social_sciences": [
        {
            "title": "Social_Cognition",
            "author": "Fiske & Taylor",
            "isbn": "1446269582",
            "priority": "high",
            "target_chapters": [
                "Social Neuroscience",
                "Schemas and Memory",
                "Attribution and Social Perception"
            ],
            "extraction_strategy": "精读模式"
        },
        {
            "title": "Cultural_Origins_of_Human_Cognition",
            "author": "Michael Tomasello",
            "isbn": "0674005821",
            "priority": "high",
            "target_chapters": "all",
            "extraction_strategy": "精读模式"
        },
        {
            "title": "Mindreading",
            "author": "Alvin Goldman",
            "isbn": "0199230692",
            "priority": "medium",
            "target_chapters": ["Theory of Mind", "Simulation Theory"],
            "extraction_strategy": "章节级"
        }
    ]
}


# 提取策略定义（保持不变）
EXTRACTION_STRATEGIES = {
    "精读模式": {
        "description": "完整章节 + 每章summary + case studies/examples",
        "chunk_size": 2000,
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


def build_book_metadata(book_info, chapter_title, chunk_index):
    """构建书籍chunk的metadata"""
    return {
        "source_type": "book",
        "book_title": book_info["title"].replace("_", " "),
        "author": book_info["author"],
        "isbn": book_info.get("isbn", ""),
        "track": book_info.get("track", ""),
        "chapter": chapter_title,
        "chunk_index": chunk_index,
        "tier": "core_textbook",
        "citation_count": 999,
        "extraction_strategy": book_info.get("extraction_strategy", "章节级")
    }
