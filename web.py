import streamlit as st
import json
import time
import asyncio
import edge_tts
import tempfile
import os
from cozepy import Coze, TokenAuth, COZE_CN_BASE_URL
import PyPDF2
import docx


def read_background_file(uploaded_file):
    if uploaded_file is None:
        return ""

    file_name = uploaded_file.name.lower()
    text = ""
    try:
        # Streamlit 上传的文件可以直接作为字节流被解析
        if file_name.endswith('.txt'):
            text = uploaded_file.getvalue().decode("utf-8")
        elif file_name.endswith('.docx'):
            doc = docx.Document(uploaded_file)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif file_name.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                if page.extract_text():
                    text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        st.error(f"⚠️ 文件读取失败: {e}")
        return ""

# ==========================================
# 新增：尝试导入你之前用的离线语音识别库
# ==========================================
try:
    from faster_whisper import WhisperModel

    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

# 注意：st.set_page_config 必须是第一个 Streamlit 命令
st.set_page_config(page_title="创新创业大赛demo", page_icon="📰", layout="wide")

# ==========================================
# 🚨 队友需要配置的变量区域 (请在此处填入你们自己的信息) 🚨
# ==========================================

# 1. Coze API Token
COZE_API_TOKEN = st.secrets.get("COZE_TOKEN", "请替换为你的_COZE_API_TOKEN")

# 2. Coze 工作流 IDs
WORKFLOW_ID_HOST = "7617241168090316810"  # 【采访者】工作流 ID
WORKFLOW_ID_INTERVIEWEE = "7617226472986902555"  # 【受访者】工作流 ID (后台原ID不变)
WORKFLOW_ID_EDITOR = "7617244491765858342"  # 【初稿撰写】工作流 ID
WORKFLOW_ID_REFINER = "7617247261945135156"  # 【打磨精修】工作流 ID

WORKFLOWS = {
    "host": {
        "name": "采访者",
        "token": COZE_API_TOKEN,
        "id": WORKFLOW_ID_HOST
    },
    "interviewee": {
        "name": "受访者",
        "token": COZE_API_TOKEN,
        "id": WORKFLOW_ID_INTERVIEWEE
    },
    "editor": {
        "name": "初稿",
        "token": COZE_API_TOKEN,
        "id": WORKFLOW_ID_EDITOR
    },
    "refiner": {
        "name": "修改",
        "token": COZE_API_TOKEN,
        "id": WORKFLOW_ID_REFINER
    }
}


# ==========================================
# 核心功能与 API 调用逻辑
# ==========================================

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
# TTS 本地语音生成函数 (Edge-TTS)
# ==========================================
def generate_audio_bytes(text, voice="zh-CN-XiaoxiaoNeural"):
    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_path = fp.name
        await communicate.save(temp_path)
        return temp_path

    try:
        temp_file_path = asyncio.run(_generate())
        with open(temp_file_path, "rb") as f:
            audio_bytes = f.read()
        os.remove(temp_file_path)
        return audio_bytes
    except Exception as e:
        st.error(f"语音生成失败: {str(e)}")
        return None


# ==========================================
# 新增：ASR 离线语音转文字 (Faster-Whisper)
# 加了缓存装饰器，防止页面刷新重复加载模型卡死
# ==========================================
@st.cache_resource(show_spinner="⏳ 正在加载离线语音模型，请稍候...")
def load_whisper_model():
    if HAS_WHISPER:
        return WhisperModel("base", device="cpu", compute_type="int8")
    return None


def transcribe_audio_input(audio_bytes):
    if not HAS_WHISPER:
        return "⚠️ 缺少 faster-whisper 库，无法识别。请在终端运行 pip install faster-whisper"

    model = load_whisper_model()
    if model is None:
        return "⚠️ 模型加载失败。"

    # 将前端传来的音频流写入临时文件供 Whisper 读取
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
        tmp_file.write(audio_bytes.read())
        tmp_path = tmp_file.name

    try:
        segments, _ = model.transcribe(tmp_path, beam_size=5)
        text = "".join([segment.text for segment in segments])
        return text.strip()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ==========================================
# 2. 侧边栏：UI 设置
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
    st.divider()
    st.header("📄 受访者背景资料")
    uploaded_file = st.file_uploader("上传该干部的个人资料(如日记/生平)，AI将据此代入角色", type=["txt", "pdf", "docx"])

    # 解析文件并存入全局状态
    bg_text = read_background_file(uploaded_file)
    if bg_text:
        st.success(f"✅ 已成功读取资料，共 {len(bg_text)} 字。")
        st.session_state.background_info = bg_text
    else:
        st.session_state.background_info = ""

# ==========================================
# 3. 网页 UI 布局与状态管理
# ==========================================
st.title("📰 智能 AI 采编系统：口述历史全自动流水线")
st.caption("集成了全自动对话采访、深度成文与人工介入精修的端到端系统")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "draft_article" not in st.session_state:
    st.session_state.draft_article = ""
if "current_article" not in st.session_state:
    st.session_state.current_article = ""
# 新增：用于保存语音或键盘输入的修改意见
if "feedback_text" not in st.session_state:
    st.session_state.feedback_text = "标题不够抓人，请把核心金句加粗。"

tab1, tab2, tab3 = st.tabs(["阶段一：访谈", "阶段二：撰稿", "阶段三：修改"])

# ------------------------------------------
# Tab 1: 自动访谈室
# ------------------------------------------
with tab1:
    st.header("1. 访谈")

    col1, col2 = st.columns([3, 1])
    with col1:
        initial_topic = st.text_input("给主持人设定一个初始提问：",
                                      "王书记，听说您当年主动申请去西藏扎根，能和我们分享一下当时的想法吗？")
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

                    with st.spinner("🎙️ 正在生成主持人语音..."):
                        audio_data = generate_audio_bytes(current_question)
                        if audio_data:
                            st.audio(audio_data, format="audio/mp3", autoplay=True)

                with st.spinner(f"受访者 正在构思回答 (回合 {i + 1})..."):
                    # 把本地读到的背景资料，作为新变量一起打包发给 Coze
                    api_params = {
                        "input": current_question,
                        "background_info": st.session_state.get("background_info", "")
                    }
                    interviewee_answer = call_workflow("interviewee", api_params)

                with st.chat_message("assistant", avatar="👤"):
                    st.write(f"**受访者**:\n{interviewee_answer}")
                st.session_state.chat_history.append({"role": "受访者", "content": interviewee_answer})

                if i < rounds - 1:
                    with st.spinner("主持人正在结合上下文生成追问..."):
                        history_context = ""
                        for msg in st.session_state.chat_history:
                            history_context += f"{msg['role']}：{msg['content']}\n\n"

                        prompt_for_host = f"以下是目前的完整访谈记录：\n{history_context}\n---\n请根据以上对话，特别是受访者的最后回答，结合最初的议题，生成你下一个深度的追问（直接输出问题，不要寒暄和废话）："

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

        # ==========================================
        # 新增：支持语音与键盘双输入的修改意见区
        # ==========================================
        st.subheader("💡 提供修改意见 (Revision Feedback)")

        input_col1, input_col2 = st.columns([1, 1])
        with input_col1:
            # Streamlit 1.36+ 提供的原生音频输入组件
            audio_val = st.audio_input("🎙️ 点击麦克风直接说出你的修改意见")
            if audio_val is not None:
                with st.spinner("🔄 正在将语音转为文字..."):
                    asr_text = transcribe_audio_input(audio_val)
                    if asr_text and not asr_text.startswith("⚠️"):
                        st.session_state.feedback_text = asr_text
                        st.success("识别成功！请在右侧核对。")
                    else:
                        st.warning(asr_text)

        with input_col2:
            # 文本输入框，它的值绑定到 session_state，这样语音识别后会自动填入这里
            current_feedback = st.text_area(
                "✍️ 键盘输入或核对语音识别结果：",
                value=st.session_state.feedback_text,
                height=120
            )
            # 实时同步用户手动修改的内容
            st.session_state.feedback_text = current_feedback

        if st.button("🚀 让 AI 按意见精修当前版本", type="primary", use_container_width=True):
            with st.spinner("Draft Refiner 正在根据您的意见重构当前文章..."):
                final_article = call_workflow("refiner", {
                    "original_article": st.session_state.current_article,
                    "revision_feedback": st.session_state.feedback_text,
                    "original_talk": st.session_state.transcript
                })

                st.session_state.current_article = final_article
                st.success("✅ 精修完成！上方文章已更新为最新版本。")
                time.sleep(1)
                st.rerun()