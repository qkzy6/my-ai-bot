import streamlit as st
import re
from openai import OpenAI

# --- 1. 基础配置 ---
st.set_page_config(page_title="无限末日：可调图片尺寸", page_icon="🖼️", layout="wide")

# 获取 API Key
try:
    # Client A: DeepSeek (负责写剧情)
    client_story = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"], 
        base_url=st.secrets["DEEPSEEK_BASE_URL"]  # <---这里修正了！
    )
    # Client B: AIHubMix (负责画图)
    client_image = OpenAI(
        api_key=st.secrets["AIHUBMIX_API_KEY"], 
        base_url=st.secrets["AIHUBMIX_BASE_URL"]
    )
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
# 初始化图片宽度设置
if "image_width" not in st.session_state:
    st.session_state.image_width = 500 # 默认设小一点，500px比较合适

# --- 3. 侧边栏 (新增图片宽度滑块) ---
with st.sidebar:
    st.title("🧟 幸存者面板")
    
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
    # 图片尺寸调节滑块
    st.session_state.image_width = st.slider(
        "图片显示宽度 (px)",
        min_value=200,
        max_value=1000,
        value=st.session_state.image_width,
        step=50
    )
    
    st.divider()
    if st.button("🔄 重置游戏"):
        st.session_state.hp = 100
        st.session_state.inventory = ["破旧的衣服", "半瓶水"]
        st.session_state.history = [] 
        st.rerun()

# --- 4. 游戏引擎 Prompt (不变) ---
SYSTEM_PROMPT = f"""
你是一个【丧尸末日文字冒险游戏】的上帝（DM）。
玩家是一个刚刚苏醒的幸存者。

【当前玩家状态】：
- 血量：{st.session_state.hp}
- 背包：{','.join(st.session_state.inventory)}

【回复格式规范 (严格遵守)】：
1. **第一段：环境与剧情**
   详细描写当前发生了什么，环境怎么样（光线、声音、气味）。
   
2. **第二段：行动选项 (必须紧接在剧情后面)**
   请另起一行，用加粗字体写：**【你会怎么做？】**
   然后列出 3 个具体的选项，使用数字列表（1. 2. 3.）。
   （注意：选项必须包含在对话内容里，不要放在别的地方！）

3. **第三段：暗号区域 (用户不可见，用于程序处理)**
   - 状态更新：`||| 血量数值 ||| 物品1,物品2`
   - 图片生成：`[IMAGE_PROMPT: 具体的画面描述]` (只在场景大变时生成)

【示例回复】：
你推开沉重的铁门，发现外面是一条荒废的街道。几辆报废的汽车还在冒烟，远处传来嘶吼声。你感觉非常口渴。

**【你会怎么做？】**
1. 搜查旁边的废弃便利店。
2. 躲进路边的汽车里休息。
3. 沿着街道快速奔跑。

[IMAGE_PROMPT: 荒废的城市街道，天空昏黄，废弃车辆，远处有丧尸影子]
||| 95 ||| 破旧的衣服,半瓶水
"""

# --- 5. 辅助函数 ---

def generate_dalle_image(prompt):
    """调用 DALL-E 3 画图"""
    try:
        with st.spinner("🎨 正在渲染场景图片..."):
            response = client_image.images.generate(
                model="dall-e-3",
                prompt=prompt + ", apocalyptic style, cinematic lighting, 4k",
                size="1024x1024", 
                quality="standard",
                n=1,
            )
            return response.data[0].url
    except Exception as e:
        st.warning(f"图片生成失败: {e}")
        return None

def process_ai_response(messages):
    """处理 AI 回复"""
    try:
        response = client_story.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=1.3, 
        )
        raw_reply = response.choices[0].message.content
        
        story_text = raw_reply
        image_url = None

        # 1. 解析图片暗号
        img_match = re.search(r'\[IMAGE_PROMPT:\s*(.*?)]', story_text)
        if img_match:
            prompt = img_match.group(1)
            story_text = story_text.replace(img_match.group(0), "").strip()
            image_url = generate_dalle_image(prompt)
        
        # 2. 解析状态暗号
        if "|||" in story_text:
            parts = story_text.split("|||")
            story_text = parts[0].strip()
            try:
                st.session_state.hp = int(parts[1].strip())
                new_inv = parts[2].strip()
                st.session_state.inventory = [i.strip() for i in new_inv.split(",") if i.strip()]
            except: pass
            
        return story_text, image_url
    except Exception as e:
        st.error(f"API Error: {e}")
        return None, None

# --- 6. 自动开场逻辑 ---
if len(st.session_state.history) == 0:
    with st.spinner("正在生成随机开场..."):
        opening_msg = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "游戏开始。请生成一个高危的出生点，并给出第一轮选项。"}
        ]
        text, img = process_ai_response(opening_msg)
        if text:
            entry = {"role": "assistant", "content": text}
            if img: entry["image_url"] = img
            st.session_state.history.append(entry)
            st.rerun()

# --- 7. 界面渲染 ---
st.title("🎬 无限末日：求生之路")

# 渲染历史消息
for msg in st.session_state.history:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.write(msg["content"]) 
            if "image_url" in msg:
                st.image(msg["image_url"], caption="当前场景", width=st.session_state.image_width)

# 死亡判定
if st.session_state.hp <= 0:
    st.error("💀 你的视线逐渐变黑... 游戏结束。")
    if st.button("☠️ 投胎重开"):
        st.session_state.hp = 100
        st.session_state.history = []
        st.rerun()
    st.stop()

# 玩家输入
if user_input := st.chat_input("输入你的选择（如：1 / 搜刮便利店）..."):
    # 显示玩家输入
    st.session_state.history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
    
    # 生成 AI 回复
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
