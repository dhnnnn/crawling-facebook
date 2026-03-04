"""
FastAPI Entry Point for Multi-Platform Social Media Crawler.
Restructured with platform-based grouping and security.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .api.routes.facebook import router as facebook_router
from .api.routes.instagram import router as instagram_router
from .api.routes.tiktok import router as tiktok_router
from .api.routes.system import router as system_router

# ============================================================
# FastAPI App Initialization
# ============================================================

app = FastAPI(
    title="Multi-Platform Social Media Crawler API",
    description="""
    API backend for crawling comments from **Facebook**, **Instagram**, and **TikTok**.
    Endpoints are organized by platform and secured via API Key.
    
    ## Security
    Include the API Key in the `X-API-Key` header for all protected requests.
    """,
    version="1.1.0",
)

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Router Registration
# ============================================================

# All platform routers are mounted under /api
app.include_router(facebook_router, prefix="/api")
app.include_router(instagram_router, prefix="/api")
app.include_router(tiktok_router, prefix="/api")
app.include_router(system_router, prefix="/api")

# ============================================================
# Root endpoint
# ============================================================

@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Multi-Platform Social Media Crawler API 🚀",
        "docs": "http://localhost:8000/docs",
        "status": "Ready",
    }

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 55)
    logger.info("  Crawler Backend Restructured — FastAPI")
    logger.info("=" * 55)
    logger.info("  Swagger UI  : http://localhost:8000/docs")
    logger.info("=" * 55)
