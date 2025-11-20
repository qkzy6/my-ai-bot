import streamlit as st
import re
import json
import pymongo
import certifi
from openai import OpenAI

# --- 1. 基础配置 ---
st.set_page_config(page_title="无限修仙模拟器", page_icon="🏮", layout="wide")

# 读取世界观文件
def load_world_setting():
    try:
        with open("world.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "（未找到 world.txt，请在同级目录创建该文件。）"

WORLD_SETTING = load_world_setting()

# 获取 API 和 数据库
try:
    # Client A: DeepSeek (剧情)
    client_story = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"], 
        base_url=st.secrets["DEEPSEEK_BASE_URL"]
    )
    # Client B: AIHubMix (画图)
    client_image = OpenAI(
        api_key=st.secrets["AIHUBMIX_API_KEY"], 
        base_url=st.secrets["AIHUBMIX_BASE_URL"]
    )
    
    # Client C: MongoDB (云存档 - 终极防报错连接)
    @st.cache_resource
    def init_connection():
        return pymongo.MongoClient(
            st.secrets["MONGO_URI"],
            tls=True,
            tlsAllowInvalidCertificates=True # 跳过证书验证
        )
    
    mongo_client = init_connection()
    db = mongo_client.xiuxian_game 
    saves_collection = db.player_saves 

except Exception as e:
    st.error(f"配置错误: {e}")
    st.stop()

# --- 2. 初始化状态 ---
if "cultivation" not in st.session_state:
    st.session_state.cultivation = "练气期 一层" # 境界
if "spirit" not in st.session_state: 
    st.session_state.spirit = 100 # 灵力/气血
if "inventory" not in st.session_state:
    st.session_state.inventory = ["残破的铁剑", "低阶储物袋", "下品灵石x5"]
if "history" not in st.session_state:
    st.session_state.history = []
if "image_width" not in st.session_state:
    st.session_state.image_width = 500
if "objective" not in st.session_state:
    st.session_state.objective = "感应天地灵气，踏入仙途"
if "image_error" not in st.session_state:
    st.session_state.image_error = None
if "username" not in st.session_state:
    st.session_state.username = "道友"

# --- 3. 云存档系统 ---
def save_game_cloud():
    user = st.session_state.username
    if not user or user == "道友": st.error("❌ 请先输入独一无二的道号！"); return
    data = {
        "username": user,
        "cultivation": st.session_state.cultivation,
        "spirit": st.session_state.spirit,
        "inventory": st.session_state.inventory,
        "history": st.session_state.history,
        "objective": st.session_state.objective
    }
    try:
        saves_collection.update_one({"username": user}, {"$set": data}, upsert=True)
        st.toast(f"☁️ 道果已寄托虚空！(存档成功)")
    except Exception as e: st.error(f"存失败: {e}")

def load_game_cloud():
    user = st.session_state.username
    if not user or user == "道友": st.error("❌ 请先输入道号！"); return
    try:
        data = saves_collection.find_one({"username": user})
        if data:
            st.session_state.cultivation = data.get("cultivation", "练气期 一层")
            st.session_state.spirit = data["spirit"]
            st.session_state.inventory = data["inventory"]
            st.session_state.history = data["history"]
            st.session_state.objective = data.get("objective", "问道")
            st.toast(f"☁️ 重塑肉身成功！")
            st.rerun()
        else: st.error(f"❌ 未找到道友 [{user}] 的前世记忆。")
    except Exception as e: st.error(f"读失败: {e}")

# --- 4. 侧边栏 UI ---
with st.sidebar:
    st.title("🏮 修仙面板")
    
    # 顶部任务提示
    st.caption("当前机缘/目标：")
    st.warning(f"📜 **{st.session_state.objective}**")
    
    st.divider()

    # 图片服务报错提示
    if st.session_state.image_error:
        st.error(f"⚠️ {st.session_state.image_error}")
        st.caption("画圣暂离，仅显示文字剧情。")
        st.divider()

    # 境界显示
    st.info(f"🧘 **境界：{st.session_state.cultivation}**")
    
    # 灵力条
    col1, col2 = st.columns([1, 3])
    with col1: st.write("🔵") 
    with col2: st.progress(min(st.session_state.spirit / 100, 1.0))
    st.caption(f"灵力/气血: {st.session_state.spirit}/100")
    
    st.divider()
    st.write("🎒 **储物袋:**")
    for item in st.session_state.inventory:
        st.code(item, language=None)
    
    st.divider()
    st.subheader("☁️ 道果同步")
    st.session_state.username = st.text_input("道号 (ID)", value=st.session_state.username)
    c1, c2 = st.columns(2)
    with c1: 
        if st.button("⬆️ 寄托"): save_game_cloud()
    with c2: 
        if st.button("⬇️ 重修"): load_game_cloud()

    st.divider()
    st.session_state.image_width = st.slider("画卷宽度", 200, 1000, st.session_state.image_width, 50)
    if st.button("🔄 转世重修 (删档)"):
        st.session_state.cultivation = "练气期 一层"
        st.session_state.spirit = 100
        st.session_state.inventory = ["残破的铁剑", "低阶储物袋"]
        st.session_state.history = []
        st.session_state.objective = "感应天地灵气"
        st.session_state.image_error = None
        st.rerun()

# --- 5. 修仙引擎 Prompt (注入仇恨连锁逻辑) ---
SYSTEM_PROMPT = f"""
你是一个【硬核修仙文字冒险游戏】的天道（DM）。
你需要结合以下小说世界观设定，来生成剧情：
>>> 世界观设定开始
{WORLD_SETTING}
>>> 世界观设定结束

【当前主角状态】：
- 境界：{st.session_state.cultivation}
- 气血/灵力：{st.session_state.spirit}
- 储物袋：{','.join(st.session_state.inventory)}
- 当前机缘/目标：{st.session_state.objective}

【剧情推进规则 (严格执行)】：
1. **深度文笔**：模仿《凡人修仙传》文笔。剧情包含杀人夺宝、黑吃黑、秘境探险。
2. **仇恨连锁 (关键)**：
   - 经常安排有背景的“小反派”（如纨绔子弟）挑衅。
   - **如果玩家杀死了小反派**：必须在剧情中描述“一道血光印记飞入你体内”或“传音符飞走”。
   - **伏笔回收**：在后续几轮中，必须安排他的长辈（高境界老怪）追杀过来！
3. **残酷修仙**：不要让玩家太顺，选择错误直接重伤（扣灵力）。
4. **境界压制**：严格遵守境界差距。

【回复格式规范】：
1. **第一段：剧情描述** (环境+事件+危机)
2. **第二段：【道友请抉择】** (3个选项，包含激进、稳健、阴险等流派)
3. **第三段：暗号区域**
   `||| 灵力数值(0-100) ||| 物品列表 ||| 新的机缘目标 ||| 新的境界(可选)`
   `[IMAGE_PROMPT: 中国水墨仙侠风格(Chinese ink painting style, Xianxia, wuxia), 具体的画面描述]`

【例子】：
你一剑斩下那少年的头颅，正欲搜尸，却见一道猩红血光从尸体中冲出，瞬间没入你的眉心，根本无法躲避！
“竖子敢尔！杀我孙儿，老夫必将你抽魂炼魄！”一道苍老的怒吼声仿佛穿透虚空而来。你感到一股元婴期的恐怖威压正在快速逼近！

**【道友请抉择】**
1. 施展“血影遁”，燃烧精血向反方向疯狂逃窜。
2. 赌一把，躲入旁边的上古传送阵，不管传送到哪里。
3. 原地布置“颠倒五行阵”，试图拖延时间（九死一生）。

[IMAGE_PROMPT: 荒野之上，少年尸首分离，一道血色骷髅印记飞向主角眉心，天空乌云密布]
||| 50 ||| 储物袋,血色印记 ||| 逃避元婴老怪的追杀
"""

# --- 6. 辅助函数 ---
def generate_dalle_image(prompt):
    try:
        with st.spinner("🎨 画圣正在挥毫泼墨..."):
            response = client_image.images.generate(
                model="dall-e-3",
                prompt=prompt + ", ancient chinese fantasy art, ink wash painting, ethereal, detailed",
                size="1024x1024", quality="standard", n=1,
            )
            # 如果成功，清除报错状态
            if st.session_state.image_error: st.session_state.image_error = None; st.rerun()
            return response.data[0].url
    except Exception as e:
        error_msg = str(e)
        if "402" in error_msg or "billing" in error_msg.lower():
            st.session_state.image_error = "图片生成余额不足，已转为文字模式。"
        else:
            st.session_state.image_error = "画圣暂时闭关(API不可用)。"
        return None

def process_ai_response(messages):
    try:
        response = client_story.chat.completions.create(
            model="deepseek-chat", messages=messages, temperature=1.3, 
        )
        story_text = response.choices[0].message.content
        image_url = None

        # 1. 解析图片
        img_match = re.search(r'\[IMAGE_PROMPT:\s*(.*?)]', story_text)
        if img_match:
            prompt = img_match.group(1)
            story_text = story_text.replace(img_match.group(0), "").strip()
            image_url = generate_dalle_image(prompt)
        
        # 2. 解析暗号状态
        if "|||" in story_text:
            parts = story_text.split("|||")
            story_text = parts[0].strip()
            try:
                st.session_state.spirit = int(parts[1].strip())
                st.session_state.inventory = [i.strip() for i in parts[2].strip().split(",") if i.strip()]
                if len(parts) > 3:
                    new_obj = parts[3].strip()
                    if new_obj and new_obj != st.session_state.objective:
                        st.session_state.objective = new_obj
                        st.toast(f"📜 机缘更新：{new_obj}")
                # 解析境界突破
                if len(parts) > 4:
                    new_realm = parts[4].strip()
                    if new_realm and new_realm != st.session_state.cultivation:
                        st.session_state.cultivation = new_realm
                        st.balloons() 
                        st.toast(f"🧘 境界突破！当前：{new_realm}")
            except: pass
            
        return story_text, image_url
    except Exception as e:
        st.error(f"天道崩塌 (API Error): {e}"); return None, None

# --- 7. 自动开场 ---
if len(st.session_state.history) == 0:
    with st.spinner("正在演化一方小世界..."):
        opening_msg = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "开启修仙之路。结合设定的世界观，生成一个低微出身（如七玄门杂役），并遭遇第一个小反派的挑衅。"}
        ]
        text, img = process_ai_response(opening_msg)
        if text:
            entry = {"role": "assistant", "content": text}
            if img: entry["image_url"] = img
            st.session_state.history.append(entry)
            st.rerun()

# --- 8. 界面渲染 ---
st.title("🏮 无限修仙模拟器")
# 渲染历史
for msg in st.session_state.history:
    role = msg["role"]
    with st.chat_message(role, avatar="🧘" if role=="user" else "☁️"):
        st.write(msg["content"])
        if msg.get("image_url"): st.image(msg["image_url"], width=st.session_state.image_width)

if st.session_state.spirit <= 0:
    st.error("💀 你的肉身已毁，兵解重修吧...")
    if st.button("☠️ 投胎转世"):
        st.session_state.spirit = 100
        st.session_state.history = []; st.rerun()
    st.stop()

if user_input := st.chat_input("道友请抉择..."):
    st.session_state.history.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧘"): st.write(user_input)
    
    with st.chat_message("assistant", avatar="☁️"):
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
