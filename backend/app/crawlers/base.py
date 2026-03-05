"""Base class untuk semua crawler platform"""

from abc import ABC, abstractmethod
from typing import List, Optional

from playwright.sync_api import Page
from loguru import logger

from ..schemas.models import CommentData, CrawlResult
from ..utils import random_delay, human_like_scroll, extract_username_from_url


class BaseCrawler(ABC):
    """Abstract base class yang mendefinisikan interface standar untuk semua crawler"""

    def __init__(self, page: Page):
        self.page = page

    @abstractmethod
    def crawl_profile(self, target: str, max_posts: int = 5) -> CrawlResult:
        """
        Crawl komentar dari profil pengguna.
        
        Args:
            target: Username atau URL profil
            max_posts: Maksimal jumlah post yang dicrawl
            
        Returns:
            CrawlResult berisi semua komentar yang berhasil dikumpulkan
        """
        pass

    @abstractmethod
    def crawl_hashtag(self, hashtag: str, max_posts: int = 5) -> CrawlResult:
        """
        Crawl komentar dari post-post berdasarkan hashtag.
        
        Args:
            hashtag: Hashtag yang dicari (tanpa #)
            max_posts: Maksimal jumlah post yang dicrawl
            
        Returns:
            CrawlResult berisi semua komentar yang berhasil dikumpulkan
        """
        pass

    def _normalize_target(self, target: str) -> str:
        """
        Normalisasi input target: jika URL maka ekstrak username,
        jika sudah username maka langsung pakai.
        """
        if target.startswith("http"):
            return extract_username_from_url(target)
        # Buang @ di depan jika ada (khusus TikTok)
        return target.lstrip("@")

    def _make_result(
        self,
        platform: str,
        target: str,
        crawl_type: str,
        comments: List[CommentData],
        errors: Optional[List[str]] = None,
    ) -> CrawlResult:
        """Helper untuk membuat CrawlResult dari list komentar"""
        # Hitung jumlah post unik
        from datetime import datetime
        unique_posts = len(set(c.post_url for c in comments))
        return CrawlResult(
            status="success" if comments else "error",
            platform=platform,
            target=target,
            crawl_type=crawl_type,
            total_posts_crawled=unique_posts,
            total_comments=len(comments),
            comments=comments,
            crawled_at=datetime.now().isoformat(),
            errors=errors or [],
        )
