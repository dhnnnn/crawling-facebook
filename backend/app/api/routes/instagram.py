import asyncio
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from typing import List, Dict, Any

from ...schemas.models import InstagramCrawlRequest, HashtagCrawlRequest, CrawlResult
from ...services.crawler_service import crawl_instagram_profile, crawl_instagram_hashtag
from ...utils import load_crawl_results
from ..deps import get_api_key

router = APIRouter(prefix="/instagram", tags=["Crawling Instagram"], dependencies=[Depends(get_api_key)])

@router.post("/crawl/username", response_model=CrawlResult, summary="Crawl Instagram by username")
async def crawl_profile(request: InstagramCrawlRequest) -> CrawlResult:
    """
    Crawl comments from an Instagram profile by **username** or profile URL.
    """
    if not request.target.strip():
        raise HTTPException(status_code=400, detail="Target cannot be empty.")

    logger.info(f"[API:IG] POST /instagram/crawl/username | target={request.target}")
    try:
        result = await asyncio.to_thread(
            crawl_instagram_profile,
            request.target.strip(),
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API:IG] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/crawl/hashtag", response_model=CrawlResult, summary="Crawl Instagram by hashtag")
async def crawl_hashtag(request: HashtagCrawlRequest) -> CrawlResult:
    """
    Crawl comments from Instagram posts by **hashtag**.
    """
    hashtag = request.hashtag.strip().lstrip("#")
    if not hashtag:
        raise HTTPException(status_code=400, detail="Hashtag cannot be empty.")

    logger.info(f"[API:IG] POST /instagram/crawl/hashtag | hashtag=#{hashtag}")
    try:
        result = await asyncio.to_thread(
            crawl_instagram_hashtag,
            hashtag,
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API:IG] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/comment", response_model=List[Dict[str, Any]], summary="Get Instagram comment results")
async def get_comment_results():
    """
    Get all saved Instagram crawl results from username/profile (comments).
    """
    return load_crawl_results("instagram", "comment")

@router.get("/results/hashtag", response_model=List[Dict[str, Any]], summary="Get Instagram hashtag results")
async def get_hashtag_results():
    """
    Get all saved Instagram crawl results from hashtags.
    """
    return load_crawl_results("instagram", "hashtag")
