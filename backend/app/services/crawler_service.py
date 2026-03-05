"""
Crawler Service — fungsi-fungsi SYNCHRONOUS per platform.
Dipanggil dari routes menggunakan asyncio.to_thread() agar tidak
memblokir asyncio event loop FastAPI.
"""

from playwright.sync_api import sync_playwright, Browser
from loguru import logger

from ..config import Config
from ..schemas.models import CrawlResult
from ..auth.facebook import FacebookAuth
from ..auth.instagram import InstagramAuth
from ..auth.tiktok import TikTokAuth
from ..crawlers.facebook import FacebookCrawler
from ..crawlers.instagram import InstagramCrawler
from ..crawlers.tiktok import TikTokCrawler
from ..utils import save_crawl_result


# ============================================================
# FACEBOOK
# ============================================================

def crawl_facebook_profile(target: str, max_posts: int) -> CrawlResult:
    """Crawl Facebook profil (sync) — dipanggil via asyncio.to_thread()"""
    logger.info(f"[Service:FB] Crawl profil | target={target}, max_posts={max_posts}")
    with sync_playwright() as p:
        # Facebook: non-headless agar login manual bisa berjalan jika cookies expired
        browser = p.chromium.launch(headless=False)
        try:
            auth = FacebookAuth()
            page = auth.login(browser)
            crawler = FacebookCrawler(page)
            result = crawler.crawl_profile(target, max_posts)
            save_crawl_result("facebook", "username", result)
            logger.success(f"[Service:FB] Selesai — {result.total_comments} komentar")
            return result
        except Exception as e:
            logger.error(f"[Service:FB] Error: {e}")
            return _error_result("facebook", target, "username", str(e))
        finally:
            browser.close()



# ============================================================
# INSTAGRAM
# ============================================================

def crawl_instagram_profile(target: str, max_posts: int) -> CrawlResult:
    """Crawl Instagram profil (sync) — dipanggil via asyncio.to_thread()"""
    logger.info(f"[Service:IG] Crawl profil | target={target}, max_posts={max_posts}")
    with sync_playwright() as p:
        # Instagram: selalu non-headless agar login manual bisa berjalan
        browser = p.chromium.launch(headless=False)
        try:
            auth = InstagramAuth()
            page = auth.login(browser)
            crawler = InstagramCrawler(page)
            result = crawler.crawl_profile(target, max_posts)
            save_crawl_result("instagram", "username", result)
            logger.success(f"[Service:IG] Selesai — {result.total_comments} komentar")
            return result
        except Exception as e:
            logger.error(f"[Service:IG] Error: {e}")
            return _error_result("instagram", target, "username", str(e))
        finally:
            browser.close()


def crawl_instagram_hashtag(hashtag: str, max_posts: int) -> CrawlResult:
    """Crawl Instagram hashtag (sync) — dipanggil via asyncio.to_thread()"""
    hashtag = hashtag.lstrip("#")
    logger.info(f"[Service:IG] Crawl hashtag | #{hashtag}, max_posts={max_posts}")
    with sync_playwright() as p:
        # Instagram: selalu non-headless agar login manual bisa berjalan
        browser = p.chromium.launch(headless=False)
        try:
            auth = InstagramAuth()
            page = auth.login(browser)
            crawler = InstagramCrawler(page)
            result = crawler.crawl_hashtag(hashtag, max_posts)
            save_crawl_result("instagram", "hashtag", result)
            logger.success(f"[Service:IG] Selesai — {result.total_comments} komentar")
            return result
        except Exception as e:
            logger.error(f"[Service:IG] Error: {e}")
            return _error_result("instagram", f"#{hashtag}", "hashtag", str(e))
        finally:
            browser.close()



# ============================================================
# TIKTOK
# ============================================================

def crawl_tiktok_profile(target: str, max_posts: int) -> CrawlResult:
    """Crawl TikTok profil (sync) — dipanggil via asyncio.to_thread()"""
    logger.info(f"[Service:TT] Crawl profil | target={target}, max_posts={max_posts}")
    with sync_playwright() as p:
        # Tambahkan stealth args untuk menghindari CAPTCHA/bot detection
        browser = p.chromium.launch(
            headless=Config.HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
            ]
        )
        try:
            # Kita tidak lagi pakai TikTokAuth.login() yang interaktif
            # TikTokCrawler akan menangani loading cookies secara internal
            crawler = TikTokCrawler(browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=Config.USER_AGENT
            ).new_page())
            
            result = crawler.crawl_profile(target, max_posts)
            save_crawl_result("tiktok", "username", result)
            logger.success(f"[Service:TT] Selesai — {result.total_comments} komentar")
            return result
        except Exception as e:
            logger.error(f"[Service:TT] Error: {e}")
            return _error_result("tiktok", target, "username", str(e))
        finally:
            browser.close()


def crawl_tiktok_hashtag(hashtag: str, max_posts: int) -> CrawlResult:
    """Crawl TikTok hashtag (sync) — dipanggil via asyncio.to_thread()"""
    hashtag = hashtag.lstrip("#")
    logger.info(f"[Service:TT] Crawl hashtag | #{hashtag}, max_posts={max_posts}")
    with sync_playwright() as p:
        # Tambahkan stealth args
        browser = p.chromium.launch(
            headless=Config.HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
            ]
        )
        try:
            crawler = TikTokCrawler(browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=Config.USER_AGENT
            ).new_page())
            
            result = crawler.crawl_hashtag(hashtag, max_posts)
            save_crawl_result("tiktok", "hashtag", result)
            logger.success(f"[Service:TT] Selesai — {result.total_comments} komentar")
            return result
        except Exception as e:
            logger.error(f"[Service:TT] Error: {e}")
            return _error_result("tiktok", f"#{hashtag}", "hashtag", str(e))
        finally:
            browser.close()


# ============================================================
# HELPER
# ============================================================

def _error_result(platform: str, target: str, crawl_type: str, error: str) -> CrawlResult:
    """Buat CrawlResult dengan status error"""
    from datetime import datetime
    return CrawlResult(
        status="error",
        platform=platform,
        target=target,
        crawl_type=crawl_type,
        total_posts_crawled=0,
        total_comments=0,
        comments=[],
        crawled_at=datetime.now().isoformat(),
        errors=[error],
    )
