from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path
import os

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "chat.db"
DB_PATH = Path(os.getenv("CHAT_DB_PATH", str(DEFAULT_DB_PATH))).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

def init_db():
    from . import models  # noqa: F401 ensure models imported
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    return Session(engine)
