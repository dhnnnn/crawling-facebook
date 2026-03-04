"""
Instagram Crawler — crawl komentar dari profil publik dan hashtag.
Menggunakan Playwright dengan autentikasi cookies.
"""

import re
from datetime import datetime
from typing import List, Optional, Set

from playwright.sync_api import Page
from loguru import logger

from .base import BaseCrawler
from ..config import Config
from ..schemas.models import CommentData, CrawlResult
from ..utils import random_delay, human_like_scroll


class InstagramCrawler(BaseCrawler):
    """Crawl komentar dari Instagram menggunakan Playwright"""

    PLATFORM = "instagram"

    def __init__(self, page: Page):
        super().__init__(page)

    # ============================================================
    # PUBLIC API
    # ============================================================

    def crawl_profile(self, target: str, max_posts: int = 5) -> CrawlResult:
        """Crawl komentar dari profil Instagram (username atau URL)"""
        username = self._normalize_target(target)
        profile_url = (
            target if target.startswith("http")
            else f"https://www.instagram.com/{username}/"
        )

        logger.info(f"[Instagram] Crawl profil: {profile_url} (max {max_posts} post)")
        logger.info(f"[Instagram] Target username: @{username}")

        errors: List[str] = []
        all_comments: List[CommentData] = []

        try:
            post_urls = self._get_post_urls_from_profile(profile_url, username, max_posts)
            logger.info(f"[Instagram] Ditemukan {len(post_urls)} post URL dari @{username}")

            for idx, post_url in enumerate(post_urls, 1):
                logger.info(f"[Instagram] Crawl post {idx}/{len(post_urls)}: {post_url}")
                try:
                    comments = self._crawl_post_comments(post_url, username)
                    all_comments.extend(comments)
                    logger.success(f"[Instagram] ✓ {len(comments)} komentar dari post {idx}")
                except Exception as e:
                    err = f"Gagal crawl post {post_url}: {e}"
                    logger.error(f"[Instagram] {err}")
                    errors.append(err)

        except Exception as e:
            err = f"Error fatal: {e}"
            logger.error(f"[Instagram] {err}")
            errors.append(err)

        return self._make_result(self.PLATFORM, target, "username", all_comments, errors)

    def crawl_hashtag(self, hashtag: str, max_posts: int = 5) -> CrawlResult:
        """Crawl komentar dari post-post berdasarkan hashtag Instagram"""
        hashtag = hashtag.lstrip("#")
        hashtag_url = f"https://www.instagram.com/explore/tags/{hashtag}/"

        logger.info(f"[Instagram] Crawl hashtag: #{hashtag} (max {max_posts} post)")

        errors: List[str] = []
        all_comments: List[CommentData] = []
        all_hashtags: List[str] = []  # kumpulkan semua hashtag dari semua post

        try:
            post_urls = self._get_post_urls_from_hashtag(hashtag_url, max_posts)
            logger.info(f"[Instagram] Ditemukan {len(post_urls)} post URL dari #{hashtag}")

            for idx, post_url in enumerate(post_urls, 1):
                logger.info(f"[Instagram] Crawl post {idx}/{len(post_urls)}: {post_url}")
                try:
                    # Buka halaman post, ekstrak hashtag dari caption, lalu komentar
                    is_reel = "/reel/" in post_url
                    self.page.goto(post_url, timeout=Config.REQUEST_TIMEOUT)
                    random_delay(3, 5)
                    self._dismiss_popup()

                    # Ekstrak hashtag dari caption SEBELUM scroll
                    post_tags = self._extract_post_hashtags()
                    all_hashtags.extend(post_tags)
                    logger.info(f"[Instagram] Hashtag di post {idx}: {post_tags}")

                    # Scroll panel komentar
                    if is_reel:
                        self._open_reel_comment_panel()
                    else:
                        self._scroll_post_comments()

                    # Ekstrak komentar
                    comments = self._extract_comments(post_url)
                    # Sisipkan post_hashtags ke setiap komentar dari post ini
                    for c in comments:
                        c.post_hashtags = post_tags
                    all_comments.extend(comments)
                    logger.success(f"[Instagram] ✓ {len(comments)} komentar, {len(post_tags)} hashtag dari post {idx}")
                except Exception as e:
                    err = f"Gagal crawl post {post_url}: {e}"
                    logger.error(f"[Instagram] {err}")
                    errors.append(err)


        except Exception as e:
            err = f"Error fatal hashtag #{hashtag}: {e}"
            logger.error(f"[Instagram] {err}")
            errors.append(err)

        # Buat statistik hashtag (diurutkan dari yang paling sering dipakai)
        hashtag_stats = self._build_hashtag_stats(all_hashtags)
        logger.info(f"[Instagram] Top hashtags: {[h['hashtag'] for h in hashtag_stats[:5]]}")

        result = self._make_result(self.PLATFORM, f"#{hashtag}", "hashtag", all_comments, errors)
        result.hashtag_stats = hashtag_stats
        return result

    def _extract_post_hashtags(self) -> List[str]:
        """
        Ekstrak semua hashtag (#tag) dari caption/deskripsi postingan yang sedang terbuka.
        Hashtag ada di span[dir=auto] di bagian caption (sisi kanan, atas komentar).
        """
        try:
            tags: list = self.page.evaluate("""
                () => {
                    const hashtags = new Set();
                    // Cari semua link yang mengarah ke halaman explore/tags/#hashtag
                    const links = document.querySelectorAll('a[href*="/explore/tags/"]');
                    links.forEach(a => {
                        const href = a.getAttribute('href') || '';
                        const match = href.match(/\\/explore\\/tags\\/([^/]+)\\/?/);
                        if (match && match[1]) {
                            hashtags.add('#' + decodeURIComponent(match[1]).toLowerCase());
                        }
                    });
                    // Juga cari dari teks yang mengandung #hashtag di caption
                    const spans = document.querySelectorAll('span[dir="auto"], div[dir="auto"]');
                    spans.forEach(span => {
                        // Hanya dari sisi kanan viewport (caption area)
                        const rect = span.getBoundingClientRect();
                        if (rect.left < window.innerWidth * 0.4) return;
                        const text = span.textContent || '';
                        const matches = text.match(/#[\\w\\u00C0-\\u024F\\u1E00-\\u1EFF]+/g) || [];
                        matches.forEach(tag => hashtags.add(tag.toLowerCase()));
                    });
                    return [...hashtags];
                }
            """)
            return tags if tags else []
        except Exception as e:
            logger.debug(f"[Instagram] Error ekstrak hashtag: {e}")
            return []

    def _build_hashtag_stats(self, all_hashtags: List[str]) -> list:
        """
        Buat statistik hashtag: hitung frekuensi setiap hashtag,
        urutkan dari yang paling banyak dipakai.
        """
        from collections import Counter
        counter = Counter(all_hashtags)
        return [
            {"hashtag": tag, "count": count}
            for tag, count in counter.most_common()
        ]



    # ============================================================
    # URL COLLECTION
    # ============================================================

    def _get_post_urls_from_profile(
        self, profile_url: str, username: str, max_posts: int
    ) -> List[str]:
        """
        Ambil URL post dari profil Instagram.
        Filter hanya post milik username target.
        """
        self.page.goto(profile_url, timeout=Config.REQUEST_TIMEOUT)
        random_delay(3, 5)
        self._dismiss_popup()

        post_urls: Set[str] = set()
        scroll_count = 0
        no_new_count = 0

        while len(post_urls) < max_posts and scroll_count < Config.MAX_SCROLL_ATTEMPTS:
            prev_count = len(post_urls)

            # Cari URL di dalam grid profil dengan filter username
            new_urls = self._extract_profile_grid_urls(username)
            post_urls.update(new_urls)

            logger.debug(f"[Instagram] {len(post_urls)} URL dari @{username} (scroll {scroll_count + 1})")

            if len(post_urls) >= max_posts:
                break

            if len(post_urls) == prev_count:
                no_new_count += 1
                if no_new_count >= 3:
                    break
            else:
                no_new_count = 0

            human_like_scroll(self.page, scroll_amount=800)
            random_delay(2, 3)
            scroll_count += 1

        return list(post_urls)[:max_posts]

    def _extract_profile_grid_urls(self, username: str) -> List[str]:
        """
        Ekstrak URL post dari grid profil Instagram.
        Hanya ambil URL yang mengandung /p/ atau /reel/ yang berasal dari profil target.
        Instagram reel URL tidak mengandung username, jadi kita hanya ambil
        yang ada di dalam main article/grid (bukan dari sidebar suggestions).
        """
        post_urls = []
        try:
            # Cari dalam <main> atau <article> untuk menghindari sidebar
            # Instagram profile grid: artikel-artikel di dalam main content
            main = self.page.query_selector("main")
            if main:
                links = main.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
            else:
                links = self.page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')

            for link in links:
                href = link.get_attribute("href")
                if not href:
                    continue

                # Normalisasi URL
                if href.startswith("/"):
                    href = f"https://www.instagram.com{href}"
                href = href.split("?")[0].rstrip("/")

                # Validasi: harus ada /p/ atau /reel/ dengan ID
                if not re.search(r'/(p|reel)/[\w-]+$', href):
                    continue

                # Untuk /p/ posts: URL biasanya tidak mengandung username
                # Untuk /reel/: juga tidak mengandung username
                # Kita percaya bahwa link di profile grid adalah milik profil itu
                post_urls.append(href)

        except Exception as e:
            logger.debug(f"[Instagram] Error ekstrak grid URL: {e}")

        return list(set(post_urls))

    def _get_post_urls_from_hashtag(self, hashtag_url: str, max_posts: int) -> List[str]:
        """Ambil URL post dari halaman hashtag Instagram"""
        self.page.goto(hashtag_url, timeout=Config.REQUEST_TIMEOUT)
        random_delay(3, 5)
        self._dismiss_popup()

        post_urls: Set[str] = set()
        scroll_count = 0
        no_new_count = 0

        while len(post_urls) < max_posts and scroll_count < Config.MAX_SCROLL_ATTEMPTS:
            prev_count = len(post_urls)
            new_urls = self._extract_profile_grid_urls("")
            post_urls.update(new_urls)

            if len(post_urls) >= max_posts:
                break
            if len(post_urls) == prev_count:
                no_new_count += 1
                if no_new_count >= 3:
                    break
            else:
                no_new_count = 0

            human_like_scroll(self.page, scroll_amount=800)
            random_delay(2, 3)
            scroll_count += 1

        return list(post_urls)[:max_posts]

    # ============================================================
    # POST: Crawl komentar dari satu post
    # ============================================================

    def _crawl_post_comments(self, post_url: str, username: str = "") -> List[CommentData]:
        """
        Crawl komentar dari satu URL post Instagram.
        - Post biasa (/p/) → sudah ada di sidebar kiri, scroll panel komentar
        - Reel (/reel/) → perlu klik icon komentar dulu
        """
        is_reel = "/reel/" in post_url
        logger.info(f"[Instagram] Tipe: {'Reel' if is_reel else 'Post'} | {post_url}")

        self.page.goto(post_url, timeout=Config.REQUEST_TIMEOUT)
        random_delay(3, 5)
        self._dismiss_popup()

        if is_reel:
            self._open_reel_comment_panel()
        else:
            self._scroll_post_comments()

        return self._extract_comments(post_url)

    def _scroll_post_comments(self) -> None:
        """
        Post biasa: panel komentar ada di sisi kanan.
        Hover mouse ke area kanan lalu wheel scroll agar scroll panel komentar,
        bukan halaman utama.
        """
        logger.info("[Instagram] Post — mouse wheel di panel komentar kanan...")
        self._scroll_comment_panel_by_mouse(scroll_times=6)
        self._click_load_more_comments()

    def _open_reel_comment_panel(self) -> None:
        """
        Reel: panel komentar sudah tampil di sisi kanan tanpa perlu klik.
        Hover mouse ke panel kanan lalu wheel scroll untuk load lebih banyak komentar.
        JANGAN scroll halaman utama (nanti turun ke postingan rekomendasi).
        """
        logger.info("[Instagram] Reel — mouse wheel di panel komentar kanan...")
        random_delay(1, 2)
        self._scroll_comment_panel_by_mouse(scroll_times=10)
        self._click_load_more_comments()

    def _scroll_comment_panel_by_mouse(self, scroll_times: int = 8) -> None:
        """
        Scroll panel komentar Instagram dengan mensimulasikan mouse wheel.
        
        Caranya:
        1. Dapatkan ukuran viewport
        2. Hover mouse ke x = 75% lebar (panel kanan), y = 50% tinggi (tengah)
        3. Putar mouse wheel ke bawah
        
        Ini jauh lebih reliable daripada mencari selector DOM karena
        Instagram sering mengubah class name-nya.
        """
        try:
            viewport = self.page.viewport_size
            if not viewport:
                viewport = {"width": 1280, "height": 720}

            # Panel komentar ada di sisi kanan — x sekitar 65-80% viewport
            panel_x = int(viewport["width"] * 0.72)
            # Posisi y di tengah-tengah area komentar (bukan header, bukan footer)
            panel_y = int(viewport["height"] * 0.55)

            logger.debug(f"[Instagram] Mouse di ({panel_x}, {panel_y}) untuk scroll panel komentar")

            # Hover ke panel komentar
            self.page.mouse.move(panel_x, panel_y)
            random_delay(1, 2)

            # Wheel scroll lebih pelan agar komentar sempat di-render
            for i in range(scroll_times):
                self.page.mouse.wheel(0, 400)  # lebih kecil dari 600
                random_delay(2.0, 3.0)  # jeda lebih panjang antar scroll
                logger.debug(f"[Instagram] Wheel scroll {i + 1}/{scroll_times}")

                # Berhenti jika sudah menemukan marker "Postingan lainnya dari ..."
                # yang menandakan komentar sudah habis
                if self._is_end_of_comments():
                    logger.info(f"[Instagram] ✓ Komentar habis setelah scroll {i + 1}, berhenti")
                    break

        except Exception as e:
            logger.warning(f"[Instagram] Error mouse wheel scroll: {e}")
            # Fallback ke JS jika mouse wheel gagal
            self._js_scroll_right_panel()

    def _js_scroll_right_panel(self) -> None:
        """Fallback: scroll div scrollable di sisi kanan via JavaScript"""
        try:
            self.page.evaluate("""
                () => {
                    // Cari semua elemen scrollable di sisi kanan viewport (x > 50%)
                    const all = document.querySelectorAll('*');
                    let best = null, maxScore = 0;
                    all.forEach(el => {
                        const rect = el.getBoundingClientRect();
                        const scrollable = el.scrollHeight > el.clientHeight + 50;
                        const onRight = rect.left > window.innerWidth * 0.45;
                        const hasHeight = el.clientHeight > 200;
                        if (scrollable && onRight && hasHeight) {
                            const score = el.clientHeight;
                            if (score > maxScore) { maxScore = score; best = el; }
                        }
                    });
                    if (best) best.scrollBy(0, 600);
                }
            """)
        except Exception as e:
            logger.debug(f"[Instagram] JS fallback scroll error: {e}")

    def _is_end_of_comments(self) -> bool:
        """
        Deteksi apakah sudah mencapai akhir section komentar.
        Instagram menampilkan 'Postingan lainnya dari [username]' saat
        komentar habis dan mulai menampilkan rekomendasi postingan lain.
        """
        try:
            result = self.page.evaluate("""
                () => {
                    const markers = [
                        'Postingan lainnya dari',
                        'More posts from',
                        'Lihat Postingan Lainnya',
                    ];
                    const allText = document.body.innerText || '';
                    return markers.some(m => allText.includes(m));
                }
            """)
            return bool(result)
        except Exception:
            return False

    def _find_comment_panel(self):
        """Deprecated — replaced by mouse wheel scroll"""
        return None


    def _click_load_more_comments(self) -> None:
        """Klik 'Load more comments' jika ada"""
        for sel in [
            'button:has-text("Load more")',
            'button:has-text("Muat lebih")',
            'span:has-text("Load more comments")',
        ]:
            try:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    random_delay(2, 3)
            except Exception:
                continue

    def _extract_comments(self, post_url: str) -> List[CommentData]:
        """
        Ekstrak komentar Instagram menggunakan JavaScript evaluate.
        Jalankan JS langsung di browser untuk traverse DOM — lebih reliable
        daripada Playwright selector karena Instagram pakai obfuscated CSS classes.
        """
        logger.info("[Instagram] Mengekstrak komentar via JS...")

        try:
            raw_comments: list = self.page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();

                    // Pattern UI yang harus di-skip
                    const UI_PATTERNS = [
                        /^\\d+\\s*(s|m|h|d|w|jam|menit|detik|hari|minggu|bulan|tahun|mng|min|det|jm|hr)\\b/i,
                        /^\\d+\\s*(second|minute|hour|day|week|month|year)s?\\s*(ago)?$/i,
                        /^\\d+\\s*(suka|like|likes?)$/i,           // "5 suka", "18 likes"
                        /komentar dari (facebook|instagram)/i,
                        /comments? from (facebook|instagram)/i,
                        /masuk untuk menyukai/i,
                        /^(like|reply|suka|balas|view|muat|load|more|lainnya|lihat|hide|sembunyikan|privasi|api|logout|masuk|daftar|ikuti|follow|meta|tentang|blog|pekerjaan|bantuan|ketentuan|lokasi|bahasa)$/i,
                    ];

                    function isUIText(text) {
                        if (!text || text.trim().length < 3) return true;
                        const t = text.trim();
                        return UI_PATTERNS.some(p => p.test(t));
                    }

                    // Validasi format username Instagram: alphanum, underscore, titik
                    // Contoh valid: rusdi_sutejo, user.name123, john_doe
                    // Contoh invalid: "3 lainnya", "PostinganBaru", "# " 
                    function isValidUsername(name) {
                        if (!name || name.length < 1 || name.length > 60) return false;
                        if (name.includes(' ')) return false;  // ada spasi = bukan username
                        if (!/^[a-zA-Z0-9._]+$/.test(name)) return false;  // harus alphanumeric/._
                        // Harus ada huruf (bukan hanya angka/titik)
                        if (!/[a-zA-Z]/.test(name)) return false;
                        return true;
                    }

                    const profileLinks = document.querySelectorAll('a[href]');

                    profileLinks.forEach(a => {
                        try {
                            const href = a.getAttribute('href') || '';

                            // Skip href # (non-profile link) dan link kosong
                            if (!href || href === '#' || href === '/' || href.startsWith('#')) return;

                            // Harus pola /username/ — tidak ada slash kedua dalam path
                            const clean = href.replace(/^\\//, '').replace(/\\/$/, '');
                            if (!clean || clean.includes('/')) return;

                            // Skip nama navigasi yang umum
                            const navItems = ['explore', 'stories', 'reels', 'direct', 'accounts',
                                              'about', 'jobs', 'help', 'terms', 'privacy', 'locations',
                                              'meta', 'lite', 'threads', 'ai'];
                            if (navItems.includes(clean.toLowerCase())) return;

                            const authorName = a.textContent.trim();
                            if (!isValidUsername(authorName)) return;

                            // *** KEY FIX: link harus di sisi kanan viewport (panel komentar) ***
                            const rect = a.getBoundingClientRect();
                            if (rect.left < window.innerWidth * 0.4) return;  // sidebar kiri → skip
                            // CATATAN: rect.top TIDAK dicek karena komentar yg sudah di-scroll
                            // ke atas viewport tetap valid (sudah di DOM tapi tidak terlihat)

                            // Cari span[dir=auto] di ancestor terdekat (naik max 8 level)
                            let container = a.parentElement;
                            let commentText = '';
                            let depth = 0;

                            while (container && depth < 8) {
                                const spans = container.querySelectorAll('span[dir="auto"]');
                                for (const span of spans) {
                                    // Span juga harus di sisi kanan
                                    const spanRect = span.getBoundingClientRect();
                                    if (spanRect.left < window.innerWidth * 0.4) continue;

                                    const txt = span.textContent.trim();
                                    if (txt && txt !== authorName && !isUIText(txt) && txt.length > 2) {
                                        if (!span.querySelector('a')) {
                                            commentText = txt;
                                            break;
                                        }
                                    }
                                }
                                if (commentText) break;
                                container = container.parentElement;
                                depth++;
                            }

                            if (!commentText) return;

                            const key = authorName + '::' + commentText;
                            if (seen.has(key)) return;
                            seen.add(key);

                            results.push({
                                author: authorName,
                                author_url: 'https://www.instagram.com/' + clean + '/',
                                text: commentText,
                            });
                        } catch(e) {}
                    });

                    return results;
                }
            """)

            if not raw_comments:
                logger.warning("[Instagram] JS strategi 1 tidak menemukan komentar, coba strategi 2...")
                raw_comments = self._extract_by_js_spans(post_url)

            comments = []
            for raw in raw_comments:
                try:
                    comments.append(CommentData(
                        post_url=post_url,
                        post_author="",
                        comment_author=raw.get("author", "Unknown"),
                        comment_author_url=raw.get("author_url", ""),
                        comment_text=raw.get("text", ""),
                        comment_timestamp="",
                        likes_count=0,
                        replies_count=0,
                        crawled_at=datetime.now().isoformat(),
                    ))
                except Exception:
                    continue

            logger.info(f"[Instagram] Berhasil ekstrak {len(comments)} komentar")
            return comments

        except Exception as e:
            logger.error(f"[Instagram] Error ekstrak komentar: {e}")
            return []

    def _extract_by_js_spans(self, post_url: str) -> list:
        """
        Strategi 2 — JS fallback: ambil span[dir=auto] di sisi kanan viewport.
        Filter ketat: timestamp, likes count, kata UI.
        Minimum panjang 8 karakter agar tidak ikut tombol UI.
        """
        try:
            return self.page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();
                    const UI_PATTERNS = [
                        /^\\d+\\s*(s|m|h|d|w|jam|menit|detik|hari|minggu|bulan|tahun|mng|min|det|jm|hr)\\b/i,
                        /^\\d+\\s*(suka|like|likes?)$/i,
                        /komentar dari/i,
                        /^(like|reply|suka|balas|view|muat|load|more|privasi|api|masuk|daftar)$/i,
                    ];

                    function isUI(t) {
                        return !t || t.length < 8 || UI_PATTERNS.some(p => p.test(t));
                    }

                    // Hanya dari sisi kanan viewport (panel komentar)
                    const spans = document.querySelectorAll('span[dir="auto"]');
                    spans.forEach(span => {
                        const rect = span.getBoundingClientRect();
                        if (rect.left < window.innerWidth * 0.4) return;  // kiri, skip
                        // Untuk fallback, TIDAK cek rect.top karena komentar sudah di-scroll
                        const text = span.textContent.trim();
                        if (isUI(text) || seen.has(text)) return;
                        seen.add(text);
                        results.push({ author: 'Unknown', author_url: '', text });
                    });

                    return results;
                }
            """)
        except Exception as e:
            logger.debug(f"[Instagram] JS spans fallback error: {e}")
            return []

    def _dismiss_popup(self) -> None:
        """Tutup popup Instagram: notifikasi, simpan login, dsb."""
        for sel in [
            'button:has-text("Not Now")',
            'button:has-text("Nanti")',
            'button:has-text("Skip")',
            '[aria-label="Close"]',
            '[aria-label="Tutup"]',
        ]:
            try:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    random_delay(0.5, 1)
                    return
            except Exception:
                continue



    def _extract_by_profile_link_pattern(self, post_url: str) -> List[CommentData]:
        """
        Strategi 1: Cari pola <a href="/username/"> diikuti span[dir="auto"].
        Ini pola standar komentar Instagram:
          <li> atau <div>
            <a href="/username/">username</a>
            <span dir="auto">teks komentar</span>
          </li>
        """
        comments = []
        seen = set()
        try:
            # Ambil semua link yang mengarah ke profil (format /username/)
            profile_links = self.page.query_selector_all(
                'a[href^="/"]:not([href*="/p/"]):not([href*="/reel/"]):not([href*="/explore/"]):not([href*="/accounts/"]):not([href="/"])'
            )

            for link in profile_links:
                try:
                    href = link.get_attribute("href") or ""
                    # Harus format /username/ — tepat 2 slash
                    clean_href = href.strip("/")
                    if not clean_href or "/" in clean_href:
                        continue  # bukan profil, skip (contoh /explore/tags/foo/)

                    author_name = link.text_content().strip()
                    if not author_name or len(author_name) > 60:
                        continue

                    # Cari span[dir="auto"] yang berdekatan (sibling atau parent > span)
                    comment_text = ""
                    parent = link.evaluate_handle("el => el.closest('li, div[role=\"listitem\"], div._a9zm, div._a9zr')")
                    if parent:
                        spans = parent.query_selector_all('span[dir="auto"]')
                        for span in spans:
                            txt = span.text_content().strip()
                            if txt and txt != author_name and not self._is_ui_text(txt) and len(txt) > 2:
                                comment_text = txt
                                break

                    if not comment_text:
                        continue

                    key = f"{author_name}::{comment_text}"
                    if key in seen:
                        continue
                    seen.add(key)

                    Author_url = f"https://www.instagram.com/{clean_href}/"
                    comments.append(CommentData(
                        post_url=post_url,
                        post_author="",
                        comment_author=author_name,
                        comment_author_url=Author_url,
                        comment_text=comment_text,
                        comment_timestamp="",
                        likes_count=0,
                        replies_count=0,
                        crawled_at=datetime.now().isoformat(),
                    ))

                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"[Instagram] Error strategi 1: {e}")

        return comments

    def _extract_by_ul_skip_caption(self, post_url: str) -> List[CommentData]:
        """
        Strategi 2: Ambil <ul> terbesar, skip <li> pertama (caption pemilik post),
        parse sisanya sebagai komentar. Filter ketat elemen UI.
        """
        comments = []
        try:
            uls = self.page.query_selector_all("ul")
            best_ul = None
            best_count = 0
            for ul in uls:
                count = len(ul.query_selector_all("li"))
                if count > best_count:
                    best_count = count
                    best_ul = ul

            if not best_ul or best_count < 2:
                return []

            items = best_ul.query_selector_all("li")
            # Skip item pertama (biasanya caption dari pemilik post)
            for item in list(items)[1:]:
                try:
                    # Cari link profil
                    links = item.query_selector_all(
                        'a[href^="/"]:not([href*="/p/"]):not([href*="/reel/"])'
                    )
                    author_name = ""
                    author_url = ""
                    for link in links:
                        href = (link.get_attribute("href") or "").strip("/")
                        if href and "/" not in href:
                            name = link.text_content().strip()
                            if name and len(name) <= 60:
                                author_name = name
                                author_url = f"https://www.instagram.com/{href}/"
                                break

                    # Cari teks komentar
                    comment_text = ""
                    spans = item.query_selector_all('span[dir="auto"]')
                    for span in spans:
                        txt = span.text_content().strip()
                        if txt and txt != author_name and not self._is_ui_text(txt) and len(txt) > 2:
                            comment_text = txt
                            break

                    if not comment_text:
                        # Fallback: ambil seluruh teks item, buang author + timestamp
                        full = item.text_content().strip()
                        full = full.replace(author_name, "").strip()
                        # Buang timestamp di awal/akhir
                        full = re.sub(r'\d+\s*(jam|menit|hari|detik|minggu|bulan)\s*(yang lalu)?', '', full)
                        full = " ".join(full.split()).strip()
                        if full and not self._is_ui_text(full) and len(full) > 3:
                            comment_text = full

                    if not comment_text:
                        continue

                    comments.append(CommentData(
                        post_url=post_url,
                        post_author="",
                        comment_author=author_name or "Unknown",
                        comment_author_url=author_url,
                        comment_text=comment_text,
                        comment_timestamp="",
                        likes_count=0,
                        replies_count=0,
                        crawled_at=datetime.now().isoformat(),
                    ))

                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"[Instagram] Error strategi 2: {e}")

        return comments

    def _dismiss_popup(self) -> None:
        """Tutup popup Instagram: notifikasi, simpan login, dsb."""
        for sel in [
            'button:has-text("Not Now")',
            'button:has-text("Nanti")',
            'button:has-text("Skip")',
            '[aria-label="Close"]',
            '[aria-label="Tutup"]',
        ]:
            try:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    random_delay(0.5, 1)
                    return
            except Exception:
                continue
