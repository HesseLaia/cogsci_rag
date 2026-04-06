"""
CogSci RAG — Streamlit 界面
运行：streamlit run app.py
"""

from datetime import datetime

import streamlit as st
from cogsci_rag import (
    load_papers, build_or_load_vectorstore, get_embedder,
    hybrid_retrieve, ask_openrouter, build_user_profile,
    build_system_prompt,
    SessionMemory, UserMemory,
    TRACK_NAMES, USER_PROFILE_QUESTIONS,
    SYSTEM_PROMPT, INTRO_SYSTEM_PROMPT,
    update_concept_understanding,
    generate_cognitive_summary,
)

# ── 页面配置 ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="CogSci RAG",
    page_icon="🧠",
    layout="wide",
)

# ── 初始化（只跑一次） ───────────────────────────────────────────
@st.cache_resource
def init():
    papers     = load_papers()
    collection = build_or_load_vectorstore(papers)
    get_embedder()
    return papers, collection

papers, collection = init()

# ── Session state 初始化 ─────────────────────────────────────────
if "profile_done"   not in st.session_state:
    st.session_state.profile_done   = False
if "user_profile"   not in st.session_state:
    st.session_state.user_profile   = ""
if "answers"        not in st.session_state:
    st.session_state.answers        = {}
if "messages"       not in st.session_state:
    st.session_state.messages       = []   # {role, content, sources}
if "profile_step"   not in st.session_state:
    st.session_state.profile_step   = 0
if "user_memory"    not in st.session_state:
    st.session_state.user_memory    = UserMemory()
if "session_memory" not in st.session_state:
    st.session_state.session_memory = SessionMemory(
        datetime.now().strftime("%Y%m%d_%H%M%S")
    )

# ── 侧边栏 ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 CogSci RAG")
    st.caption("认知科学论文知识库问答")
    st.divider()

    if st.session_state.profile_done:
        # 知识库统计
        st.markdown("### 知识库")
        counts = {}
        for p in papers:
            k = TRACK_NAMES.get(p.get("track", ""), p.get("track", "未知"))
            counts[k] = counts.get(k, 0) + 1
        for k, n in sorted(counts.items(), key=lambda x: -x[1]):
            st.markdown(f"`{k}` &nbsp; **{n}篇**")
        st.caption(f"共 {len(papers)} 篇")
        st.divider()

        # 使用说明
        st.markdown("### 使用方式")
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
        st.divider()

        st.markdown("### 对话记忆")
        if st.session_state.session_memory.current_topics:
            st.caption("当前话题")
            for topic in st.session_state.session_memory.current_topics:
                st.caption(f"· {topic}")
        top_in = st.session_state.user_memory.get_top_interests(3)
        if top_in:
            st.caption("常问主题（本地累计）")
            for interest in top_in:
                cnt = st.session_state.user_memory.data["interests"]["topics"][
                    interest
                ].get("mentions", 0)
                st.caption(f"· {interest}（{cnt}次）")
        if st.button("清除本次对话记忆", use_container_width=True):
            st.session_state.session_memory = SessionMemory(
                datetime.now().strftime("%Y%m%d_%H%M%S")
            )
            st.session_state.messages = []
            st.rerun()
        st.divider()

        # 重置按钮
        if st.button("🔄 重新填写问卷", use_container_width=True):
            st.session_state.profile_done = False
            st.session_state.answers      = {}
            st.session_state.profile_step = 0
            st.session_state.messages     = []
            st.session_state.session_memory = SessionMemory(
                datetime.now().strftime("%Y%m%d_%H%M%S")
            )
            st.rerun()

# ── 问卷界面 ─────────────────────────────────────────────────────
if not st.session_state.profile_done:
    st.markdown("## 👋 先花30秒让我了解一下你")
    st.markdown("这会影响我解释概念的方式和类比选择。")
    st.divider()

    with st.form("profile_form"):
        form_answers = {}
        for q in USER_PROFILE_QUESTIONS:
            key  = q["key"]
            opts = q["options"]

            if key == "interest":
                st.markdown(f"**{q['question']}**")
                selected = []
                cols = st.columns(len(opts))
                for ci, (k, v) in enumerate(opts.items()):
                    if cols[ci].checkbox(v, key=f"interest_{k}"):
                        selected.append(k)
                form_answers[key] = "".join(selected) if selected else "A"
            else:
                labels = [f"{k}. {v}" for k, v in opts.items()]
                choice = st.radio(
                    f"**{q['question']}**",
                    options=list(opts.keys()),
                    format_func=lambda x, o=opts: f"{x}. {o[x]}",
                    horizontal=True,
                    key=f"radio_{key}"
                )
                form_answers[key] = choice

            st.write("")  # 间距

        submitted = st.form_submit_button("开始吧 →", use_container_width=True, type="primary")

    if submitted:
        if not form_answers.get("interest"):
            st.warning("请至少选择一个感兴趣的方向")
        else:
            profile = build_user_profile(form_answers)
            st.session_state.user_profile = profile
            st.session_state.answers      = form_answers
            st.session_state.profile_done = True
            st.rerun()

    st.stop()

# ── 主界面：对话 ─────────────────────────────────────────────────
st.markdown("## 🧠 CogSci RAG")

# 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # 显示引用来源
        if msg.get("sources"):
            with st.expander("📄 检索到的来源", expanded=False):
                for i, d in enumerate(msg["sources"], 1):
                    track_cn = TRACK_NAMES.get(d["track"], d["track"])
                    cite_str = f" · {d['citations']}次引用" if d.get("citations") else ""
                    url      = d.get("url", "")
                    if d.get("source_type") == "book":
                        bt = d.get("book_title") or d["title"]
                        title_md = bt
                    else:
                        title_md = f"[{d['title']}]({url})" if url else d["title"]
                    st.markdown(
                        f"**[{i}]** {title_md}  \n"
                        f"<small>{d['authors']} · {d['year']} · {track_cn}{cite_str}</small>",
                        unsafe_allow_html=True,
                    )

# 输入框
user_input = st.chat_input("问点什么，或「入门」「地图」「综述」「假设」+主题...")

if user_input:
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 判断模式
    is_intro       = user_input.startswith("入门")
    is_concept_map = user_input.startswith("地图")
    is_survey      = user_input.startswith("综述")
    is_hypothesis  = user_input.startswith("假设")
    topic          = user_input[2:].strip() if (is_intro or is_concept_map or is_survey or is_hypothesis) else user_input

    # 构建带画像的prompt（每次从session state里取，含认知摘要）
    base_profile = build_system_prompt(
        st.session_state.user_profile,
        st.session_state.user_memory.data.get("cognitive_summary", ""),
    )

    sys_qa    = SYSTEM_PROMPT.replace("{user_profile}", base_profile)
    sys_intro = INTRO_SYSTEM_PROMPT.replace("{user_profile}", base_profile)

    # 检索 + 生成
    with st.chat_message("assistant"):
        with st.spinner("检索相关论文..."):
            docs = hybrid_retrieve(topic, collection)

        if is_concept_map:
            mode = "concept_map"
        elif is_survey:
            mode = "survey"
        elif is_hypothesis:
            mode = "hypothesis"
        elif is_intro:
            mode = "intro"
        else:
            mode = "qa"

        expanded_sources = (mode == "hypothesis")

        if mode == "concept_map":
            from cogsci_rag import ask_concept_map
            with st.spinner("生成概念地图..."):
                result = ask_concept_map(topic, docs, st.session_state.user_profile)

            if "error" not in result:
                st.markdown(f"### 核心定义\n{result.get('core', '')}")
                st.divider()

                st.markdown("### 相关概念")
                related = result.get("related") or []
                if related:
                    cols = st.columns(min(len(related), 3))
                    for i, rel in enumerate(related):
                        if not isinstance(rel, dict):
                            continue
                        with cols[i % len(cols)]:
                            st.info(
                                f"**{rel.get('concept', '')}**\n\n{rel.get('relation', '')}"
                            )
                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 争议点")
                    st.warning(result.get("debate", ""))
                with col2:
                    st.markdown("### 入门推荐")
                    st.success(result.get("entry_point", ""))

                st.divider()
                st.markdown("### 代表人物")
                kf = result.get("key_figures") or []
                kf = [str(x) for x in kf if x is not None]
                st.caption("、".join(kf) if kf else "—")

                answer = f"概念地图已生成（{topic}）"
            else:
                st.error(f"生成失败：{result.get('error')}")
                answer = result.get("raw", "生成失败")
        elif mode == "survey":
            from cogsci_rag import ask_survey
            st.warning("⚠️ 综述基于知识库现有文献，不保证覆盖最新进展")
            with st.spinner("生成综述中（检索扩展到12篇）..."):
                answer, docs = ask_survey(topic, docs, st.session_state.user_profile)
            st.markdown(answer)
        elif mode == "hypothesis":
            from cogsci_rag import ask_hypothesis
            with st.spinner("生成研究假设..."):
                answer = ask_hypothesis(topic, docs, st.session_state.user_profile)
            st.markdown(answer)
        else:
            # 临时替换全局prompt（ask_openrouter用的active_system_prompt）
            import cogsci_rag
            cogsci_rag.active_system_prompt = sys_qa
            cogsci_rag.active_intro_prompt  = sys_intro

            chat_hist = []
            for msg in st.session_state.messages[:-1]:
                chat_hist.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })
            with st.spinner("生成回答..."):
                answer = ask_openrouter(
                    topic,
                    docs,
                    mode=mode,
                    session_memory=st.session_state.session_memory,
                    chat_history=chat_hist,
                )

            st.markdown(answer)

        # 来源折叠面板
        if docs:
            with st.expander("📄 检索到的来源", expanded=expanded_sources):
                for i, d in enumerate(docs, 1):
                    track_cn = TRACK_NAMES.get(d["track"], d["track"])
                    cite_str = f" · {d['citations']}次引用" if d.get("citations") else ""
                    url      = d.get("url", "")
                    if d.get("source_type") == "book":
                        bt = d.get("book_title") or d["title"]
                        title_md = bt
                    else:
                        title_md = f"[{d['title']}]({url})" if url else d["title"]
                    st.markdown(
                        f"**[{i}]** {title_md}  \n"
                        f"<small>{d['authors']} · {d['year']} · {track_cn}{cite_str}</small>",
                        unsafe_allow_html=True,
                    )

    # 存入历史
    st.session_state.messages.append({
        "role":    "assistant",
        "content": answer,
        "sources": docs,
    })

    topics = st.session_state.session_memory.add_turn(user_input, answer, docs)
    st.session_state.user_memory.record_turn_after(
        topics,
        docs,
        st.session_state.answers.get("interest"),
    )
    update_concept_understanding(
        user_input,
        st.session_state.user_memory,
        st.session_state.user_profile,
    )
    generate_cognitive_summary(st.session_state.user_memory)