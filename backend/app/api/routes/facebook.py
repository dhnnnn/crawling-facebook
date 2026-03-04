import asyncio
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from typing import List, Dict, Any

from ...schemas.models import FacebookCrawlRequest, CrawlResult
from ...services.crawler_service import crawl_facebook_profile
from ...utils import load_crawl_results
from ..deps import get_api_key

router = APIRouter(prefix="/facebook", tags=["Crawling Facebook"], dependencies=[Depends(get_api_key)])

@router.post("/crawl/username", response_model=CrawlResult, summary="Crawl Facebook by username")
async def crawl_profile(request: FacebookCrawlRequest) -> CrawlResult:
    """
    Crawl comments from a Facebook profile by **username** or profile URL.
    """
    if not request.target.strip():
        raise HTTPException(status_code=400, detail="Target cannot be empty.")

    logger.info(f"[API:FB] POST /facebook/crawl/username | target={request.target}")
    try:
        result = await asyncio.to_thread(
            crawl_facebook_profile,
            request.target.strip(),
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API:FB] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/comment", response_model=List[Dict[str, Any]], summary="Get Facebook comment results")
async def get_comment_results():
    """
    Get all saved Facebook crawl results from username/profile (comments).
    """
    return load_crawl_results("facebook", "comment")
