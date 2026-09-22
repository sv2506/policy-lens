from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import get_settings
from .routers import health, echo, home
from .routers import chat
from .db import init_db

settings = get_settings()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(echo.router, prefix=settings.api_prefix)
app.include_router(home.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)

@app.get("/")
async def root():
    return {"service": settings.app_name, "docs": "/docs"}
