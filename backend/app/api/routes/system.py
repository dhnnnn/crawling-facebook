from fastapi import APIRouter
from ...schemas.models import HealthResponse
from ...config import Config

router = APIRouter(tags=["System"])

@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check():
    """
    Check server status and platform cookies availability.
    """
    cookies_status = {}
    for platform in ["facebook", "instagram", "tiktok"]:
        cookies_path = Config.get_cookies_path(platform)
        cookies_status[platform] = cookies_path.exists()

    return HealthResponse(
        status="ok",
        message="Backend crawler is running",
        platform_cookies=cookies_status
    )
