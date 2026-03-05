"""Pydantic schemas untuk request dan response API crawler"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================
# REQUEST MODELS — per platform (tidak perlu field 'platform' lagi)
# ============================================================

class FacebookCrawlRequest(BaseModel):
    """Request untuk POST /api/crawl/facebook"""
    target: str = Field(
        ...,
        description="Username atau URL profil Facebook"
    )
    max_posts: int = Field(default=5, ge=1, le=50, description="Jumlah maksimal post (1-50)")

    class Config:
        json_schema_extra = {
            "example": {"target": "MasRusdisutejo.N1", "max_posts": 3}
        }


class InstagramCrawlRequest(BaseModel):
    """Request untuk POST /api/crawl/instagram"""
    target: str = Field(
        ...,
        description="Username atau URL profil Instagram"
    )
    max_posts: int = Field(default=5, ge=1, le=50, description="Jumlah maksimal post (1-50)")

    class Config:
        json_schema_extra = {
            "example": {"target": "rusdi.sutejo", "max_posts": 3}
        }


class TikTokCrawlRequest(BaseModel):
    """Request untuk POST /api/crawl/tiktok"""
    target: str = Field(
        ...,
        description="Username TikTok (tanpa @) atau URL profil"
    )
    max_posts: int = Field(default=5, ge=1, le=50, description="Jumlah maksimal video (1-50)")

    class Config:
        json_schema_extra = {
            "example": {"target": "rusdi.sutejo", "max_posts": 3}
        }


class HashtagCrawlRequest(BaseModel):
    """Request untuk POST /api/crawl/hashtag/instagram atau /api/crawl/hashtag/tiktok"""
    hashtag: str = Field(
        ...,
        description="Hashtag yang dicari (tanpa #, contoh: 'wisataIndonesia')"
    )
    max_posts: int = Field(default=5, ge=1, le=30, description="Jumlah maksimal post (1-30)")

    class Config:
        json_schema_extra = {
            "example": {"hashtag": "wisataIndonesia", "max_posts": 5}
        }


# ============================================================
# RESPONSE MODELS
# ============================================================

class CommentData(BaseModel):
    """Data satu komentar yang berhasil dicrawl"""
    post_url: str = Field(description="URL post tempat komentar berada")
    post_author: Optional[str] = Field(default="", description="Nama pemilik post")
    comment_author: str = Field(description="Nama pengguna yang berkomentar")
    comment_author_url: Optional[str] = Field(default="", description="URL profil komentator")
    comment_text: str = Field(description="Isi komentar")
    comment_timestamp: Optional[str] = Field(default="", description="Waktu komentar diposting")
    likes_count: Optional[int] = Field(default=0, description="Jumlah likes pada komentar")
    replies_count: Optional[int] = Field(default=0, description="Jumlah balasan komentar")
    post_hashtags: Optional[List[str]] = Field(default=[], description="Semua hashtag yang ada di caption postingan")
    crawled_at: str = Field(description="Waktu crawling dilakukan (ISO format)")


class CrawlResult(BaseModel):
    """Response lengkap dari semua endpoint crawling"""
    status: str = Field(description="'success' atau 'error'")
    platform: str = Field(description="Platform yang dicrawl")
    target: str = Field(description="Username/URL/hashtag yang dicrawl")
    crawl_type: str = Field(description="'username' atau 'hashtag'")
    total_posts_crawled: int = Field(description="Jumlah post yang berhasil dicrawl")
    total_comments: int = Field(description="Total semua komentar yang dikumpulkan")
    comments: List[CommentData] = Field(description="Daftar semua komentar")
    hashtag_stats: Optional[List[dict]] = Field(
        default=[],
        description="Statistik hashtag yang ditemukan di caption post (khusus hashtag crawl). "
                    "Format: [{hashtag, count}] diurutkan dari yang paling banyak dipakai."
    )
    crawled_at: str = Field(description="Waktu crawling selesai dilakukan (ISO format)")
    errors: List[str] = Field(default=[], description="Daftar error yang terjadi (jika ada)")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "platform": "facebook",
                "target": "MasRusdisutejo.N1",
                "crawl_type": "username",
                "total_posts_crawled": 3,
                "total_comments": 47,
                "crawled_at": "2026-03-04T08:00:00",
                "comments": [
                    {
                        "post_url": "https://www.facebook.com/...",
                        "post_author": "Mas Rudi",
                        "comment_author": "Budi Santoso",
                        "comment_author_url": "https://www.facebook.com/budi",
                        "comment_text": "Mantap banget kontennya!",
                        "comment_timestamp": "2 jam yang lalu",
                        "likes_count": 5,
                        "replies_count": 1,
                        "crawled_at": "2026-03-04T08:00:00"
                    }
                ],
                "errors": []
            }
        }


class HealthResponse(BaseModel):
    """Response dari endpoint health check"""
    status: str = "ok"
    message: str = "Backend crawler berjalan normal"
    platform_cookies: dict = Field(
        description="Status cookies tiap platform (True = tersedia)"
    )
