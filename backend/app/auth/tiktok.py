"""Autentikasi TikTok menggunakan Playwright"""

from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page
from loguru import logger

from ..config import Config
from ..utils import random_delay, save_cookies, load_cookies


class TikTokAuth:
    """Mengelola autentikasi ke TikTok menggunakan Playwright"""

    def __init__(self):
        self.username = Config.TT_USERNAME
        self.password = Config.TT_PASSWORD
        self.cookies_path = Config.get_cookies_path("tiktok")
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def login(self, browser: Browser) -> Page:
        """
        Login ke TikTok. Prioritas:
        1. Gunakan cookies tersimpan jika masih valid
        2. Login manual via browser yang terbuka (TikTok sulit di-automate)
        """
        logger.info("=== Memulai autentikasi TikTok ===")

        cookies = load_cookies(self.cookies_path)
        if cookies:
            logger.info("Mencoba login TikTok via cookies tersimpan...")
            page = self._login_with_cookies(browser, cookies)
            if page:
                return page
            logger.warning("Cookies TikTok expired. Login ulang...")

        # TikTok sangat ketat soal bot — lebih baik login manual
        return self._login_manual(browser)

    def _login_with_cookies(self, browser: Browser, cookies: list) -> Optional[Page]:
        """Coba login menggunakan cookies tersimpan"""
        try:
            self.context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=Config.USER_AGENT,
            )
            self.context.add_cookies(cookies)
            self.page = self.context.new_page()

            self.page.goto("https://www.tiktok.com", timeout=Config.REQUEST_TIMEOUT)
            random_delay(4, 6)

            if self._is_logged_in():
                logger.success("✓ Login TikTok berhasil via cookies tersimpan")
                return self.page

            self.context.close()
            self.context = None
            self.page = None
            return None

        except Exception as e:
            logger.error(f"Error login TikTok dengan cookies: {e}")
            if self.context:
                self.context.close()
                self.context = None
            return None

    def _login_manual(self, browser: Browser) -> Page:
        """
        Login TikTok secara manual.
        TikTok memiliki proteksi bot yang sangat ketat sehingga
        login otomatis seringkali tidak berhasil. Login manual
        lebih andal dan aman.
        """
        logger.info("Membuka browser untuk login TikTok secara manual...")

        # Paksa headless=False agar user bisa login
        self.context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=Config.USER_AGENT,
        )
        self.page = self.context.new_page()

        try:
            self.page.goto("https://www.tiktok.com/login", timeout=Config.REQUEST_TIMEOUT)

            logger.warning("=" * 60)
            logger.warning("⚠️  LOGIN TIKTOK MANUAL DIPERLUKAN")
            logger.warning("=" * 60)
            logger.warning("1. Browser sudah terbuka di halaman login TikTok")
            logger.warning("2. Login menggunakan akun TikTok Anda")
            logger.warning("3. Tunggu sampai masuk ke halaman beranda TikTok")
            logger.warning("4. JANGAN tutup browser!")
            logger.warning("=" * 60)
            input("👉 Tekan ENTER setelah berhasil login ke TikTok...")

            random_delay(2, 3)

            if self._is_logged_in():
                cookies = self.context.cookies()
                save_cookies(cookies, self.cookies_path)
                logger.success("✓ Login TikTok berhasil! Cookies disimpan.")
                return self.page
            else:
                raise Exception(
                    "Login TikTok gagal — pastikan Anda sudah masuk ke beranda TikTok"
                )

        except Exception as e:
            logger.error(f"Error login TikTok: {e}")
            raise

    def _is_logged_in(self) -> bool:
        """Cek apakah sudah login ke TikTok"""
        try:
            url = self.page.url

            # Kalau di halaman login → belum login
            if "/login" in url:
                return False

            # Cek apakah ada indikator login (avatar/profil icon)
            logged_in_selectors = [
                '[data-e2e="profile-icon"]',
                '[data-e2e="nav-profile"]',
                'a[href*="/@"]',  # Link profil sendiri
            ]
            for selector in logged_in_selectors:
                if self.page.query_selector(selector):
                    return True

            # Fallback: jika di tiktok.com bukan halaman login
            return "tiktok.com" in url and "/login" not in url

        except Exception as e:
            logger.debug(f"Error cek status login TikTok: {e}")
            return False

    def close(self) -> None:
        """Tutup browser context"""
        if self.context:
            self.context.close()
            logger.debug("Browser context TikTok ditutup")
