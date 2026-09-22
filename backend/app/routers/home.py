from fastapi import APIRouter

router = APIRouter(tags=["home"])

@router.get("/home")
async def get_home():
    return {"message": "Welcome to the PolicyLens API"}
