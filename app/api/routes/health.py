# app/api/routes/health.py

from fastapi import APIRouter

# Create router with prefix and tag
router = APIRouter(
    prefix="/health",
    tags=["health"]
)


# GET /health/
@router.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "adhivakta-ai"
    }