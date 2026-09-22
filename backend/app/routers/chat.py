import json
import asyncio
from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from ..db import get_session
from ..models import ChatSession
from ...store.retrieval import build_grounded_answer, get_docs_meta, get_all_policies
try:
    from ...store.llm import stream_llm_answer, USE_LLM
except Exception:  # if dependency not installed or import fails
    stream_llm_answer = None  # type: ignore
    USE_LLM = False  # type: ignore

router = APIRouter(prefix="/chat", tags=["chat"])

class SessionCreateIn(BaseModel):
    user_id: str
    session_id: Optional[str] = None

class SessionCreateOut(BaseModel):
    session_id: str
    chat_history: list
    persisted: bool = True

class SessionSummary(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    title: str

@router.post("/session", response_model=SessionCreateOut)
def create_or_get_session(payload: SessionCreateIn):
    """Return existing session if persisted, else issue a new ephemeral session id without persisting.
    A session is only persisted when the first user message arrives over WebSocket."""
    from ..db import get_session as _gs
    import uuid
    with _gs() as session:
        if payload.session_id:
            stmt = select(ChatSession).where(ChatSession.session_id == payload.session_id, ChatSession.user_id == payload.user_id)
            existing = session.exec(stmt).first()
            if existing:
                return SessionCreateOut(session_id=existing.session_id, chat_history=existing.get_history(), persisted=True)
        # create ephemeral id only
        ephemeral_id = str(uuid.uuid4())
        return SessionCreateOut(session_id=ephemeral_id, chat_history=[], persisted=False)

@router.get("/sessions", response_model=List[SessionSummary])
def list_sessions(user_id: str):
    from ..db import get_session as _gs
    with _gs() as session:
        stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
        rows = session.exec(stmt).all()
        summaries = []
        for r in rows:
            history = r.get_history()
            if not history:  # skip empty sessions
                continue
            first_user = next((m for m in history if m.get("role") == "user" and m.get("content")), None)
            title = first_user["content"].strip() if first_user else "New Chat"
            if len(title) > 40:
                title = title[:37] + "..."
            summaries.append(SessionSummary(session_id=r.session_id, created_at=r.created_at.isoformat(), updated_at=r.updated_at.isoformat(), title=title))
        return summaries

@router.get("/session/{session_id}", response_model=SessionCreateOut)
def get_session(session_id: str, user_id: str):
    from ..db import get_session as _gs
    with _gs() as session:
        stmt = select(ChatSession).where(ChatSession.session_id == session_id, ChatSession.user_id == user_id)
        chat = session.exec(stmt).first()
        if not chat:
            raise HTTPException(status_code=404, detail="session_not_found")
        if not chat.get_history():  # treat empty as not persisted for clients
            raise HTTPException(status_code=404, detail="session_not_found")
        return SessionCreateOut(session_id=chat.session_id, chat_history=chat.get_history(), persisted=True)

async def stream_assistant_reply(ws: WebSocket, chat: ChatSession, session_db, grounded_text: str, *, already_appended: bool = False):
    """Legacy deterministic streaming: split grounded_text by words.
    already_appended avoids duplicating assistant message if LLM path created the placeholder."""
    if not already_appended:
        chat.append_message("assistant", "")
        session_db.add(chat)
        session_db.commit()
    for word in grounded_text.split():
        await ws.send_json({"type": "token", "token": f"{word} "})
        await asyncio.sleep(0.05)
    history = chat.get_history()
    for msg in reversed(history):
        if msg["role"] == "assistant":
            msg["content"] = grounded_text
            break
    chat.chat_history = json.dumps(history)
    session_db.add(chat)
    session_db.commit()
    await ws.send_json({"type": "final", "text": grounded_text})
    await ws.send_json({"type": "complete"})

@router.websocket("/ws/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str, user_id: str):
    await websocket.accept()
    from ..db import get_session as _gs
    with _gs() as session_db:
        stmt = select(ChatSession).where(ChatSession.session_id == session_id, ChatSession.user_id == user_id)
        chat = session_db.exec(stmt).first()
        if chat and not chat.get_history():
            # prune accidental empty sessions
            session_db.delete(chat)
            session_db.commit()
            chat = None
        # send history (empty if ephemeral)
        await websocket.send_json({"type": "history", "history": chat.get_history() if chat else []})
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "error": "invalid_json"})
                    continue
                if payload.get("type") == "user_message":
                    content = str(payload.get("content", "")).strip()
                    if not content:
                        continue
                    if chat is None:
                        # persist now
                        chat = ChatSession(user_id=user_id, session_id=session_id)
                    chat.append_message("user", content)
                    session_db.add(chat)
                    session_db.commit()
                    await websocket.send_json({"type": "ack"})
                    # If LLM enabled use streaming LLM path
                    if USE_LLM and stream_llm_answer is not None:
                        # Append placeholder assistant message
                        chat.append_message("assistant", "")
                        session_db.add(chat)
                        session_db.commit()
                        try:
                            full_chunks = []
                            async for ev_type, data in stream_llm_answer(content, k=3):
                                if ev_type == "delta":
                                    full_chunks.append(data)
                                    await websocket.send_json({"type": "token", "token": data})
                                elif ev_type == "done":
                                    final_text = data
                                    history = chat.get_history()
                                    for msg in reversed(history):
                                        if msg["role"] == "assistant":
                                            msg["content"] = final_text
                                            break
                                    chat.chat_history = json.dumps(history)
                                    session_db.add(chat)
                                    session_db.commit()
                                    await websocket.send_json({"type": "final", "text": final_text})
                                    await websocket.send_json({"type": "complete"})
                                elif ev_type == "error":
                                    # Fall back immediately
                                    grounded_answer, _cit = build_grounded_answer(content, k=3)
                                    await stream_assistant_reply(websocket, chat, session_db, grounded_answer, already_appended=True)
                                    break
                        except Exception as e:
                            grounded_answer, _cit = build_grounded_answer(content, k=3)
                            await stream_assistant_reply(websocket, chat, session_db, grounded_answer, already_appended=True)
                    else:
                        grounded_answer, citations = build_grounded_answer(content, k=3)
                        await stream_assistant_reply(websocket, chat, session_db, grounded_answer)
                else:
                    await websocket.send_json({"type": "error", "error": "unknown_type"})
        except WebSocketDisconnect:
            return

@router.delete("/session/{session_id}")
def delete_session(session_id: str, user_id: str):
    from ..db import get_session as _gs
    with _gs() as session_db:
        stmt = select(ChatSession).where(ChatSession.session_id == session_id, ChatSession.user_id == user_id)
        chat = session_db.exec(stmt).first()
        if not chat or not chat.get_history():
            # deleting empty or non-existent is idempotent
            return {"deleted": False}
        session_db.delete(chat)
        session_db.commit()
        return {"deleted": True}

@router.get("/policies_meta")
def policies_meta():
    return {"policies": get_docs_meta()}

@router.get("/policies")
def policies():
    return {"policies": get_all_policies()}
