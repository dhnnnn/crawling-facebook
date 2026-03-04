"""
Entry point FastAPI untuk backend Multi-Platform Social Media Crawler.

Cara menjalankan:
    cd d:\.dev\python\Facebook\backend
    uvicorn app.main:app --reload --port 8000

Swagger UI: http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .api.routes.crawler import router as crawler_router

# ============================================================
# Inisialisasi Aplikasi FastAPI
# ============================================================

app = FastAPI(
    title="Multi-Platform Social Media Crawler API",
    description="""
    API backend untuk crawling komentar dari **Facebook**, **Instagram**, dan **TikTok**
    menggunakan Playwright. Semua platform memerlukan autentikasi via cookies.
    
    ## Endpoints
    
    - **POST /api/crawl** — Crawl komentar dari profil pengguna (username/URL)
    - **POST /api/crawl/hashtag** — Crawl komentar berdasarkan hashtag (IG & TikTok)
    - **GET /api/health** — Cek status server dan ketersediaan cookies
    
    ## Cara pakai
    
    1. Salin `.env.example` ke `.env` dan isi kredensial
    2. Jalankan server: `uvicorn app.main:app --reload --port 8000`
    3. Buka `http://localhost:8000/docs` untuk Swagger UI
    """,
    version="1.0.0",
)

# ============================================================
# CORS — izinkan frontend (Next.js) mengakses API ini
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Register Routes
# ============================================================

app.include_router(crawler_router)


# ============================================================
# Root endpoint
# ============================================================

@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Multi-Platform Social Media Crawler API 🚀",
        "docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/api/health",
    }


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 55)
    logger.info("  Social Media Crawler Backend — FastAPI")
    logger.info("=" * 55)
    logger.info("  Swagger UI  : http://localhost:8000/docs")
    logger.info("  Health Check: http://localhost:8000/api/health")
    logger.info("=" * 55)
