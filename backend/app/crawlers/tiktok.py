"""
TikTok Crawler — crawl komentar dari profil pengguna (username).
Hashtag di-handle oleh endpoint terpisah.
Menggunakan Playwright dengan autentikasi cookies.
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

from playwright.sync_api import Page
from loguru import logger

from .base import BaseCrawler
from ..config import Config
from ..schemas.models import CommentData, CrawlResult
from ..utils import random_delay, human_like_scroll


class TikTokCrawler(BaseCrawler):
    """Crawl komentar dari TikTok menggunakan Playwright"""

    PLATFORM = "tiktok"

    def __init__(self, page: Page):
        super().__init__(page)

    # ============================================================
    # PUBLIC API
    # ============================================================

    def crawl_profile(self, target: str, max_posts: int = 5) -> CrawlResult:
        """Crawl komentar dari profil TikTok (username atau URL)"""
        username = self._normalize_target(target)
        # TikTok URL profil menggunakan @ prefix
        profile_url = (
            target if target.startswith("http")
            else f"https://www.tiktok.com/@{username}"
        )

        logger.info(f"[TikTok] Mulai crawl profil: {profile_url} (max {max_posts} video)")

        errors: List[str] = []
        all_comments: List[CommentData] = []

        try:
            video_urls = self._get_video_urls_from_profile(profile_url, max_posts)
            logger.info(f"[TikTok] Ditemukan {len(video_urls)} video URL")

            for idx, video_url in enumerate(video_urls, 1):
                logger.info(f"[TikTok] Crawl video {idx}/{len(video_urls)}: {video_url}")
                try:
                    comments = self._crawl_video_comments(video_url)
                    all_comments.extend(comments)
                    logger.success(f"[TikTok] ✓ {len(comments)} komentar dari video {idx}")
                except Exception as e:
                    err = f"Gagal crawl video {video_url}: {e}"
                    logger.error(f"[TikTok] {err}")
                    errors.append(err)

        except Exception as e:
            err = f"Error fatal saat crawl profil TikTok {profile_url}: {e}"
            logger.error(f"[TikTok] {err}")
            errors.append(err)

        return self._make_result(self.PLATFORM, target, "username", all_comments, errors)

    def crawl_hashtag(self, hashtag: str, max_posts: int = 5) -> CrawlResult:
        """Crawl komentar dari video-video berdasarkan hashtag TikTok"""
        hashtag = hashtag.lstrip("#")
        hashtag_url = f"https://www.tiktok.com/tag/{hashtag}"

        logger.info(f"[TikTok] Mulai crawl hashtag: #{hashtag} (max {max_posts} video)")

        errors: List[str] = []
        all_comments: List[CommentData] = []

        try:
            video_urls = self._get_video_urls_from_hashtag(hashtag_url, max_posts)
            logger.info(f"[TikTok] Ditemukan {len(video_urls)} video URL dari #{hashtag}")

            for idx, video_url in enumerate(video_urls, 1):
                logger.info(f"[TikTok] Crawl video {idx}/{len(video_urls)}: {video_url}")
                try:
                    comments = self._crawl_video_comments(video_url)
                    all_comments.extend(comments)
                    logger.success(f"[TikTok] ✓ {len(comments)} komentar dari video {idx}")
                except Exception as e:
                    err = f"Gagal crawl video {video_url}: {e}"
                    logger.error(f"[TikTok] {err}")
                    errors.append(err)

        except Exception as e:
            err = f"Error fatal crawl hashtag TikTok #{hashtag}: {e}"
            logger.error(f"[TikTok] {err}")
            errors.append(err)

        return self._make_result(self.PLATFORM, f"#{hashtag}", "hashtag", all_comments, errors)

    # ============================================================
    # PROFIL: Ambil URL video dari halaman profil
    # ============================================================

    def _get_video_urls_from_profile(self, profile_url: str, max_videos: int) -> List[str]:
        """Navigasi ke profil TikTok dan kumpulkan URL video"""
        self.page.goto(profile_url, timeout=Config.REQUEST_TIMEOUT)
        random_delay(4, 6)

        video_urls: Set[str] = set()
        scroll_count = 0
        no_new_count = 0

        while len(video_urls) < max_videos and scroll_count < Config.MAX_SCROLL_ATTEMPTS:
            prev_count = len(video_urls)
            new_urls = self._extract_video_urls_from_page()
            video_urls.update(new_urls)

            logger.debug(f"[TikTok] {len(video_urls)} video URL (scroll {scroll_count + 1})")

            if len(video_urls) >= max_videos:
                break

            if len(video_urls) == prev_count:
                no_new_count += 1
                if no_new_count >= 3:
                    break
            else:
                no_new_count = 0

            human_like_scroll(self.page, scroll_amount=800)
            random_delay(2, 4)
            scroll_count += 1

        return list(video_urls)[:max_videos]

    def _get_video_urls_from_hashtag(self, hashtag_url: str, max_videos: int) -> List[str]:
        """Navigasi ke halaman hashtag TikTok dan kumpulkan URL video"""
        self.page.goto(hashtag_url, timeout=Config.REQUEST_TIMEOUT)
        random_delay(4, 6)

        video_urls: Set[str] = set()
        scroll_count = 0
        no_new_count = 0

        while len(video_urls) < max_videos and scroll_count < Config.MAX_SCROLL_ATTEMPTS:
            prev_count = len(video_urls)
            new_urls = self._extract_video_urls_from_page()
            video_urls.update(new_urls)

            logger.debug(f"[TikTok] {len(video_urls)} video URL hashtag (scroll {scroll_count + 1})")

            if len(video_urls) >= max_videos:
                break

            if len(video_urls) == prev_count:
                no_new_count += 1
                if no_new_count >= 3:
                    break
            else:
                no_new_count = 0

            human_like_scroll(self.page, scroll_amount=800)
            random_delay(2, 4)
            scroll_count += 1

        return list(video_urls)[:max_videos]

    def _extract_video_urls_from_page(self) -> List[str]:
        """Ekstrak URL video TikTok dari halaman saat ini"""
        video_urls = []
        try:
            # URL video TikTok: /video/XXXX
            elements = self.page.query_selector_all('a[href*="/video/"]')
            for el in elements:
                href = el.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        href = f"https://www.tiktok.com{href}"
                    # Hanya ambil URL yang berisi /video/
                    if "/video/" in href:
                        href = href.split("?")[0]
                        video_urls.append(href)
        except Exception as e:
            logger.debug(f"[TikTok] Error ekstrak URL video: {e}")

        return list(set(video_urls))

    # ============================================================
    # VIDEO: Crawl komentar dari satu video
    # ============================================================

    def _crawl_video_comments(self, video_url: str) -> List[CommentData]:
        """Crawl komentar dari satu URL video TikTok"""
        self.page.goto(video_url, timeout=Config.REQUEST_TIMEOUT)
        random_delay(4, 6)

        # Scroll untuk load komentar
        self._load_comments()

        return self._extract_comments(video_url)

    def _load_comments(self) -> None:
        """Scroll halaman video TikTok untuk load komentar"""
        for _ in range(3):
            human_like_scroll(self.page, scroll_amount=600)
            random_delay(2, 3)

            # Klik "Load more" jika ada
            try:
                load_more = self.page.query_selector('[data-e2e="comment-more-btn"]')
                if load_more and load_more.is_visible():
                    load_more.click()
                    random_delay(2, 3)
            except Exception:
                pass

    def _extract_comments(self, video_url: str) -> List[CommentData]:
        """Ekstrak komentar dari halaman video TikTok"""
        comments = []
        logger.info("[TikTok] Mengekstrak komentar...")

        # TikTok menggunakan data-e2e attributes yang lebih stabil
        comment_items = self.page.query_selector_all('[data-e2e="comment-item"]')

        if not comment_items:
            # Fallback selector
            comment_items = self.page.query_selector_all(
                'div[class*="CommentListItem"], div[class*="comment-item"]'
            )

        for idx, item in enumerate(comment_items):
            try:
                comment = self._parse_comment_element(item, video_url)
                if comment:
                    comments.append(comment)
            except Exception as e:
                logger.debug(f"[TikTok] Error parse komentar {idx}: {e}")

        if not comments:
            comments = self._fallback_extract_comments(video_url)

        logger.info(f"[TikTok] Berhasil ekstrak {len(comments)} komentar")
        return comments

    def _parse_comment_element(self, element, video_url: str) -> Optional[CommentData]:
        """Parse elemen komentar TikTok menjadi CommentData"""
        try:
            # Nama author
            author_name = ""
            author_url = ""

            # TikTok: data-e2e="comment-username"
            author_el = element.query_selector('[data-e2e="comment-username-1"]') or \
                        element.query_selector('[data-e2e="comment-username"]') or \
                        element.query_selector('a[href*="/@"]')

            if author_el:
                author_name = author_el.text_content().strip()
                href = author_el.get_attribute("href") or ""
                if href.startswith("/"):
                    author_url = f"https://www.tiktok.com{href}"
                elif href.startswith("http"):
                    author_url = href

            # Teks komentar
            comment_text = ""
            text_el = element.query_selector('[data-e2e="comment-level-1"]') or \
                      element.query_selector('p[data-e2e="comment-text"]') or \
                      element.query_selector('span[data-e2e="comment-text-1"]')

            if text_el:
                comment_text = text_el.text_content().strip()
            else:
                # Fallback: ambil span terpanjang
                spans = element.query_selector_all("span")
                for span in spans:
                    text = span.text_content().strip()
                    if text and len(text) > len(comment_text) and len(text) > 3:
                        comment_text = text

            if not comment_text or not author_name:
                return None

            # Likes
            likes = 0
            try:
                like_el = element.query_selector('[data-e2e="comment-like-count"]')
                if like_el:
                    like_text = like_el.text_content().strip()
                    # Handle "1.2K", "5", dll.
                    likes = self._parse_count(like_text)
            except Exception:
                pass

            return CommentData(
                post_url=video_url,
                post_author="",
                comment_author=author_name,
                comment_author_url=author_url,
                comment_text=comment_text,
                comment_timestamp="",
                likes_count=likes,
                replies_count=0,
                crawled_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.debug(f"[TikTok] Error parse elemen komentar: {e}")
            return None

    def _fallback_extract_comments(self, video_url: str) -> List[CommentData]:
        """Fallback: coba ambil komentar dari struktur umum halaman"""
        comments = []
        try:
            # Cari semua div yang mengandung teks di seksi komentar
            comment_section = self.page.query_selector('[data-e2e="comment-list"]')
            if comment_section:
                items = comment_section.query_selector_all("div")
                for div in items:
                    text = div.text_content().strip()
                    if text and 5 < len(text) < 500:
                        comments.append(CommentData(
                            post_url=video_url,
                            post_author="",
                            comment_author="Unknown",
                            comment_author_url="",
                            comment_text=text,
                            comment_timestamp="",
                            likes_count=0,
                            replies_count=0,
                            crawled_at=datetime.now().isoformat(),
                        ))
        except Exception as e:
            logger.debug(f"[TikTok] Fallback extract gagal: {e}")
        return comments

    @staticmethod
    def _parse_count(text: str) -> int:
        """
        Parse angka dari format TikTok: '1.2K' → 1200, '5M' → 5000000, '42' → 42
        """
        try:
            text = text.strip().upper()
            if "K" in text:
                return int(float(text.replace("K", "")) * 1_000)
            elif "M" in text:
                return int(float(text.replace("M", "")) * 1_000_000)
            else:
                return int(text)
        except Exception:
            return 0
