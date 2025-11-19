import streamlit as st
from openai import OpenAI

# --- 1. 基础配置 ---
st.set_page_config(page_title="无限末日生存", page_icon="🧟", layout="wide")

try:
    client = OpenAI(api_key=st.secrets["MY_API_KEY"], base_url=st.secrets["MY_BASE_URL"])
except:
    st.error("请先配置 .streamlit/secrets.toml")
    st.stop()

# --- 2. 初始化游戏状态 (关键！) ---
# 我们需要用 session_state 来记住血量、背包和剧情
if "hp" not in st.session_state:
    st.session_state.hp = 100  # 初始血量
if "inventory" not in st.session_state:
    st.session_state.inventory = ["破旧的衣服", "一瓶水"]  # 初始装备
if "history" not in st.session_state:
    st.session_state.history = []  # 聊天记录

# --- 3. 侧边栏：玩家状态面板 ---
with st.sidebar:
    st.title("🧟 幸存者状态")
    
    # 显示血条
    st.metric("生命值 (HP)", f"{st.session_state.hp}/100")
    st.progress(st.session_state.hp / 100)
    
    # 显示背包
    st.write("🎒 **背包物品:**")
    for item in st.session_state.inventory:
        st.info(item)
    
    # 重置游戏按钮
    if st.button("☠️ 重开一局"):
        st.session_state.hp = 100
        st.session_state.inventory = ["破旧的衣服", "一瓶水"]
        st.session_state.history = []
        st.rerun()

# --- 4. 定义游戏引擎 (System Prompt) ---
# 这是整个游戏的核心，教 AI 怎么遵守规则
SYSTEM_PROMPT = f"""
你是一个文字冒险游戏的上帝（DM）。背景是【丧尸末日】。
玩家是一个幸存者。

【当前状态】：
- 玩家血量：{st.session_state.hp}
- 玩家背包：{','.join(st.session_state.inventory)}

【回复规则 (必须严格遵守！！！)】：
1. 先描写剧情，告诉玩家发生了什么，环境怎么样，有什么危险或机遇。
2. 剧情最后，给出 2-3 个行动选项供玩家选择。
3. **关键机制**：在回复的最后，必须使用分隔符 `|||` 来更新玩家状态。
   格式：`剧情文本... ||| 新的血量数值 ||| 新的背包物品列表(逗号分隔)`

【例子】：
玩家：我吃掉面包，然后去打丧尸。
你的回复：
你大口吃下面包，感觉体力恢复了。但是丧尸冲了过来，你用木棍狠狠敲碎了它的头，不过你也被抓伤了手臂。
现在你面前有一家废弃超市，门开着。
1. 进入超市搜刮。
2. 继续沿大路走。
||| 95 ||| 木棍, 绷带

(注意：如果物品没变，就照抄旧的；如果血量没变，就照抄旧的。如果玩家死了，血量设为0)
"""

# --- 5. 游戏主界面 ---
st.title("🧟 无限末日：文字求生")
st.caption("你的每一个选择，都决定了你能活多久...")

# 显示历史剧情
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 游戏结束判定
if st.session_state.hp <= 0:
    st.error("💀 你已经死亡... 请点击左侧按钮重开一局。")
    st.stop()

# --- 6. 处理玩家输入 ---
if user_input := st.chat_input("你会怎么做？(例如：搜刮房间 / 逃跑)"):
    
    # 1. 显示玩家动作
    st.session_state.history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 2. 调用 AI 引擎
    with st.chat_message("assistant"):
        with st.spinner("命运正在转动..."):
            # 构造消息链
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                # 注意：我们只把剧情历史发给 AI，不发之前的状态指令，节省 token 且防乱
                *[{"role": m["role"], "content": m["content"]} for m in st.session_state.history[-6:]] 
            ]
            
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=1.2, # 稍微高一点，让剧情更随机
                )
                raw_reply = response.choices[0].message.content
                
                # --- 7. 解析“暗号” (Parsers) ---
                # AI 返回的可能是： "剧情... ||| 90 ||| 物品A, 物品B"
                if "|||" in raw_reply:
                    parts = raw_reply.split("|||")
                    story_text = parts[0].strip()
                    
                    # 尝试解析血量
                    try:
                        new_hp = int(parts[1].strip())
                        st.session_state.hp = new_hp
                    except:
                        pass # 如果AI格式错了，就忽略血量变化
                    
                    # 尝试解析背包
                    try:
                        new_inv_str = parts[2].strip()
                        # 简单的清理逻辑
                        new_inv = [item.strip() for item in new_inv_str.split(",") if item.strip()]
                        st.session_state.inventory = new_inv
                    except:
                        pass
                    
                    # 显示剧情
                    st.write(story_text)
                    st.session_state.history.append({"role": "assistant", "content": story_text})
                    
                    # 强制刷新页面，让左侧侧边栏的数据立刻更新！
                    st.rerun()
                    
                else:
                    # 如果 AI 忘了加暗号（偶尔发生），就只显示剧情
                    st.write(raw_reply)
                    st.session_state.history.append({"role": "assistant", "content": raw_reply})
                    
            except Exception as e:
                st.error(f"游戏引擎故障: {e}")
