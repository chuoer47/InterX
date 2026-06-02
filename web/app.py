from __future__ import annotations

import base64
import os
from typing import Any

import requests
import streamlit as st

API_BASE = os.getenv("INTERX_CHAT_API_BASE", "http://127.0.0.1:8000")
API_TOKEN = os.getenv("INTERX_CHAT_API_TOKEN", "sk_local_dev")

st.set_page_config(page_title="InterX 智能客服", page_icon="🤖", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "user_id" not in st.session_state:
    st.session_state.user_id = "default"
if "messages" not in st.session_state:
    st.session_state.messages = []


def _api_headers() -> dict[str, str]:
    """Build API headers once so UI calls stay consistent."""
    return {"Authorization": f"Bearer {API_TOKEN}"}


def render_answer(answer: str, image_ids: list[str] | None = None) -> None:
    """
    Render an answer containing `<PIC>` placeholders.

    The backend returns text plus image ids separately, so the UI stitches them back
    together by walking placeholder positions in order.
    """
    image_ids = image_ids or []
    parts = answer.split("<PIC>")
    for idx, part in enumerate(parts):
        if part.strip():
            st.markdown(part)
        if idx < len(parts) - 1:
            img_id = image_ids[idx] if idx < len(image_ids) else None
            if not img_id:
                st.caption("[Missing image]")
                continue
            try:
                resp = requests.get(f"{API_BASE}/images/{img_id}", headers=_api_headers(), timeout=10)
                if resp.ok:
                    st.image(resp.content, caption=img_id, width=400)
                else:
                    st.caption(f"[图片: {img_id}]")
            except Exception:
                st.caption(f"[图片: {img_id}]")


with st.sidebar:
    st.title("🤖 InterX 智能客服")
    st.caption("基于产品手册的多轮对话系统")

    st.divider()
    st.text_input(
        "用户 ID",
        value=st.session_state.user_id,
        key="user_id_input",
        on_change=lambda: setattr(st.session_state, "user_id", st.session_state.user_id_input),
    )

    if st.button("🆕 新对话"):
        st.session_state.session_id = None
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.subheader("历史会话")
    try:
        resp = requests.get(
            f"{API_BASE}/sessions/{st.session_state.user_id}",
            headers=_api_headers(),
            timeout=5,
        )
        if resp.ok:
            for sid in resp.json().get("data", {}).get("sessions", []):
                if st.button(f"💬 {sid}", key=f"load_{sid}"):
                    st.session_state.session_id = sid
                    detail = requests.get(
                        f"{API_BASE}/sessions/{st.session_state.user_id}/{sid}",
                        headers=_api_headers(),
                        timeout=5,
                    ).json()
                    st.session_state.messages = []
                    for t in detail.get("data", {}).get("turns", []):
                        st.session_state.messages.append({"role": "user", "content": t["user_message"]})
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": t["assistant_message"],
                            "image_ids": t.get("image_ids", []),
                        })
                    st.rerun()
    except Exception:
        st.caption("API 未连接")

    st.divider()
    st.caption(f"Session: {st.session_state.session_id or '新建中...'}")


st.header("💬 对话")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            render_answer(msg["content"], msg.get("image_ids"))
        else:
            st.markdown(msg["content"])

uploaded_files = st.file_uploader(
    "📷 上传图片（可选，最多3张，每张≤5MB）",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if prompt := st.chat_input("输入你的问题..."):
    with st.chat_message("user"):
        st.markdown(prompt)
        if uploaded_files:
            cols = st.columns(min(len(uploaded_files), 4))
            for i, f in enumerate(uploaded_files):
                with cols[i % 4]:
                    st.image(f, width=120)

    st.session_state.messages.append({"role": "user", "content": prompt})

    images_data_url: list[str] = []
    for f in (uploaded_files or []):
        mime = f.type or "image/png"
        b64 = base64.b64encode(f.read()).decode()
        images_data_url.append(f"data:{mime};base64,{b64}")

    payload = {
        "question": prompt,
        "images": images_data_url,
        "session_id": st.session_state.session_id,
        "user_id": st.session_state.user_id,
    }

    with st.chat_message("assistant"):
        with st.spinner("正在思考..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/chat",
                    json=payload,
                    headers=_api_headers(),
                    timeout=None,
                )
                if resp.ok:
                    body = resp.json()
                    if body.get("code") != 0:
                        st.error(f"API 错误: {body.get('msg')}")
                    else:
                        data = body["data"]
                        render_answer(data["answer"], data.get("image_ids"))
                        st.session_state.session_id = data["session_id"]
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": data["answer"],
                                "image_ids": data.get("image_ids", []),
                            }
                        )
                else:
                    st.error(f"HTTP {resp.status_code}: {resp.text[:200]}")
            except requests.ConnectionError:
                st.error("无法连接 API 服务，请确认 API 已启动")
            except Exception as exc:
                st.error(f"请求失败: {exc}")
