"""
Facebook Crawler — diadaptasi dari src/profile_crawler.py dan src/crawler.py
Menggunakan Playwright untuk crawl komentar dari profil Facebook.
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from loguru import logger

from .base import BaseCrawler
from ..config import Config
from ..schemas.models import CommentData, CrawlResult
from ..utils import random_delay, human_like_scroll


class FacebookCrawler(BaseCrawler):
    """Crawl komentar dari profil Facebook menggunakan Playwright"""

    PLATFORM = "facebook"

    # Pola URL post Facebook yang valid
    VALID_POST_PATTERNS = ["/posts/", "/story.php", "/permalink.php", "/videos/", "/reel/", "/photo.php"]
    # Pola URL yang BUKAN post individual
    INVALID_URL_PATTERNS = ["/about", "/friends", "/photos", "/groups", "/events", "/watch"]

    def __init__(self, page: Page):
        super().__init__(page)

    # ============================================================
    # PUBLIC API
    # ============================================================

    def crawl_profile(self, target: str, max_posts: int = 5) -> CrawlResult:
        """Crawl komentar dari profil Facebook (username atau URL)"""
        username = self._normalize_target(target)
        profile_url = (
            target if target.startswith("http")
            else f"https://www.facebook.com/{username}"
        )

        logger.info(f"[Facebook] Mulai crawl profil: {profile_url} (max {max_posts} post)")
        logger.info(f"[Facebook] Target username: {username}")

        errors: List[str] = []
        all_comments: List[CommentData] = []

        try:
            # Teruskan username ke fungsi pengambil URL agar bisa filter
            post_urls = self._get_post_urls(profile_url, max_posts, username)
            logger.info(f"[Facebook] Ditemukan {len(post_urls)} post URL dari profil {username}")

            if not post_urls:
                errors.append(f"Tidak ada post ditemukan dari profil '{username}'. Pastikan nama akun benar dan profil publik.")

            for idx, post_url in enumerate(post_urls, 1):
                logger.info(f"[Facebook] Crawl post {idx}/{len(post_urls)}: {post_url}")
                try:
                    comments = self._crawl_post_comments(post_url)
                    all_comments.extend(comments)
                    logger.success(f"[Facebook] ✓ {len(comments)} komentar dari post {idx}")
                except Exception as e:
                    err_msg = f"Gagal crawl post {post_url}: {e}"
                    logger.error(f"[Facebook] {err_msg}")
                    errors.append(err_msg)

        except Exception as e:
            err_msg = f"Error fatal saat crawl profil {profile_url}: {e}"
            logger.error(f"[Facebook] {err_msg}")
            errors.append(err_msg)

        return self._make_result(self.PLATFORM, target, "username", all_comments, errors)

    def crawl_hashtag(self, hashtag: str, max_posts: int = 5) -> CrawlResult:
        """
        Facebook tidak punya halaman hashtag yang crawlable seperti IG.
        Return error informatif.
        """
        logger.warning("[Facebook] Crawl hashtag tidak didukung di Facebook")
        return CrawlResult(
            status="error",
            platform=self.PLATFORM,
            target=hashtag,
            crawl_type="hashtag",
            total_posts_crawled=0,
            total_comments=0,
            comments=[],
            errors=["Crawl hashtag tidak didukung untuk Facebook. Gunakan username/URL profil."],
        )

    # ============================================================
    # PROFILE: Ambil daftar URL post dari profil
    # ============================================================

    def _get_post_urls(self, profile_url: str, max_posts: int, username: str = "") -> List[str]:
        """Navigasi ke profil dan kumpulkan URL post HANYA dari profil target"""
        post_urls: Set[str] = set()
        scroll_count = 0
        no_new_count = 0

        # Navigasi ke profil
        self.page.goto(profile_url, timeout=Config.REQUEST_TIMEOUT)
        random_delay(3, 5)

        # Verifikasi kita benar-benar di halaman profil target
        current_url = self.page.url
        logger.info(f"[Facebook] Landing di: {current_url}")

        # Jika Facebook redirect ke feed/reel/home, navigasikan ulang ke profil
        if self._is_not_profile_page(current_url, username):
            logger.warning(f"[Facebook] Redirect terdeteksi! URL={current_url}, coba navigasi ulang...")
            self.page.goto(profile_url, timeout=Config.REQUEST_TIMEOUT)
            random_delay(4, 6)
            current_url = self.page.url
            logger.info(f"[Facebook] Landing ke-2 di: {current_url}")

        while len(post_urls) < max_posts and scroll_count < Config.MAX_SCROLL_ATTEMPTS:
            prev_count = len(post_urls)
            new_urls = self._extract_post_urls_from_page(username)
            post_urls.update(new_urls)

            logger.debug(f"[Facebook] {len(post_urls)} post URL dari @{username} (scroll {scroll_count + 1})")

            if len(post_urls) >= max_posts:
                break

            if len(post_urls) == prev_count:
                no_new_count += 1
                if no_new_count >= 3:
                    logger.info("[Facebook] Tidak ada post baru, berhenti scroll")
                    break
            else:
                no_new_count = 0

            # Pastikan masih di halaman profil setelah scroll
            current_url = self.page.url
            if self._is_not_profile_page(current_url, username):
                logger.warning(f"[Facebook] Meninggalkan halaman profil ({current_url}), berhenti")
                break

            human_like_scroll(self.page, scroll_amount=600)
            random_delay(2, 4)
            scroll_count += 1

        return list(post_urls)[:max_posts]

    def _is_not_profile_page(self, url: str, username: str = "") -> bool:
        """Kembalikan True jika URL bukan halaman profil target (artinya terjadi redirect)"""
        if "facebook.com" not in url:
            return True
        # Halaman beranda / reel feed umum / watch feed
        bad_urls = [
            "https://www.facebook.com/",
            "https://www.facebook.com",
            "facebook.com/reel/",    # feed reel umum tanpa ID
            "facebook.com/watch",
        ]
        for bad in bad_urls:
            if url.rstrip("/") == bad.rstrip("/"):
                return True
        # Jika username diketahui, pastikan URL mengandung username tsb
        if username and username.lower() not in url.lower():
            # Pengecualian: URL bisa pakai numeric ID seperti profile.php?id=XXX
            if "profile.php" not in url:
                return True
        return False

    def _extract_post_urls_from_page(self, username: str = "") -> List[str]:
        """Ekstrak URL post dari profil target saja — filter by username"""
        post_urls = []
        selectors = [
            'a[href*="/posts/"]',
            'a[href*="/story.php"]',
            'a[href*="/permalink.php"]',
            'a[href*="/videos/"]',
            'a[href*="/reel/"]',
            'a[href*="/photo"]',
        ]

        for selector in selectors:
            try:
                elements = self.page.query_selector_all(selector)
                for el in elements:
                    href = el.get_attribute("href")
                    if not href:
                        continue
                    # Normalisasi URL absolut
                    if href.startswith("/"):
                        href = f"https://www.facebook.com{href}"
                    # Buang query params
                    href = href.split("?")[0]
                    # Validasi URL
                    if self._is_valid_post_url(href, username):
                        post_urls.append(href)
            except Exception as e:
                logger.debug(f"[Facebook] Error ekstrak href: {e}")
                continue

        return list(set(post_urls))

    def _is_valid_post_url(self, url: str, username: str = "") -> bool:
        """
        Validasi URL adalah post yang valid dari profil target.
        
        Rules:
        1. Tidak boleh mengandung pola URL yang tidak valid (tab profil, dll.)
        2. Harus mengandung salah satu pola URL post yang valid
        3. Untuk /reel/ — HARUS ada numeric ID setelah /reel/ (bukan feed reel umum)
        4. Jika username diketahui — URL harus mengandung username ATAU /reel/ID (reel profil)
        """
        # Rule 1: Check invalid patterns
        for invalid in self.INVALID_URL_PATTERNS:
            if invalid in url:
                return False

        # Harus dari facebook.com
        if "facebook.com" not in url:
            return False

        # Rule 3: /reel/ harus diikuti numeric ID
        if "/reel/" in url:
            # Ambil segmen setelah /reel/
            after_reel = url.split("/reel/")[-1].strip("/")
            if not after_reel or not after_reel.isdigit():
                logger.debug(f"[Facebook] Skip URL reel tanpa ID: {url}")
                return False
            # Reel dengan ID valid — boleh dari profil manapun yang ada di halaman profil target
            return True

        # Rule 2: Harus ada pola post yang valid
        if not any(pattern in url for pattern in self.VALID_POST_PATTERNS):
            return False

        # Rule 4: Filter by username jika diketahui
        if username:
            username_lower = username.lower()
            url_lower = url.lower()
            # URL harus mengandung username target
            if username_lower not in url_lower and "profile.php" not in url_lower:
                logger.debug(f"[Facebook] Skip URL bukan milik @{username}: {url}")
                return False

        return True

    # ============================================================
    # POST: Crawl komentar dari satu post
    # ============================================================

    def _crawl_post_comments(self, post_url: str) -> List[CommentData]:
        """
        Crawl komentar dari satu URL post Facebook.
        
        - Post biasa (/posts/, /videos/, dll.) → langsung scroll, komentar sudah tampil
        - Reel (/reel/) → klik icon komentar dulu, baru scroll
        """
        is_reel = "/reel/" in post_url
        post_type = "Reel" if is_reel else "Post"
        logger.info(f"[Facebook] Tipe: {post_type} | {post_url}")

        self.page.goto(post_url, timeout=Config.REQUEST_TIMEOUT)
        random_delay(3, 5)

        post_info = self._extract_post_info()

        if is_reel:
            # Reel: perlu klik tombol komentar dulu untuk membuka panel komentar
            self._open_reel_comments()
        else:
            # Post biasa: komentar sudah langsung tampil, cukup scroll ke bawah
            self._scroll_to_load_comments()

        # Klik 'Lihat selengkapnya' untuk mambuka komentar yang panjang
        self._expand_see_more()

        raw_comments = self._extract_comments()

        comments: List[CommentData] = []
        for raw in raw_comments:
            try:
                comments.append(CommentData(
                    post_url=post_info.get("post_url", post_url),
                    post_author=post_info.get("post_author", ""),
                    comment_author=raw.get("comment_author_name", "Unknown"),
                    comment_author_url=raw.get("comment_author_url", ""),
                    comment_text=raw.get("comment_text", ""),
                    comment_timestamp=raw.get("comment_timestamp", ""),
                    likes_count=raw.get("likes_count", 0),
                    replies_count=raw.get("replies_count", 0),
                    crawled_at=datetime.now().isoformat(),
                ))
            except Exception as e:
                logger.debug(f"[Facebook] Error konversi komentar: {e}")
                continue

        return comments

    def _extract_post_info(self) -> Dict[str, Any]:
        """Ekstrak informasi dasar dari post"""
        info: Dict[str, Any] = {
            "post_url": self.page.url,
            "post_author": "",
            "post_content": "",
        }
        try:
            for sel in ["h2 a", "h3 a", "a[role='link']"]:
                el = self.page.query_selector(sel)
                if el:
                    text = el.text_content().strip()
                    if text:
                        info["post_author"] = text
                        break
        except Exception as e:
            logger.debug(f"[Facebook] Error ekstrak info post: {e}")
        return info

    def _scroll_to_load_comments(self) -> None:
        """
        Post biasa: komentar sudah tampil otomatis.
        Cukup scroll ke bawah untuk load lebih banyak komentar.
        """
        logger.info("[Facebook] Post biasa — scroll untuk load komentar...")
        try:
            scroll_count = min(Config.MAX_SCROLL_ATTEMPTS, 6)  # max 6x scroll
            for i in range(scroll_count):
                human_like_scroll(self.page, scroll_amount=700)
                random_delay(2, 3)
                logger.debug(f"[Facebook] Scroll {i + 1}/{scroll_count}")
        except Exception as e:
            logger.warning(f"[Facebook] Error scroll post: {e}")

    def _open_reel_comments(self) -> None:
        """
        Reel: panel komentar perlu dibuka dulu dengan klik icon komentar.
        Setelah terbuka, scroll untuk load lebih banyak komentar.
        """
        logger.info("[Facebook] Reel — klik icon komentar dulu...")
        try:
            # Selector icon komentar di Reel Facebook
            reel_comment_selectors = [
                '[aria-label*="Comment"]',
                '[aria-label*="Komentar"]',
                'div[role="button"][tabindex="0"] svg',  # icon komentar
                'a[aria-label*="komentar"]',
                'a[aria-label*="comment"]',
            ]

            clicked = False
            for sel in reel_comment_selectors:
                try:
                    btn = self.page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click()
                        random_delay(2, 3)
                        clicked = True
                        logger.info("[Facebook] ✓ Panel komentar reel dibuka")
                        break
                except Exception:
                    continue

            if not clicked:
                logger.warning("[Facebook] Tombol komentar reel tidak ditemukan, langsung scroll")

            # Scroll dalam panel komentar reel
            scroll_count = min(Config.MAX_SCROLL_ATTEMPTS, 6)
            for i in range(scroll_count):
                human_like_scroll(self.page, scroll_amount=500)
                random_delay(2, 3)
                logger.debug(f"[Facebook] Scroll reel {i + 1}/{scroll_count}")

        except Exception as e:
            logger.warning(f"[Facebook] Error buka komentar reel: {e}")

    def _expand_all_comments(self) -> None:
        """[DEPRECATED] Tetap ada untuk backward compatibility"""
        self._scroll_to_load_comments()

    def _open_comment_section(self) -> None:
        """Buka seksi komentar jika tersembunyi"""
        selectors = [
            'text=/View.*comment/i',
            'text=/Lihat.*komentar/i',
            '[aria-label*="comment"]',
            '[aria-label*="Komentar"]',
        ]
        for sel in selectors:
            try:
                btn = self.page.wait_for_selector(sel, timeout=3000)
                if btn and btn.is_visible():
                    btn.click()
                    random_delay(2, 3)
                    return
            except Exception:
                continue

    def _click_view_more_buttons(self) -> None:
        """Klik semua tombol 'Lihat komentar lainnya'"""
        selectors = [
            'text=/View more comments/i',
            'text=/Lihat komentar lainnya/i',
            'text=/View previous comments/i',
            'text=/Lihat komentar sebelumnya/i',
        ]
        for sel in selectors:
            try:
                buttons = self.page.query_selector_all(sel)
                for btn in buttons:
                    if btn.is_visible():
                        btn.click()
                        random_delay(1, 2)
            except Exception:
                continue

    def _expand_replies(self) -> None:
        """Expand semua balasan komentar"""
        selectors = [
            'text=/View.*repl/i',
            'text=/Lihat.*balas/i',
            r'text=/\d+ repl/i',
            r'text=/\d+ balas/i',
        ]
        for sel in selectors:
            try:
                buttons = self.page.query_selector_all(sel)
                for btn in buttons[:50]:
                    if btn.is_visible():
                        btn.scroll_into_view_if_needed()
                        random_delay(0.5, 1)
                        btn.click()
                        random_delay(1, 2)
            except Exception:
                continue

    def _expand_see_more(self) -> None:
        """Klik tombol 'See more' / 'Lihat selengkapnya' di komentar"""
        selectors = [
            'text=/See more/i',
            'text=/Lihat selengkapnya/i',
        ]
        for sel in selectors:
            try:
                buttons = self.page.query_selector_all(sel)
                for btn in buttons:
                    if btn.is_visible():
                        text = btn.text_content().strip().lower()
                        if "see more" in text or "lihat selengkapnya" in text:
                            btn.scroll_into_view_if_needed()
                            btn.click()
                            random_delay(0.3, 0.8)
            except Exception:
                continue

    def _extract_comments(self) -> List[Dict[str, Any]]:
        """Ekstrak semua komentar yang terlihat di halaman"""
        logger.info("[Facebook] Mengekstrak data komentar...")
        comments = []
        random_delay(1, 2)

        selectors = [
            'div[aria-label*="Comment by"]',
            'div[aria-label*="Komentar oleh"]',
            '[role="article"]',
        ]

        elements = []
        for sel in selectors:
            elements = self.page.query_selector_all(sel)
            if elements:
                logger.debug(f"[Facebook] {len(elements)} elemen komentar dengan selector: {sel}")
                break

        for idx, el in enumerate(elements):
            try:
                data = self._parse_comment_element(el)
                if data:
                    data["comment_id"] = f"fb_comment_{idx}"
                    comments.append(data)
            except Exception as e:
                logger.debug(f"[Facebook] Error parse komentar {idx}: {e}")

        logger.info(f"[Facebook] Berhasil ekstrak {len(comments)} komentar")
        return comments

    def _parse_comment_element(self, element) -> Optional[Dict[str, Any]]:
        """Parse satu elemen komentar menjadi dict data"""
        try:
            # Ekstrak nama penulis
            author_name = ""
            author_url = ""
            for sel in ["a[role='link']", "a[href*='/user/']", "a[href*='/profile']", "h4 a", "strong a"]:
                try:
                    link = element.query_selector(sel)
                    if link:
                        text = link.text_content().strip()
                        if text and len(text) > 0:
                            author_name = text
                            author_url = link.get_attribute("href") or ""
                            break
                except Exception:
                    continue

            if not author_name:
                links = element.query_selector_all("a")
                for link in links:
                    text = link.text_content().strip()
                    if text and len(text) > 2 and text not in ["Like", "Reply", "Suka", "Balas"]:
                        author_name = text
                        author_url = link.get_attribute("href") or ""
                        break

            # Ekstrak teks komentar
            comment_text = ""
            for text_el in element.query_selector_all('div[dir="auto"], span[dir="auto"]'):
                text = text_el.text_content().strip()
                if text and len(text) > 5 and text != author_name:
                    if text not in ["Like", "Reply", "Suka", "Balas", "Komentar", "Comment"]:
                        if len(text) > len(comment_text):
                            comment_text = text

            if not comment_text:
                full = element.text_content().strip()
                for noise in [author_name, "Like", "Reply", "Suka", "Balas", "·"]:
                    full = full.replace(noise, "")
                comment_text = full.strip()

            # Bersihkan URL dari teks komentar
            if comment_text:
                comment_text = re.sub(r"https?://\S+", "", comment_text)
                comment_text = re.sub(r"www\.\S+", "", comment_text)
                comment_text = " ".join(comment_text.split()).strip()

            # Skip jika tidak ada data penting
            if not author_name and not comment_text:
                return None
            if len(comment_text) < 2:
                return None

            # Ekstrak timestamp
            timestamp = ""
            for el in element.query_selector_all("a, span"):
                text = el.text_content().strip()
                if len(text) > 50 or text in [author_name, comment_text]:
                    continue
                if re.search(r'\d+\s*(m|h|d|j|w|hari|jam|menit|minggu|bulan|tahun|detik)', text, re.I) or \
                   re.search(r'just now|ago|yang lalu|baru saja', text, re.I):
                    timestamp = text
                    break

            # Ekstrak jumlah likes
            likes = 0
            try:
                for el in element.query_selector_all('[aria-label*="eaction"]'):
                    label = el.get_attribute("aria-label") or ""
                    m = re.search(r"(\d+)", label)
                    if m:
                        likes = int(m.group(1))
                        break
            except Exception:
                pass

            # Ekstrak jumlah balasan
            replies = 0
            try:
                for el in element.query_selector_all('text=/\\d+ repl|\\d+ balas/i'):
                    m = re.search(r"(\d+)", el.text_content())
                    if m:
                        replies = int(m.group(1))
                        break
            except Exception:
                pass

            return {
                "comment_author_name": author_name or "Unknown",
                "comment_author_url": author_url,
                "comment_text": comment_text,
                "comment_timestamp": timestamp,
                "likes_count": likes,
                "replies_count": replies,
            }

        except Exception as e:
            logger.debug(f"[Facebook] Error parse elemen komentar: {e}")
            return None
