import streamlit as st
import json
import time
import asyncio
import edge_tts
import tempfile
import os
from cozepy import Coze, TokenAuth, COZE_CN_BASE_URL

# ==========================================
# 1. 核心配置与 API 初始化
# ==========================================
st.set_page_config(page_title="创新创业大赛demo", page_icon="📰", layout="wide")

# 最新的有效 Token (建议测试完毕后在Coze后台重置，避免泄露)
NEW_TOKEN = st.secrets["COZE_TOKEN"]

WORKFLOWS = {
    "host": {
        "name": "采访者",
        "token": NEW_TOKEN,
        "id": "7617241168090316810"
    },
    "lecun": {
        "name": "Yann LeCun",
        "token": NEW_TOKEN,
        "id": "7617226472986902555"
    },
    "editor": {
        "name": "初稿",
        "token": NEW_TOKEN,
        "id": "7617244491765858342"
    },
    "refiner": {
        "name": "修改",
        "token": NEW_TOKEN,
        "id": "7617247261945135156"
    }
}


# 统一的 Coze 工作流调用函数
def call_workflow(role_key, parameters):
    config = WORKFLOWS[role_key]
    coze = Coze(auth=TokenAuth(token=config["token"]), base_url=COZE_CN_BASE_URL)

    try:
        workflow_result = coze.workflows.runs.create(
            workflow_id=config["id"],
            parameters=parameters
        )
        data_dict = json.loads(workflow_result.data)
        ans = data_dict.get("output", str(data_dict))

        if isinstance(ans, list):
            ans = "\n\n".join(str(item) for item in ans)

        return ans
    except Exception as e:
        return f"❌ 调用 {config['name']} 时发生错误: {str(e)}"


# ==========================================
# 新增：本地 TTS 语音生成函数 (Edge-TTS)
# ==========================================
def generate_audio_bytes(text, voice="zh-CN-XiaoxiaoNeural"):
    """
    将文本转换为音频流。
    可选音色(voice)：
    - 'zh-CN-YunxiNeural' (男声，干练，适合记者)
    - 'zh-CN-XiaoxiaoNeural' (女声，清晰温暖)
    """

    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        # 创建一个临时文件来保存音频
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_path = fp.name
        await communicate.save(temp_path)
        return temp_path

    try:
        # 运行异步函数
        temp_file_path = asyncio.run(_generate())
        # 读取音频字节流用于 Streamlit 播放
        with open(temp_file_path, "rb") as f:
            audio_bytes = f.read()
        # 读取完毕后立刻删除临时文件，防止占用硬盘
        os.remove(temp_file_path)
        return audio_bytes
    except Exception as e:
        st.error(f"语音生成失败: {str(e)}")
        return None


# ==========================================
# 2. 侧边栏：UI 设置 (全局字体与黑夜模式)
# ==========================================
with st.sidebar:
    st.header("⚙️ 界面与排版设置")
    font_size = st.slider("调整字体大小", min_value=12, max_value=24, value=16)
    read_mode = st.radio("👁️ 界面模式", ["浅色模式 (普通)", "深色模式 (黑夜)"])

    if read_mode == "深色模式 (黑夜)":
        bg_color = "#0E1117"
        sidebar_bg = "#262730"
        text_color = "#FAFAFA"
        input_bg = "#262730"
    else:
        bg_color = "#FFFFFF"
        sidebar_bg = "#F0F2F6"
        text_color = "#31333F"
        input_bg = "#FFFFFF"

    custom_css = f"""
    <style>
        [data-testid="stAppViewContainer"] {{ background-color: {bg_color} !important; }}
        [data-testid="stSidebar"] {{ background-color: {sidebar_bg} !important; }}
        [data-testid="stHeader"] {{ background-color: transparent !important; }}
        h1, h2, h3, h4, h5, h6, p, span, label, li {{ color: {text_color} !important; }}
        p, li, label, .stTextArea textarea, .stTextInput input, div[data-baseweb="base-input"] {{ font-size: {font_size}px !important; }}
        div[data-baseweb="base-input"] > div, .stTextArea textarea, .stTextInput input {{ background-color: {input_bg} !important; color: {text_color} !important; }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# 3. 网页 UI 布局与状态管理
# ==========================================
st.title("📰 智能 AI 编辑部：全自动采编发流水线")
st.caption("集成了全自动对话采访、深度成文与人工介入精修的端到端系统")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "draft_article" not in st.session_state:
    st.session_state.draft_article = ""
if "current_article" not in st.session_state:
    st.session_state.current_article = ""

tab1, tab2, tab3 = st.tabs(["阶段一：访谈", "阶段二：撰稿", "阶段三：修改"])

# ------------------------------------------
# Tab 1: 自动访谈室
# ------------------------------------------
with tab1:
    st.header("1. 访谈")

    col1, col2 = st.columns([3, 1])
    with col1:
        initial_topic = st.text_input("给主持人设定一个初始提问：",
                                      "杨教授，既然大语言模型已经能写代码了，为什么我们还要搞世界模型？")
    with col2:
        rounds = st.number_input("设置自动对谈回合数", min_value=1, max_value=10, value=3)

    if st.button("开始访谈", type="primary"):
        st.session_state.chat_history = []
        current_question = initial_topic
        st.session_state.chat_history.append({"role": "主持人", "content": current_question})

        chat_container = st.container()

        for i in range(rounds):
            with chat_container:
                with st.chat_message("user", avatar="🎤"):
                    st.write(f"**主持人 (回合 {i + 1})**:\n{current_question}")

                    # === 新增：在此处生成并播放主持人的语音 ===
                    with st.spinner("🎙️ 正在生成主持人语音..."):
                        audio_data = generate_audio_bytes(current_question)
                        if audio_data:
                            st.audio(audio_data, format="audio/mp3", autoplay=True)

                with st.spinner(f"Yann LeCun 正在构思反击 (回合 {i + 1})..."):
                    lecun_answer = call_workflow("lecun", {"input": current_question})

                with st.chat_message("assistant", avatar="🕶️"):
                    st.write(f"**Yann LeCun**:\n{lecun_answer}")
                st.session_state.chat_history.append({"role": "Yann LeCun", "content": lecun_answer})

                if i < rounds - 1:
                    with st.spinner("主持人正在结合上下文生成追问..."):
                        history_context = ""
                        for msg in st.session_state.chat_history:
                            history_context += f"{msg['role']}：{msg['content']}\n\n"

                        prompt_for_host = f"以下是目前的完整访谈记录：\n{history_context}\n---\n请根据以上对话，特别是LeCun的最后回答，结合最初的议题，生成你下一个尖锐的追问（直接输出问题，不要寒暄和废话）："

                        next_question = call_workflow("host", {"input": prompt_for_host})
                        current_question = next_question
                        st.session_state.chat_history.append({"role": "主持人", "content": current_question})

                time.sleep(1)

        st.success("✅ 访谈结束！")
        transcript = ""
        for msg in st.session_state.chat_history:
            transcript += f"**{msg['role']}**：\n{msg['content']}\n\n"
        st.session_state.transcript = transcript

    if st.session_state.transcript:
        with st.expander("查看/编辑原始访谈录 (生肉)", expanded=True):
            st.session_state.transcript = st.text_area("这部分将被直接喂给阶段二的主编", st.session_state.transcript,
                                                       height=300)

# ------------------------------------------
# Tab 2: 主编撰稿
# ------------------------------------------
with tab2:
    st.header("2. 专稿生成")
    st.info("将阶段一生成的访谈流水账，结构化为精美的 Markdown 文章。")

    if st.button("📝 一键生成专稿"):
        if not st.session_state.transcript:
            st.warning("请先在阶段一完成访谈！")
        else:
            with st.spinner("主编正在撰写文章..."):
                draft = call_workflow("editor", {"input": st.session_state.transcript})
                st.session_state.draft_article = draft
                st.session_state.current_article = draft

    if st.session_state.draft_article:
        st.success("初稿生成完毕！请前往“阶段三”进行迭代精修。")
        st.markdown(st.session_state.draft_article)

# ------------------------------------------
# Tab 3: 初稿精修与下载
# ------------------------------------------
with tab3:
    st.header("3. 打磨与迭代精修")
    st.info("在这里你可以无限次进行迭代修改。支持手动改字，也支持一键下载最终定稿。")

    if not st.session_state.current_article:
        st.warning("请先在阶段二生成初稿！")
    else:
        edit_tab, preview_tab = st.tabs(["✏️ 编辑源码", "👁️ 实时预览"])

        with edit_tab:
            edited_article = st.text_area(
                "📝 您可以在此直接修改 Markdown 源码：",
                st.session_state.current_article,
                height=400
            )
            st.session_state.current_article = edited_article

        with preview_tab:
            st.markdown(st.session_state.current_article)

        st.download_button(
            label="📥 下载最终定稿 (.md)",
            data=st.session_state.current_article,
            file_name="AI_访谈专稿_最终版.md",
            mime="text/markdown",
            type="primary"
        )

        st.divider()

        feedback = st.text_area("💡 请输入给 AI 的修改意见 (Revision Feedback)：",
                                "标题不够抓人，请把核心金句加粗。")

        if st.button("让 AI 按意见精修当前版本"):
            with st.spinner("Draft Refiner 正在根据您的意见重构当前文章..."):
                final_article = call_workflow("refiner", {
                    "original_article": st.session_state.current_article,
                    "revision_feedback": feedback,
                    "original_talk": st.session_state.transcript
                })

                st.session_state.current_article = final_article
                st.success("✅ 精修完成！上方文章已更新为最新版本。")
                time.sleep(1)
                st.rerun()