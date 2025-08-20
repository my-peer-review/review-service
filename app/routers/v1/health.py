from fastapi import APIRouter

router = APIRouter()

@router.get("/review/health")
async def health_check():
    return {"status": "ok"}