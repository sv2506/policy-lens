from __future__ import annotations
from typing import Optional, List, Any
from sqlmodel import SQLModel, Field
import json
import uuid
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class ChatSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True, default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(index=True)
    chat_history: str = Field(default="[]")  # JSON array of messages
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def get_history(self) -> List[dict]:
        try:
            return json.loads(self.chat_history)
        except Exception:
            return []

    def append_message(self, role: str, content: str):
        history = self.get_history()
        history.append({"role": role, "content": content, "ts": utc_now().isoformat()})
        self.chat_history = json.dumps(history)
        self.updated_at = utc_now()
