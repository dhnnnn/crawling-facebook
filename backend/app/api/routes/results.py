from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from ...utils import list_crawl_results_metadata, get_crawl_result_detail
from ..deps import get_api_key

router = APIRouter(prefix="/results", tags=["Crawl Results Summary"], dependencies=[Depends(get_api_key)])

@router.get("/{platform}/{crawl_type}/list", response_model=List[Dict[str, Any]])
async def get_results_list(platform: str, crawl_type: str):
    """
    Get a list of all crawl results metadata (filenames, targets, timestamps).
    `crawl_type` can be 'comment' or 'hashtag'.
    """
    valid_platforms = ["instagram", "tiktok", "facebook"]
    valid_types = ["comment", "hashtag"]
    
    if platform.lower() not in valid_platforms:
        raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of {valid_platforms}")
    if crawl_type.lower() not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid crawl_type. Must be one of {valid_types}")
    
    metadata = list_crawl_results_metadata(platform.lower(), crawl_type.lower())
    if not metadata:
        raise HTTPException(status_code=404, detail="masih belum ada data crawling silahkan crawling terlebih dahulu")
    
    return metadata

@router.get("/{platform}/{crawl_type}/view/{filename}", response_model=Dict[str, Any])
async def get_result_detail(platform: str, crawl_type: str, filename: str):
    """
    Get the full JSON content for a specific crawl result by its filename (ID).
    """
    valid_platforms = ["instagram", "tiktok", "facebook"]
    if platform.lower() not in valid_platforms:
        raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of {valid_platforms}")
        
    result = get_crawl_result_detail(platform.lower(), crawl_type.lower(), filename)
    if not result:
        raise HTTPException(status_code=404, detail="File JSON tidak ditemukan.")
    
    return result
