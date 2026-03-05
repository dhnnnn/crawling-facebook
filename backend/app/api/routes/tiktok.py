import asyncio
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from typing import List, Dict, Any

from ...schemas.models import TikTokCrawlRequest, HashtagCrawlRequest, CrawlResult
from ...services.crawler_service import crawl_tiktok_profile, crawl_tiktok_hashtag
from ...utils import load_crawl_results, list_crawl_results_metadata, get_crawl_result_detail
from ..deps import get_api_key

router = APIRouter(prefix="/tiktok", tags=["Crawling TikTok"], dependencies=[Depends(get_api_key)])

@router.post("/crawl/username", response_model=CrawlResult, summary="Crawl TikTok by username")
async def crawl_profile(request: TikTokCrawlRequest) -> CrawlResult:
    """
    Crawl comments from a TikTok profile by **username** (without @) or profil URL.
    """
    if not request.target.strip():
        raise HTTPException(status_code=400, detail="Target cannot be empty.")

    logger.info(f"[API:TT] POST /tiktok/crawl/username | target={request.target}")
    try:
        result = await asyncio.to_thread(
            crawl_tiktok_profile,
            request.target.strip(),
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API:TT] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/crawl/hashtag", response_model=CrawlResult, summary="Crawl TikTok by hashtag")
async def crawl_hashtag(request: HashtagCrawlRequest) -> CrawlResult:
    """
    Crawl comments from TikTok videos by **hashtag**.
    """
    hashtag = request.hashtag.strip().lstrip("#")
    if not hashtag:
        raise HTTPException(status_code=400, detail="Hashtag cannot be empty.")

    logger.info(f"[API:TT] POST /tiktok/crawl/hashtag | hashtag=#{hashtag}")
    try:
        result = await asyncio.to_thread(
            crawl_tiktok_hashtag,
            hashtag,
            request.max_posts,
        )
        return result
    except Exception as e:
        logger.error(f"[API:TT] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/comment/list", response_model=List[Dict[str, Any]], summary="Get TikTok comment results List")
async def list_comment_results():
    """
    Get a list of all TikTok comment crawl result metadata.
    """
    metadata = list_crawl_results_metadata("tiktok", "comment")
    if not metadata:
        raise HTTPException(status_code=404, detail="masih belum ada data crawling silahkan crawling terlebih dahulu")
    return metadata

@router.get("/results/comment/view/{filename}", response_model=Dict[str, Any], summary="View TikTok comment result detail")
async def view_comment_result(filename: str):
    """
    Get the full JSON content for a specific TikTok comment result file.
    """
    result = get_crawl_result_detail("tiktok", "comment", filename)
    if not result:
        raise HTTPException(status_code=404, detail="File JSON tidak ditemukan.")
    return result

@router.get("/results/comment", response_model=List[Dict[str, Any]], summary="Get ALL TikTok comment results (Legacy/Full)")
async def get_comment_results():
    """
    Get all saved TikTok crawl results from username/profile (comments).
    """
    results = load_crawl_results("tiktok", "comment")
    if not results:
        raise HTTPException(status_code=404, detail="masih belum ada data crawling silahkan crawling terlebih dahulu")
    return results

@router.get("/results/hashtag/list", response_model=List[Dict[str, Any]], summary="Get TikTok hashtag results List")
async def list_hashtag_results():
    """
    Get a list of all TikTok hashtag crawl result metadata.
    """
    metadata = list_crawl_results_metadata("tiktok", "hashtag")
    if not metadata:
        raise HTTPException(status_code=404, detail="masih belum ada data crawling silahkan crawling terlebih dahulu")
    return metadata

@router.get("/results/hashtag/view/{filename}", response_model=Dict[str, Any], summary="View TikTok hashtag result detail")
async def view_hashtag_result(filename: str):
    """
    Get the full JSON content for a specific TikTok hashtag result file.
    """
    result = get_crawl_result_detail("tiktok", "hashtag", filename)
    if not result:
        raise HTTPException(status_code=404, detail="File JSON tidak ditemukan.")
    return result

@router.get("/results/hashtag", response_model=List[Dict[str, Any]], summary="Get ALL TikTok hashtag results (Legacy/Full)")
async def get_hashtag_results():
    """
    Get all saved TikTok crawl results from hashtags.
    """
    results = load_crawl_results("tiktok", "hashtag")
    if not results:
        raise HTTPException(status_code=404, detail="masih belum ada data crawling silahkan crawling terlebih dahulu")
    return results
