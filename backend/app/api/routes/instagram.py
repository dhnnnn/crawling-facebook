import asyncio
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from typing import List, Dict, Any

from ...schemas.models import InstagramCrawlRequest, HashtagCrawlRequest, CrawlResult
from ...services.crawler_service import crawl_instagram_profile, crawl_instagram_hashtag
from ...utils import load_crawl_results, list_crawl_results_metadata, get_crawl_result_detail
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

@router.get("/results/comment/list", response_model=List[Dict[str, Any]], summary="Get Instagram comment results List")
async def list_comment_results():
    """
    Get a list of all Instagram comment crawl result metadata.
    """
    metadata = list_crawl_results_metadata("instagram", "comment")
    if not metadata:
        raise HTTPException(status_code=404, detail="masih belum ada data crawling silahkan crawling terlebih dahulu")
    return metadata

@router.get("/results/comment/view/{filename}", response_model=Dict[str, Any], summary="View Instagram comment result detail")
async def view_comment_result(filename: str):
    """
    Get the full JSON content for a specific Instagram comment result file.
    """
    result = get_crawl_result_detail("instagram", "comment", filename)
    if not result:
        raise HTTPException(status_code=404, detail="File JSON tidak ditemukan.")
    return result

@router.get("/results/comment", response_model=List[Dict[str, Any]], summary="Get ALL Instagram comment results (Legacy/Full)")
async def get_comment_results():
    """
    Get all saved Instagram crawl results from username/profile (comments).
    """
    results = load_crawl_results("instagram", "comment")
    if not results:
        raise HTTPException(status_code=404, detail="masih belum ada data crawling silahkan crawling terlebih dahulu")
    return results

@router.get("/results/hashtag/list", response_model=List[Dict[str, Any]], summary="Get Instagram hashtag results List")
async def list_hashtag_results():
    """
    Get a list of all Instagram hashtag crawl result metadata.
    """
    metadata = list_crawl_results_metadata("instagram", "hashtag")
    if not metadata:
        raise HTTPException(status_code=404, detail="masih belum ada data crawling silahkan crawling terlebih dahulu")
    return metadata

@router.get("/results/hashtag/view/{filename}", response_model=Dict[str, Any], summary="View Instagram hashtag result detail")
async def view_hashtag_result(filename: str):
    """
    Get the full JSON content for a specific Instagram hashtag result file.
    """
    result = get_crawl_result_detail("instagram", "hashtag", filename)
    if not result:
        raise HTTPException(status_code=404, detail="File JSON tidak ditemukan.")
    return result

@router.get("/results/hashtag", response_model=List[Dict[str, Any]], summary="Get ALL Instagram hashtag results (Legacy/Full)")
async def get_hashtag_results():
    """
    Get all saved Instagram crawl results from hashtags.
    """
    results = load_crawl_results("instagram", "hashtag")
    if not results:
        raise HTTPException(status_code=404, detail="masih belum ada data crawling silahkan crawling terlebih dahulu")
    return results
