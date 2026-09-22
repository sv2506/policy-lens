from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["echo"])

class EchoIn(BaseModel):
    message: str

@router.post("/echo")
async def echo(payload: EchoIn):
    return {"echo": payload.message}
