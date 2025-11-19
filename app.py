import streamlit as st
import re
import json 
from openai import OpenAI
import pymongo 
import certifi

# --- 1. 基础配置 ---
st.set_page_config(page_title="无限末日：云存档版", page_icon="☁️", layout="wide")

# 获取 API Key 和 数据库连接串
try:
    client_story = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"], 
        base_url=st.secrets["DEEPSEEK_BASE_URL"]
    )
    client_image = OpenAI(
        api_key=st.secrets["AIHUBMIX_API_KEY"], 
        base_url=st.secrets["AIHUBMIX_BASE_URL"]
    )
    
    # ✨ 连接 MongoDB (终极防报错版)
    @st.cache_resource
    def init_connection():
        return pymongo.MongoClient(
            st.secrets["MONGO_URI"],
            tls=True,
            tlsAllowInvalidCertificates=True 
        )
    
    mongo_client = init_connection()
    db = mongo_client.zombie_game 
    saves_collection = db.player_saves 

except Exception as e:
    st.error(f"配置错误: {e}")
    st.stop()

# --- 2. 初始化状态 ---
if "hp" not in st.session_state:
    st.session_state.hp = 100
if "inventory" not in st.session_state:
    st.session_state.inventory = ["破旧的衣服", "半瓶水"]
if "history" not in st.session_state:
    st.session_state.history = []
if "image_width" not in st.session_state:
    st.session_state.image_width = 500
if "objective" not in st.session_state:
    st.session_state.objective = "寻找线索"
if "image_error" not in st.session_state:
    st.session_state.image_error = None
if "username" not in st.session_state:
    st.session_state.username = "Player1"

# --- 3. 云存档/读档系统 ---

def save_game_cloud():
    user = st.session_state.username
    if not user:
        st.error("❌ 请先输入用户名！")
        return

    data = {
        "username": user,
        "hp": st.session_state.hp,
        "inventory": st.session_state.inventory,
        "history": st.session_state.history,
        "objective": st.session_state.objective
    }
    
    try:
        saves_collection.update_one(
            {"username": user}, 
            {"$set": data},     
            upsert=True         
        )
        st.toast(f"☁️ 成功保存到云端！(用户: {user})")
    except Exception as e:
        st.error(f"云端保存失败: {e}")

def load_game_cloud():
    user = st.session_state.username
    if not user:
        st.error("❌ 请先输入用户名！")
        return

    try:
        data = saves_collection.find_one({"username": user})
        
        if data:
            st.session_state.hp = data["hp"]
            st.session_state.inventory = data["inventory"]
            st.session_state.history = data["history"]
            st.session_state.objective = data.get("objective", "存活")
            st.toast(f"☁️ 云存档读取成功！欢迎回来，{user}")
            st.rerun()
        else:
            st.error(f"❌ 云端找不到用户 [{user}] 的存档。")
    except Exception as e:
        st.error(f"读取失败: {e}")

# --- 4. 侧边栏 UI (界面调整核心区域) ---
with st.sidebar:
    st.title("🧟 幸存者面板")
    
    # ✨✨✨ 修改点：把任务目标移到最上方 ✨✨✨
    st.caption("当前任务目标：")
    st.warning(f"🚩 **{st.session_state.objective}**")
    st.divider()
    # ✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨

    # 报错提示
    if st.session_state.image_error:
        st.error(f"⚠️ {st.session_state.image_error}")
        st.divider()

    # 状态显示
    col1, col2 = st.columns([1, 3])
    with col1: st.write("❤️")
    with col2: st.progress(min(st.session_state.hp / 100, 1.0))
    st.caption(f"生命值: {st.session_state.hp}/100")
    
    st.divider()
    st.write("🎒 **背包物品:**")
    if not st.session_state.inventory:
        st.caption("空空如也...")
    for item in st.session_state.inventory:
        st.info(item)
    
    st.divider()
    
    # 云存档区域
    st.subheader("☁️ 云端同步")
    st.session_state.username = st.text_input("你的ID (区分大小写)", value=st.session_state.username)
    
    col_save, col_load = st.columns(2)
    with col_save:
        if st.button("⬆️ 上传存档"): save_game_cloud()
    with col_load:
        if st.button("⬇️ 下载存档"): load_game_cloud()

    st.divider()
    st.session_state.image_width = st.slider("图片宽度", 200, 1000, st.session_state.image_width, 50)
    
    if st.button("🔄 重置游戏"):
        st.session_state.hp = 100
        st.session_state.inventory = ["破旧的衣服", "半瓶水"]
        st.session_state.history = []
        st.session_state.objective = "寻找线索"
        st.session_state.image_error = None
        st.rerun()

# --- 5. 游戏引擎 Prompt ---
SYSTEM_PROMPT = f"""
你是一个【快节奏丧尸末日文字冒险游戏】的上帝（DM）。
玩家是一个幸存者。

【当前数据】：
- 血量：{st.session_state.hp}
- 背包：{','.join(st.session_state.inventory)}
- 任务：{st.session_state.objective}

【回复规则】：
1. **剧情推进**：拒绝拖沓，立即结算玩家动作后果。
2. **任务系统**：关注任务目标，完成后立刻更新新任务。
3. **格式规范**：
   - 第一段：剧情 (结果 + 新危机)
   - 第二段：**【你会怎么做？】** (3个选项)
   - 第三段：暗号区域

【暗号区域格式】：
`||| 血量 ||| 物品列表 ||| 新的任务目标`
`[IMAGE_PROMPT: 图片描述]`

【例子】：
炸弹轰然爆炸，铁门飞了出去！你冲出烟雾，终于呼吸到了外面的空气。但你发现医院外是是更加危险的市中心广场，四周全是游荡的尸潮。你看到广场中央有一辆完好的警车。

**【你会怎么做？】**
1. 潜行穿过尸潮去抢警车。
2. 爬上旁边的雕像暂避锋芒。
3. 寻找下水道入口。

[IMAGE_PROMPT: 破败的市中心广场，密密麻麻的丧尸，远处有一辆警车]
||| 90 ||| 枪,绷带 ||| 到达警车并逃离市中心
"""

# --- 6. 辅助函数 ---
def generate_dalle_image(prompt):
    try:
        with st.spinner("🎨 正在尝试绘制场景..."):
            response = client_image.images.generate(
                model="dall-e-3",
                prompt=prompt + ", apocalyptic style, cinematic lighting, 4k",
                size="1024x1024", 
                quality="standard", 
                n=1,
            )
            if st.session_state.image_error is not None:
                st.session_state.image_error = None
                st.rerun()
            return response.data[0].url
    except Exception as e:
        error_msg = str(e)
        if "402" in error_msg or "billing" in error_msg.lower():
            st.session_state.image_error = "图片生成余额不足，已转为文字模式。"
        else:
            st.session_state.image_error = f"图片生成不可用。"
        return None

def process_ai_response(messages):
    try:
        response = client_story.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=1.3, 
        )
        raw_reply = response.choices[0].message.content
        story_text = raw_reply
        image_url = None

        img_match = re.search(r'\[IMAGE_PROMPT:\s*(.*?)]', story_text)
        if img_match:
            prompt = img_match.group(1)
            story_text = story_text.replace(img_match.group(0), "").strip()
            image_url = generate_dalle_image(prompt)
        
        if "|||" in story_text:
            parts = story_text.split("|||")
            story_text = parts[0].strip()
            try:
                st.session_state.hp = int(parts[1].strip())
                st.session_state.inventory = [i.strip() for i in parts[2].strip().split(",") if i.strip()]
                if len(parts) > 3:
                    new_obj = parts[3].strip()
                    if new_obj and new_obj != st.session_state.objective:
                        st.session_state.objective = new_obj
                        st.toast(f"🚩 任务更新：{new_obj}")
            except: pass
            
        return story_text, image_url
    except Exception as e:
        st.error(f"DeepSeek Error: {e}")
        return None, None

# --- 7. 自动开场 ---
if len(st.session_state.history) == 0:
    with st.spinner("正在初始化世界..."):
        opening_msg = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "游戏开始。生成随机高危出生点，设定初始任务。"}
        ]
        text, img = process_ai_response(opening_msg)
        if text:
            entry = {"role": "assistant", "content": text}
            if img: entry["image_url"] = img
            st.session_state.history.append(entry)
            st.rerun()

# --- 8. 界面渲染 ---
st.title("☁️ 无限末日：云存档版")
# ❌ 删除了这里原来的 st.info(当前目标)

for msg in st.session_state.history:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.write(msg["content"]) 
            if "image_url" in msg and msg["image_url"]:
                st.image(msg["image_url"], caption="当前场景", width=st.session_state.image_width)

if st.session_state.hp <= 0:
    st.error("💀 你的视线逐渐变黑... 游戏结束。")
    if st.button("☠️ 投胎重开"):
        st.session_state.hp = 100
        st.session_state.history = []
        st.session_state.image_error = None
        st.rerun()
    st.stop()

if user_input := st.chat_input("输入你的选择..."):
    st.session_state.history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
    
    with st.chat_message("assistant"):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in st.session_state.history[-6:]:
            messages.append({"role": m["role"], "content": m["content"]})
            
        text, img = process_ai_response(messages)
        
        if text:
            st.write(text)
            entry = {"role": "assistant", "content": text}
            if img:
                st.image(img, width=st.session_state.image_width)
                entry["image_url"] = img
            
            st.session_state.history.append(entry)
            st.rerun()
