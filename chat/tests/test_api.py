"""Tests for the chat API — aligned with InterX API spec."""
from __future__ import annotations

import base64
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chat.api import app, _get_settings

AUTH_HEADERS = {"Authorization": "Bearer sk_test_token"}


@pytest.fixture(autouse=True)
def _use_temp_sessions(tmp_path):
    from chat.config import ChatSettings, MemoryConfig, QueryRewriteConfig, LLMEndpoint
    settings = ChatSettings(
        root=Path("."), config_path=Path("."),
        llm=LLMEndpoint(env_file=Path(".env"), api_key_env="X", base_url_env="X", model_name="m"),
        memory=MemoryConfig(strategy="sliding_window", window_size=5, max_summary_tokens=500,
                            summary_trigger_turns=10, temperature=0.3, timeout_seconds=30, max_retries=1),
        query_rewrite=QueryRewriteConfig(enabled=False, temperature=0.1, max_tokens=256,
                                         timeout_seconds=30, max_retries=1),
        session_dir=tmp_path,
    )
    import chat.api as api_mod
    api_mod._settings = settings
    yield
    api_mod._settings = None


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_auth_required():
    """无 token 应返回 401."""
    resp = client.post("/chat", json={"question": "hello"})
    assert resp.status_code == 401


def test_question_required():
    """缺少 question 应返回 422."""
    resp = client.post("/chat", json={}, headers=AUTH_HEADERS)
    assert resp.status_code == 422


def test_question_empty():
    """空 question 应返回 422."""
    resp = client.post("/chat", json={"question": ""}, headers=AUTH_HEADERS)
    assert resp.status_code == 422


def test_list_sessions_empty():
    resp = client.get("/sessions/testuser", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"]["sessions"] == []


def test_get_session_not_found():
    resp = client.get("/sessions/testuser/nonexistent", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_chat_endpoint_mocked():
    """标准响应格式 {code, msg, data: {answer, session_id, timestamp}}."""
    mock_result = type("R", (), {
        "session_id": "s1",
        "user_message": "hello",
        "assistant_message": "hi there",
        "rewritten_query": "hello",
        "turn_id": "t1",
        "history_turns_used": 0,
        "summary_used": False,
        "image_ids": [],
    })()

    with patch("chat.api.chat_fn", return_value=mock_result):
        resp = client.post("/chat", json={"question": "hello"}, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["msg"] == "success"
    assert data["data"]["answer"] == "hi there"
    assert data["data"]["session_id"] == "s1"
    assert isinstance(data["data"]["timestamp"], int)


def test_chat_with_images_mocked():
    """带图片的多模态调用."""
    # 合法的 data URL
    img_b64 = "data:image/png;base64," + base64.b64encode(b"\x89PNG" + b"\x00" * 50).decode()

    mock_result = type("R", (), {
        "session_id": "s2",
        "user_message": "what is this?",
        "assistant_message": "It's a product image.",
        "rewritten_query": "what is this?",
        "turn_id": "t1",
        "history_turns_used": 0,
        "summary_used": False,
        "image_ids": ["img_001"],
    })()

    with patch("chat.api.chat_fn", return_value=mock_result):
        resp = client.post("/chat", json={
            "question": "what is this?",
            "images": [img_b64],
        }, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"]["answer"] == "It's a product image."


def test_image_bad_format():
    """图片格式错误应返回 400."""
    resp = client.post("/chat", json={
        "question": "test",
        "images": ["not_a_valid_image"],
    }, headers=AUTH_HEADERS)
    assert resp.status_code == 400
    assert "格式错误" in resp.json()["detail"]


def test_images_max_count():
    """超过 3 张图片应返回 422."""
    img = "data:image/png;base64," + base64.b64encode(b"\x89PNG\x00").decode()
    resp = client.post("/chat", json={
        "question": "test",
        "images": [img] * 4,
    }, headers=AUTH_HEADERS)
    assert resp.status_code == 422
