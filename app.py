import streamlit as st
from openai import OpenAI

# --- 页面基础设置 ---
st.set_page_config(page_title="心态炸裂的主播", page_icon="🎮")

# --- 1. 安全认证模块 (不用动) ---
try:
    API_KEY = st.secrets["MY_API_KEY"]
    BASE_URL = st.secrets["MY_BASE_URL"]
    PASSWORD = st.secrets["MY_PASSWORD"]
except FileNotFoundError:
    st.error("❌ 未找到密钥配置！请检查 secrets.toml。")
    st.stop()

# 侧边栏：密码验证
with st.sidebar:
    st.header("🔐 直播间后台")
    input_pwd = st.text_input("请输入访问密码", type="password")
    if input_pwd != PASSWORD:
        st.warning("请输入正确密码进入直播间")
        st.stop()
    else:
        st.success("已连接！")

# --- 2. 初始化 AI ---
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# --- 3. 注入人物灵魂 (关键修改部分) ---
# 我已经把你提取的第 1, 3, 5, 7, 9, 11 句话放进去了
PERSONA_PROMPT = """
你现在扮演一个【刚输了比赛、心态炸裂、极度嘴硬的游戏主播】。
你正在直播复盘刚才的比赛，观众（用户）正在发弹幕和你互动。

【人物状态】：
瘫坐在椅子上，气喘吁吁，感觉心脏病都要犯了。

【说话风格】：
1. 语气极度不耐烦，充满负能量，喜欢叹气。
2. **绝不承认自己菜**，疯狂甩锅给队友、英雄机制、或者装备差距。
3. 情绪激动时会骂骂咧咧（例如“他妈的”、“NC”）。
4. 必须使用刚才那把游戏的术语：蛇女、鳄鱼、六神装、魔抗、龙魂、E技能、WAQ。

【你的经典语录（必须模仿这些话的语气）】：
- “瘫坐在椅子上...”（这是你的动作状态）
- “唉...”（无奈叹气）
- “又黑我啊？这把跟我有鸡毛关系？我前面还一直是优势！”
- “蛇女打团又不厉害，你是不是nc啊？”
- “老子E不死他啊，他妈的！”
- “他肉的跟鬼一样，他点龙魂减速，我能E几下啊？他一个WAQ我就死了，麻烦你玩一玩蛇女再叫，好吗。”

【当前的回复逻辑】：
无论用户说什么，你都要觉得他在黑你，或者觉得他不懂游戏。你要用上面的逻辑回怼他，强调“对面鳄鱼太肉”、“队友不买真眼”、“蛇女这个英雄不行”，反正不是你的锅。
"""

# --- 4. 聊天逻辑 ---
st.title("🎮 直播间：心态崩了")
st.caption("主播正在气头上，请谨慎发言...")

# 初始化历史
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": PERSONA_PROMPT}
    ]

# 显示历史消息
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# 处理用户输入
if user_input := st.chat_input("发条弹幕安慰（或嘲讽）一下主播..."):

    # 显示用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 调用 API
    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model="deepseek-chat",  # 确保你用的是 deepseek-chat
                messages=st.session_state.messages,
                stream=True,
            )
            response = st.write_stream(stream)
            # 保存回复
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            st.error(f"直播间断线了 (API错误): {e}")