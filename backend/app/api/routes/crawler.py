"""
API Routes — endpoint terpisah per platform.
Semua handler adalah async, Playwright dipanggil via asyncio.to_thread()
agar tidak memblokir asyncio event loop FastAPI.

Endpoints:
    POST /api/crawl/facebook           - crawl profil Facebook
    POST /api/crawl/instagram          - crawl profil Instagram
    POST /api/crawl/tiktok             - crawl profil TikTok
    POST /api/crawl/hashtag/instagram  - crawl hashtag Instagram
    POST /api/crawl/hashtag/tiktok     - crawl hashtag TikTok
    GET  /api/health                   - health check
"""

import asyncio
from fastapi import APIRouter, HTTPException
from loguru import logger

from ...schemas.models import (
    FacebookCrawlRequest,
    InstagramCrawlRequest,
    TikTokCrawlRequest,
    HashtagCrawlRequest,
    CrawlResult,
)
from ...services.crawler_service import (
    crawl_facebook_profile,
    crawl_instagram_profile,
    crawl_instagram_hashtag,
    crawl_tiktok_profile,
    crawl_tiktok_hashtag,
)
from ...config import Config

router = APIRouter(prefix="/api", tags=["Crawler"])


# ============================================================
# FACEBOOK
# ============================================================

@router.post(
    "/crawl/facebook",
    response_model=CrawlResult,
    summary="Crawl komentar dari profil Facebook",
)
async def crawl_facebook(request: FacebookCrawlRequest) -> CrawlResult:
    """
    Crawl komentar dari profil Facebook berdasarkan **username** atau **URL profil**.
    
    Memerlukan cookies Facebook yang valid di `data/cookies/cookies_default.json`.
    """
    if not request.target.strip():
        raise HTTPException(status_code=400, detail="Target tidak boleh kosong.")

    logger.info(f"[API] POST /api/crawl/facebook | target={request.target}")
    try:
        # Jalankan sync Playwright di thread terpisah agar tidak block event loop
        result = await asyncio.to_thread(
            crawl_facebook_profile,
            request.target.strip(),
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API] Error /api/crawl/facebook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# INSTAGRAM
# ============================================================

@router.post(
    "/crawl/instagram",
    response_model=CrawlResult,
    summary="Crawl komentar dari profil Instagram",
)
async def crawl_instagram(request: InstagramCrawlRequest) -> CrawlResult:
    """
    Crawl komentar dari profil Instagram berdasarkan **username** atau **URL profil**.
    
    Memerlukan cookies Instagram di `data/cookies/cookies_instagram.json`.  
    Jika belum ada, isi `IG_USERNAME` dan `IG_PASSWORD` di `.env` untuk auto-login.
    """
    if not request.target.strip():
        raise HTTPException(status_code=400, detail="Target tidak boleh kosong.")

    logger.info(f"[API] POST /api/crawl/instagram | target={request.target}")
    try:
        result = await asyncio.to_thread(
            crawl_instagram_profile,
            request.target.strip(),
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API] Error /api/crawl/instagram: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/crawl/hashtag/instagram",
    response_model=CrawlResult,
    summary="Crawl komentar dari hashtag Instagram",
)
async def crawl_instagram_hashtag_endpoint(request: HashtagCrawlRequest) -> CrawlResult:
    """
    Crawl komentar dari post-post Instagram berdasarkan **hashtag**.
    
    Masukkan hashtag **tanpa #**, contoh: `wisataIndonesia` bukan `#wisataIndonesia`.
    """
    hashtag = request.hashtag.strip().lstrip("#")
    if not hashtag:
        raise HTTPException(status_code=400, detail="Hashtag tidak boleh kosong.")

    logger.info(f"[API] POST /api/crawl/hashtag/instagram | hashtag=#{hashtag}")
    try:
        result = await asyncio.to_thread(
            crawl_instagram_hashtag,
            hashtag,
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API] Error /api/crawl/hashtag/instagram: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# TIKTOK
# ============================================================

@router.post(
    "/crawl/tiktok",
    response_model=CrawlResult,
    summary="Crawl komentar dari profil TikTok",
)
async def crawl_tiktok(request: TikTokCrawlRequest) -> CrawlResult:
    """
    Crawl komentar dari profil TikTok berdasarkan **username** (tanpa @) atau **URL profil**.
    
    Memerlukan cookies TikTok di `data/cookies/cookies_tiktok.json`.  
    Jika belum ada, server akan membuka browser untuk **login manual** (TikTok anti-bot sangat ketat).
    """
    if not request.target.strip():
        raise HTTPException(status_code=400, detail="Target tidak boleh kosong.")

    logger.info(f"[API] POST /api/crawl/tiktok | target={request.target}")
    try:
        result = await asyncio.to_thread(
            crawl_tiktok_profile,
            request.target.strip(),
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API] Error /api/crawl/tiktok: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/crawl/hashtag/tiktok",
    response_model=CrawlResult,
    summary="Crawl komentar dari hashtag TikTok",
)
async def crawl_tiktok_hashtag_endpoint(request: HashtagCrawlRequest) -> CrawlResult:
    """
    Crawl komentar dari video-video TikTok berdasarkan **hashtag**.
    
    Masukkan hashtag **tanpa #**, contoh: `fyp` bukan `#fyp`.
    """
    hashtag = request.hashtag.strip().lstrip("#")
    if not hashtag:
        raise HTTPException(status_code=400, detail="Hashtag tidak boleh kosong.")

    logger.info(f"[API] POST /api/crawl/hashtag/tiktok | hashtag=#{hashtag}")
    try:
        result = await asyncio.to_thread(
            crawl_tiktok_hashtag,
            hashtag,
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API] Error /api/crawl/hashtag/tiktok: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# HEALTH CHECK
# ============================================================

@router.get("/health", summary="Health check — status server dan cookies")
async def health_check():
    """Cek status server dan ketersediaan cookies tiap platform."""
    cookies_status = {}
    for platform in ["facebook", "instagram", "tiktok"]:
        cookies_path = Config.get_cookies_path(platform)
        cookies_status[platform] = cookies_path.exists()

    return {
        "status": "ok",
        "message": "Backend crawler berjalan normal 🚀",
        "platform_cookies": cookies_status,
        "endpoints": {
            "facebook": "POST /api/crawl/facebook",
            "instagram": "POST /api/crawl/instagram",
            "tiktok": "POST /api/crawl/tiktok",
            "hashtag_instagram": "POST /api/crawl/hashtag/instagram",
            "hashtag_tiktok": "POST /api/crawl/hashtag/tiktok",
        },
    }
