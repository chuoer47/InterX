"""RESTful API for the chat service."""
from __future__ import annotations

import base64
import re
import sys
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

_SRC = str(Path(__file__).resolve().parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from chat.config import ChatSettings
from chat.pipeline import chat as chat_fn, get_session, reset_session
from chat.store import list_sessions

app = FastAPI(title="InterX 智能客服 API", version="1.0.0")
_settings: ChatSettings | None = None


def _get_settings() -> ChatSettings:
    global _settings
    if _settings is None:
        _settings = ChatSettings.load()
    return _settings


class ChatRequest(BaseModel):
    """Request body for `/chat`."""
    question: str = Field(..., min_length=1, description="User question text.")
    images: list[str] = Field(default_factory=list, description="Base64 image data URLs.", max_length=3)
    session_id: str | None = Field(None, description="Existing session id for multi-turn continuation.")
    user_id: str = Field("default", description="User id for session isolation.")
    stream: bool = Field(False, description="Reserved for future streaming support.")


class ChatData(BaseModel):
    """Successful chat response payload."""
    answer: str
    session_id: str
    timestamp: int
    image_ids: list[str] = Field(default_factory=list)


class ChatResponseEnvelope(BaseModel):
    """Standard success envelope."""
    code: int = 0
    msg: str = "success"
    data: ChatData


class ErrorEnvelope(BaseModel):
    """Standard error envelope."""
    code: int
    msg: str
    data: None = None


_DATA_URL_RE = re.compile(r"^data:image/(png|jpe?g|webp);base64,(.+)$", re.DOTALL)


def _verify_token(request: Request) -> str:
    """Require a Bearer token on every request."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header. Expected: Bearer {token}")
    token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")
    return token


def _parse_images(images: list[str]) -> list[str]:
    """
    Validate incoming image data URLs and materialize them as temp files.

    The downstream retrieval and answer layers work with file paths, so the API
    converts base64 uploads into temporary files at the boundary.
    """
    paths: list[str] = []
    for i, raw in enumerate(images):
        match = _DATA_URL_RE.match(raw)
        if not match:
            raise HTTPException(status_code=400, detail=f"images[{i}] 格式错误，需 data:image/{{png/jpg/jpeg/webp}};base64,{{内容}}")
        ext = match.group(1).replace("jpeg", "jpg")
        b64_content = match.group(2)
        img_bytes = base64.b64decode(b64_content)
        if len(img_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"images[{i}] exceeds the 5MB limit")
        tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
        tmp.write(img_bytes)
        tmp.flush()
        tmp.close()
        paths.append(tmp.name)
    return paths


@app.post("/chat", response_model=ChatResponseEnvelope, responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}})
def chat_endpoint(body: ChatRequest, request: Request) -> ChatResponseEnvelope:
    """Main multi-modal chat endpoint."""
    _verify_token(request)
    image_paths = _parse_images(body.images)
    try:
        response = chat_fn(
            body.question,
            session_id=body.session_id,
            user_id=body.user_id,
            images=image_paths,
            settings=_get_settings(),
        )
        return ChatResponseEnvelope(
            data=ChatData(
                answer=response.assistant_message,
                session_id=response.session_id,
                timestamp=int(time.time()),
                image_ids=response.image_ids,
            )
        )
    finally:
        for path in image_paths:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass


@app.get("/images/{image_id}")
def get_image(image_id: str, request: Request) -> FileResponse:
    """Serve one retrieved manual image by image id."""
    _verify_token(request)
    image_dir = _get_settings().root.parent / "process" / "data" / "插图"
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        path = image_dir / f"{image_id}{ext}"
        if path.exists():
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/sessions/{user_id}")
def list_sessions_endpoint(user_id: str, request: Request) -> dict:
    """List session ids for one user."""
    _verify_token(request)
    settings = _get_settings()
    return {"code": 0, "msg": "success", "data": {"sessions": list_sessions(settings.session_dir, user_id=user_id)}}


@app.get("/sessions/{user_id}/{session_id}")
def get_session_endpoint(user_id: str, session_id: str, request: Request) -> dict:
    """Load one persisted session."""
    _verify_token(request)
    session = get_session(session_id, user_id=user_id, settings=_get_settings())
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"code": 0, "msg": "success", "data": session.to_dict()}


@app.post("/sessions/{user_id}/{session_id}/reset")
def reset_session_endpoint(user_id: str, session_id: str, request: Request) -> dict:
    """Reset a session to an empty state."""
    _verify_token(request)
    session = reset_session(session_id, user_id=user_id, settings=_get_settings())
    return {"code": 0, "msg": "success", "data": session.to_dict()}


@app.get("/health")
def health() -> dict:
    """Lightweight health endpoint used by tests and local checks."""
    return {"status": "ok"}
