import streamlit as st
import re
from openai import OpenAI

# --- 1. 基础配置 ---
st.set_page_config(page_title="无限末日：省钱黄金版", page_icon="💰", layout="wide")

try:
    # 客户端 A：DeepSeek (负责写故事，走 DeepSeek 余额)
    client_story = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"], 
        base_url=st.secrets["DEEPSEEK_BASE_URL"]
    )
    
    # 客户端 B：AIHubMix (负责画图，走 AIHubMix 余额)
    client_image = OpenAI(
        api_key=st.secrets["AIHUBMIX_API_KEY"], 
        base_url=st.secrets["AIHUBMIX_BASE_URL"]
    )
except Exception as e:
    st.error(f"请检查 secrets.toml 配置，你需要同时填入 DeepSeek 和 AIHubMix 的 Key。错误: {e}")
    st.stop()

# --- 2. 初始化游戏状态 (不变) ---
if "hp" not in st.session_state:
    st.session_state.hp = 100
if "inventory" not in st.session_state:
    st.session_state.inventory = ["破旧的衣服", "一瓶水"]
if "history" not in st.session_state:
    st.session_state.history = []

# --- 3. 侧边栏 (不变) ---
with st.sidebar:
    st.title("🧟 幸存者状态")
    st.metric("生命值 (HP)", f"{st.session_state.hp}/100")
    st.progress(st.session_state.hp / 100)
    st.write("🎒 **背包物品:**")
    for item in st.session_state.inventory:
        st.info(item)
    if st.button("☠️ 重开一局"):
        st.session_state.hp = 100
        st.session_state.inventory = ["破旧的衣服", "一瓶水"]
        st.session_state.history = []
        st.rerun()

# --- 4. 定义游戏引擎 (System Prompt) ---
# 注意：这里我们依然用 DeepSeek，它完全能理解画图指令
SYSTEM_PROMPT = f"""
你是一个文字冒险游戏的上帝（DM）。背景是【丧尸末日】。
玩家是一个幸存者。

【当前状态】：
- 玩家血量：{st.session_state.hp}
- 玩家背包：{','.join(st.session_state.inventory)}

【回复规则】：
1. 描写剧情，然后给出 2-3 个选项。
2. **状态更新**：使用 `|||` 分隔。格式：`剧情... ||| 血量 ||| 背包`
3. **图片生成**：在关键场景，使用 `[IMAGE_PROMPT: 图片描述]`。
   - 图片描述要英文或中文皆可，要具体。
   - **不要每次回复都生成图片！** 只有到达新地点或打BOSS时才生成，帮玩家省钱。
"""

# --- 辅助函数：用 AIHubMix 画图 ---
def generate_image(prompt):
    try:
        st.toast(f"正在调用 DALL-E 3 绘制: {prompt}") # 弹个小窗提示
        with st.spinner("AI 画师正在铺纸研墨..."):
            # 注意：这里使用的是 client_image (AIHubMix)
            response = client_image.images.generate(
                model="dall-e-3",
                prompt=prompt + ", dystopian zombie apocalypse style, highly detailed",
                size="1024x1024",
                quality="standard",
                n=1,
            )
            return response.data[0].url
    except Exception as e:
        st.error(f"画图失败 (可能是余额不足): {e}")
        return None

# --- 5. 主逻辑 ---
st.title("🧟 无限末日 (DeepSeek剧情 + DALL-E画图)")

for item in st.session_state.history:
    if item["role"] == "user":
        with st.chat_message("user"):
            st.write(item["content"])
    elif item["role"] == "assistant":
        with st.chat_message("assistant"):
            st.write(item["content"])
            if item.get("image_url"):
                st.image(item["image_url"], caption="场景渲染", use_column_width=True)

if st.session_state.hp <= 0:
    st.error("💀 你死了。")
    st.stop()

if user_input := st.chat_input("你的行动..."):
    st.session_state.history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("DeepSeek 正在构思剧情..."):
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *[{"role": m["role"], "content": m["content"]} for m in st.session_state.history[-4:] if "content" in m]
            ]
            
            try:
                # 注意：这里使用的是 client_story (DeepSeek)
                # DeepSeek V3 写故事非常便宜又好用
                response = client_story.chat.completions.create(
                    model="deepseek-chat", 
                    messages=messages,
                    temperature=1.3,
                )
                raw_reply = response.choices[0].message.content
                
                story_text = raw_reply
                image_url = None
                
                # 1. 提取图片暗号
                image_match = re.search(r'\[IMAGE_PROMPT:\s*(.*?)]', story_text)
                if image_match:
                    image_prompt = image_match.group(1).strip()
                    story_text = story_text.replace(image_match.group(0), "").strip()
                    # 调用画图函数
                    image_url = generate_image(image_prompt)

                # 2. 提取状态暗号
                if "|||" in story_text:
                    parts = story_text.split("|||")
                    story_text = parts[0].strip()
                    try: st.session_state.hp = int(parts[1].strip())
                    except: pass
                    try: st.session_state.inventory = [i.strip() for i in parts[2].split(",") if i.strip()]
                    except: pass
                
                st.write(story_text)
                entry = {"role": "assistant", "content": story_text}
                if image_url:
                    st.image(image_url)
                    entry["image_url"] = image_url
                
                st.session_state.history.append(entry)
                st.rerun()
                
            except Exception as e:
                st.error(f"DeepSeek 出错: {e}")
