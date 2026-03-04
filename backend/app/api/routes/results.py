from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ...utils import load_crawl_results

router = APIRouter()

@router.get("/{platform}", response_model=List[Dict[str, Any]])
async def get_results(platform: str):
    """
    Get all saved crawl results for a specific platform (instagram, tiktok, facebook).
    Returns a list of all JSON objects found in the platform's data folder.
    """
    valid_platforms = ["instagram", "tiktok", "facebook"]
    if platform.lower() not in valid_platforms:
        raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of {valid_platforms}")
    
    results = load_crawl_results(platform.lower())
    return results
