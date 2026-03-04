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
from ..utils import random_delay, human_like_scroll, load_cookies


class TikTokCrawler(BaseCrawler):
    """Crawl komentar dari TikTok menggunakan Playwright"""

    PLATFORM = "tiktok"

    def __init__(self, page: Page):
        super().__init__(page)
        self.cookies_path = Config.get_cookies_path("tiktok")
        self._setup_cookies()

    def _setup_cookies(self):
        """Muat cookies jika tersedia"""
        cookies = load_cookies(self.cookies_path)
        if cookies:
            try:
                self.page.context.add_cookies(cookies)
                logger.info("[TikTok] Cookies berhasil dipasang dari file")
            except Exception as e:
                logger.warning(f"[TikTok] Gagal memasang cookies: {e}")

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
                try:
                    href = el.get_attribute("href")
                    if href:
                        if href.startswith("/"):
                            href = f"https://www.tiktok.com{href}"
                        # Hanya ambil URL yang berisi /video/
                        if "/video/" in href:
                            href = href.split("?")[0]
                            video_urls.append(href)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[TikTok] Error ekstrak URL video: {e}")

        return list(set(video_urls))

    def _dismiss_popups(self) -> None:
        """Tekan Escape sekali untuk menutup popup apapun secara pasif.
        Tidak mencari / mengklik tombol X — langsung lanjut ke panel komentar.
        """
        try:
            random_delay(0.5, 1.0)
            self.page.keyboard.press("Escape")
            random_delay(0.5, 1.0)
            logger.debug("[TikTok] Escape ditekan untuk dismiss popup")
        except Exception as e:
            logger.debug(f"[TikTok] Gagal tekan Escape: {e}")

    def _open_comments_panel(self) -> bool:
        """Klik tab Komentar dan verifikasi panel komentar benar-benar terbuka sebelum lanjut."""
        # Selector tab "Komentar" di panel kanan (urutan prioritas)
        tab_selectors = [
            'div[role="tab"]:has-text("Komentar")',
            '#tabs-0-tab-0',
            'p[data-e2e="browse-comment"]',
            'div[data-e2e="browse-comment"]',
            'button[data-e2e="browse-comment"]',
            'span:has-text("Komentar")',
            'p:has-text("Komentar")',
        ]
        # Selector untuk verifikasi: komentar sudah muncul di DOM
        verify_selectors = [
            '[data-e2e="comment-list-container"]',
            '[data-e2e="comment-list"]',
            'div[class*="DivCommentListContainer"]',
            '[data-e2e="comment-item"]',
        ]

        MAX_ATTEMPTS = 3
        for attempt in range(1, MAX_ATTEMPTS + 1):
            logger.debug(f"[TikTok] Mencoba buka tab Komentar (percobaan {attempt}/{MAX_ATTEMPTS})...")
            random_delay(1.0, 1.5)

            try:
                width = self.page.viewport_size['width']
            except Exception:
                width = 1280  # default fallback

            clicked = False
            for selector in tab_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for btn in elements:
                        if not btn.is_visible():
                            continue
                        box = btn.bounding_box()
                        # Hanya klik jika elemen berada di panel kanan (> 55% lebar layar)
                        if box and box['x'] > width * 0.55:
                            logger.info(f"[TikTok] Klik tab Komentar via '{selector}' di x={box['x']:.0f}")
                            btn.click(timeout=2000, force=True)
                            random_delay(1.5, 2.5)
                            clicked = True
                            break
                    if clicked:
                        break
                except Exception:
                    continue

            if not clicked:
                logger.debug(f"[TikTok] Tab tidak ditemukan pada percobaan {attempt}, tunggu sebentar...")
                random_delay(1.5, 2.0)
                continue

            # Verifikasi: pastikan area komentar sudah muncul di DOM
            verified = False
            for vsel in verify_selectors:
                try:
                    el = self.page.query_selector(vsel)
                    if el and el.is_visible():
                        logger.success(f"[TikTok] ✓ Panel komentar terbuka dan terverifikasi via '{vsel}'")
                        verified = True
                        break
                except Exception:
                    continue

            if verified:
                return True

            logger.debug(f"[TikTok] Klik tab berhasil tapi panel belum terverifikasi, coba lagi...")

        logger.warning("[TikTok] Panel komentar tidak berhasil dibuka setelah semua percobaan.")
        return False

    # ============================================================
    # VIDEO: Crawl komentar dari satu video
    # ============================================================

    def _crawl_video_comments(self, video_url: str) -> List[CommentData]:
        """Crawl komentar dari satu URL video TikTok"""
        self.page.goto(video_url, timeout=Config.REQUEST_TIMEOUT)
        random_delay(3, 5)

        # 1. Tekan Escape sekali (pasif) — tidak perlu klik tombol X
        self._dismiss_popups()

        # 2. Langsung klik tab Komentar & buka panel komentar
        panel_opened = self._open_comments_panel()
        if not panel_opened:
            logger.warning(f"[TikTok] Panel komentar tidak terbuka untuk {video_url}, tetap lanjut ekstrak")

        # 3. Scroll untuk load lebih banyak komentar
        self._load_comments()

        return self._extract_comments(video_url)

    def _load_comments(self) -> None:
        """Scroll di dalam panel komentar TikTok untuk load komentar"""
        logger.info("[TikTok] Loading lebih banyak komentar...")
        
        # Cari container yang bisa di-scroll di panel kanan
        container_selectors = [
            '[data-e2e="comment-list-container"]',
            'div[class*="DivCommentListContainer"]',
            '[data-e2e="comment-list"]',
            'div[class*="comment-list-container"]',
        ]
        
        scrollable_sel = None
        for sel in container_selectors:
            try:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    scrollable_sel = sel
                    break
            except Exception: continue

        for _ in range(12):
            if scrollable_sel:
                # Scroll di dalam container spesifik
                self.page.evaluate(
                    f'document.querySelector(`{scrollable_sel}`).scrollBy(0, 800)'
                )
            else:
                # Fallback: Cari div di sisi kanan yang bisa di-scroll
                self.page.evaluate('''() => {
                    const elements = document.querySelectorAll('div');
                    const width = window.innerWidth;
                    for (const el of elements) {
                        const rect = el.getBoundingClientRect();
                        const style = getComputedStyle(el);
                        // Cari element yang berada di 60% sisi kanan layar (panel komentar)
                        if (rect.left > width * 0.4 && 
                            el.scrollHeight > el.clientHeight && 
                            (style.overflowY === 'auto' || style.overflowY === 'scroll' || style.position === 'absolute' || style.position === 'fixed')) {
                            el.scrollBy(0, 800);
                        }
                    }
                }''')
                
            random_delay(1.5, 3.0)

            # Klik "Load more" jika ada
            try:
                load_more = self.page.query_selector('[data-e2e="comment-more-btn"]')
                if load_more and load_more.is_visible():
                    load_more.click(force=True)
                    random_delay(1.0, 2.0)
            except Exception:
                pass

    def _extract_comments(self, video_url: str) -> List[CommentData]:
        """Ekstrak komentar dari halaman video TikTok"""
        comments = []
        logger.info("[TikTok] Mengekstrak komentar...")

        # Coba cari elemen komentar dari container spesifik dulu
        selectors = [
            '[data-e2e="comment-item"]',
            'div[class*="CommentItemContainer"]',
            'div[class*="CommentListItem"]',
            'div[class*="comment-item"]',
            'div[data-e2e="comment-level-1"]',
            'div[class*="DivCommentItem"]',
            'div[class*="CommentItemV2"]',
        ]

        comment_items = []
        for s in selectors:
            try:
                items = self.page.query_selector_all(s)
                if len(items) > 0:
                    logger.debug(f"[TikTok] Ditemukan {len(items)} item via {s}")
                    comment_items = items
                    break
            except Exception:
                continue

        # Fallback: cari di dalam comment-list container saja (bukan seluruh page)
        if not comment_items:
            try:
                container = None
                for csel in ('[data-e2e="comment-list-container"]', '[data-e2e="comment-list"]',
                             'div[class*="DivCommentListContainer"]'):
                    container = self.page.query_selector(csel)
                    if container:
                        break
                if container:
                    # Ambil hanya div langsung yang punya link @username di dalamnya
                    comment_items = container.query_selector_all('div:has(a[href*="/@"])')
                    logger.debug(f"[TikTok] Fallback container: {len(comment_items)} item")
            except Exception:
                pass

        for idx, item in enumerate(comment_items):
            try:
                comment = self._parse_comment_element(item, video_url)
                if comment:
                    comments.append(comment)
            except Exception as e:
                logger.debug(f"[TikTok] Error parse komentar {idx}: {e}")

        logger.info(f"[TikTok] Berhasil ekstrak {len(comments)} komentar valid")
        return comments

    # Daftar nama yang bukan komentar asli (navigasi, UI element, dll.)
    _AUTHOR_BLACKLIST = {
        "profil", "unknown", "tiktok", "lainnya", "saran", "jelajahi",
        "mengikuti", "live", "pesan", "aktivitas", "unggah", "teman",
        "follow", "following", "profile", "explore", "home", "inbox",
        "notification", "more", "creator", "business", "legal",
    }
    # Kata-kata penanda teks navigasi / caption — bukan komentar
    _NAV_PATTERNS = [
        "ketentuan dan kebijakan", "kebijakan privasi", "program kreator",
        "tentang tiktok", "perusahaan", "𝗙𝗼𝗹𝗹𝗼𝘄", "supported by",
        "follow us", "beli sekarang", "shop now",
    ]

    def _parse_comment_element(self, element, video_url: str) -> Optional[CommentData]:
        """Parse elemen komentar TikTok menjadi CommentData.
        Hanya dikembalikan jika: author punya URL /@username valid,
        teks bukan navigasi/caption, dan panjang teks wajar.
        """
        try:
            # ── Author ──────────────────────────────────────────────
            author_name = ""
            author_url  = ""

            author_selectors = [
                '[data-e2e="comment-username-1"]',
                '[data-e2e="comment-username"]',
                '[data-e2e="comment-user-name"]',
                'a[href*="/@"]',
                'span[class*="SpanUserName"]',
                'p[class*="PUserName"]',
            ]
            for s in author_selectors:
                try:
                    author_el = element.query_selector(s)
                    if not author_el:
                        continue
                    name  = author_el.text_content().strip()
                    href  = author_el.get_attribute("href") or ""
                    url   = (
                        f"https://www.tiktok.com{href}" if href.startswith("/")
                        else href if href.startswith("http") else ""
                    )
                    # Wajib: URL mengandung /@  → bukan elemen UI biasa
                    if "/@" in url and name:
                        author_name = name
                        author_url  = url
                        break
                except Exception:
                    continue

            # Validasi author: harus punya URL /@username yang valid
            if not author_name or not author_url or "/@" not in author_url:
                return None
            # Tolak jika nama ada di blacklist (navigasi / UI)
            if author_name.lower() in self._AUTHOR_BLACKLIST:
                return None

            # ── Teks Komentar ────────────────────────────────────────
            comment_text = ""
            text_selectors = [
                '[data-e2e="comment-level-1"]',
                '[data-e2e="comment-text-1"]',
                'p[data-e2e="comment-text"]',
                'span[data-e2e="comment-text-1"]',
                'div[class*="DivCommentText"]',
                'span[class*="SpanCommentText"]',
                'p[class*="PCommentText"]',
            ]
            for s in text_selectors:
                try:
                    text_el = element.query_selector(s)
                    if text_el:
                        t = text_el.inner_text().strip()
                        if t:
                            comment_text = t
                            break
                except Exception:
                    continue

            # Fallback teks: cari p/span yang bukan nama author dan bukan angka
            if not comment_text:
                try:
                    for el in element.query_selector_all("p, span"):
                        t = el.inner_text().strip()
                        if t and t != author_name and len(t) > 3 and not t.isdigit():
                            comment_text = t
                            break
                except Exception:
                    pass

            if not comment_text:
                return None

            # ── Validasi teks komentar ───────────────────────────────
            # 1. Terlalu panjang → kemungkinan caption video (bukan komentar)
            if len(comment_text) > 500:
                logger.debug(f"[TikTok] Skip: teks terlalu panjang ({len(comment_text)} char) → bukan komentar")
                return None
            # 2. Banyak baris → kemungkinan menu navigasi atau caption multi-baris
            newline_count = comment_text.count("\n")
            if newline_count > 5:
                logger.debug(f"[TikTok] Skip: terlalu banyak newline ({newline_count}) → bukan komentar")
                return None
            # 3. Mengandung pola teks navigasi / caption
            lower_text = comment_text.lower()
            for pattern in self._NAV_PATTERNS:
                if pattern.lower() in lower_text:
                    logger.debug(f"[TikTok] Skip: teks mengandung pola nav/caption '{pattern}'")
                    return None

            # ── Likes ────────────────────────────────────────────────
            likes = 0
            try:
                like_el = element.query_selector('[data-e2e="comment-like-count"]')
                if like_el:
                    likes = self._parse_count(like_el.text_content().strip())
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
