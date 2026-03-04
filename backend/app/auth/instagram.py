"""
Autentikasi Instagram menggunakan Playwright.

Instagram memiliki proteksi anti-bot yang sangat ketat sehingga
login otomatis seringkali diblokir. Strategi:
  1. Coba pakai cookies tersimpan (cookies_instagram.json)
  2. Jika tidak ada / expired → buka browser non-headless untuk LOGIN MANUAL
     (user login sendiri, cookies disimpan otomatis untuk sesi berikutnya)
"""

from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page
from loguru import logger

from ..config import Config
from ..utils import random_delay, save_cookies, load_cookies


class InstagramAuth:
    """Mengelola autentikasi ke Instagram menggunakan Playwright"""

    def __init__(self):
        self.cookies_path = Config.get_cookies_path("instagram")
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def login(self, browser: Browser) -> Page:
        """
        Login ke Instagram.
        1. Coba cookies tersimpan
        2. Jika gagal → login manual via browser
        """
        logger.info("=== Memulai autentikasi Instagram ===")

        cookies = load_cookies(self.cookies_path)
        if cookies:
            logger.info("Mencoba login Instagram via cookies tersimpan...")
            page = self._login_with_cookies(browser, cookies)
            if page:
                return page
            logger.warning("Cookies Instagram expired, perlu login ulang...")

        # Instagram blokir automated login, gunakan login manual
        return self._login_manual(browser)

    def _login_with_cookies(self, browser: Browser, cookies: list) -> Optional[Page]:
        """Coba login menggunakan cookies tersimpan"""
        try:
            self.context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=Config.USER_AGENT,
            )
            self.context.add_cookies(cookies)
            self.page = self.context.new_page()

            self.page.goto("https://www.instagram.com", timeout=Config.REQUEST_TIMEOUT)
            random_delay(3, 5)

            if self._is_logged_in():
                logger.success("✓ Login Instagram berhasil via cookies tersimpan")
                return self.page

            logger.warning("Cookies Instagram tidak valid")
            self.context.close()
            self.context = None
            self.page = None
            return None

        except Exception as e:
            logger.error(f"Error login Instagram dengan cookies: {e}")
            if self.context:
                self.context.close()
                self.context = None
            return None

    def _login_manual(self, browser: Browser) -> Page:
        """
        Login Instagram secara manual.
        Browser dibuka dalam mode VISIBLE (non-headless) agar user bisa login.
        Cookies disimpan otomatis setelah login berhasil.
        """
        logger.info("Membuka browser untuk login Instagram secara manual...")
        logger.warning("=" * 60)
        logger.warning("⚠️  LOGIN INSTAGRAM MANUAL DIPERLUKAN")
        logger.warning("=" * 60)
        logger.warning("Instagram memblokir login otomatis (anti-bot)")
        logger.warning("Silakan login manual di browser yang akan terbuka:")
        logger.warning("  1. Browser terbuka di halaman login Instagram")
        logger.warning("  2. Masukkan username/password atau Login dengan Facebook")
        logger.warning("  3. Tunggu sampai masuk ke beranda Instagram")
        logger.warning("  4. JANGAN tutup browser!")
        logger.warning("=" * 60)

        # Paksa non-headless agar user bisa interaksi
        non_headless_browser = browser._impl_obj._connection._transport._proc  # noqa
        # Buat context baru (headless=False akan diatur via browser yang sudah di-launch)
        self.context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=Config.USER_AGENT,
        )
        self.page = self.context.new_page()

        try:
            self.page.goto(
                "https://www.instagram.com/accounts/login/",
                timeout=Config.REQUEST_TIMEOUT,
            )

            input("👉 Tekan ENTER setelah berhasil login (setelah halaman onetap/simpan info login muncul atau langsung ke beranda)...")

            # Auto-dismiss halaman /accounts/onetap/ (Simpan Info Login)
            # Instagram menampilkan halaman ini sebelum redirect ke beranda
            random_delay(2, 3)
            self._dismiss_onetap()

            # Tunggu URL menjadi instagram.com (beranda)
            logger.info("Menunggu redirect ke beranda Instagram...")
            try:
                self.page.wait_for_url(
                    lambda url: (
                        "instagram.com" in url
                        and "/accounts/" not in url
                    ),
                    timeout=15000,
                )
                logger.info(f"✓ URL sekarang: {self.page.url}")
            except Exception:
                logger.warning(f"Timeout redirect, URL saat ini: {self.page.url}")

            random_delay(2, 3)

            if self._is_logged_in():
                cookies = self.context.cookies()
                save_cookies(cookies, self.cookies_path)
                logger.success("✓ Login Instagram berhasil! Cookies disimpan ke cookies_instagram.json")
                logger.info("   Sesi berikutnya akan otomatis menggunakan cookies tersimpan.")
                return self.page
            else:
                current_url = self.page.url
                raise Exception(
                    f"Login Instagram gagal. URL saat ini: {current_url}. "
                    "Pastikan Anda sudah benar-benar masuk ke beranda Instagram sebelum tekan Enter."
                )

        except Exception as e:
            logger.error(f"Error login Instagram manual: {e}")
            raise


    def _dismiss_onetap(self) -> None:
        """
        Dismiss halaman 'Simpan Info Login' (onetap).
        Instagram menampilkan /accounts/onetap/ setelah login berhasil,
        sebelum redirect ke beranda.
        """
        try:
            current_url = self.page.url
            if "/accounts/onetap" in current_url or "/accounts/login" in current_url:
                # Klik 'Not Now' / 'Nanti' untuk skip
                for sel in [
                    'button:has-text("Not Now")',
                    'button:has-text("Nanti")',
                    'button:has-text("Nanti Saja")',
                    'div[role="button"]:has-text("Not Now")',
                ]:
                    try:
                        btn = self.page.query_selector(sel)
                        if btn and btn.is_visible():
                            btn.click()
                            random_delay(2, 3)
                            logger.info(f"✓ Halaman onetap di-dismiss, URL: {self.page.url}")
                            return
                    except Exception:
                        continue
                logger.debug("Tombol dismiss onetap tidak ditemukan")
        except Exception as e:
            logger.debug(f"Error dismiss onetap: {e}")

    def _is_logged_in(self) -> bool:
        """
        Cek apakah sudah login ke Instagram.
        Login = URL adalah instagram.com tanpa path /accounts/
        """
        try:
            pages = self.context.pages
            for page in pages:
                url = page.url
                if "instagram.com" not in url:
                    continue
                # Semua path /accounts/* dianggap belum login (login flow)
                if "/accounts/" in url:
                    continue
                # Halaman instagram.com valid — sudah login
                logger.info(f"Login terdeteksi di: {url}")
                self.page = page  # Update ke page yang aktif
                return True
            return False
        except Exception as e:
            logger.debug(f"Error cek status login Instagram: {e}")
            return False


    def close(self) -> None:
        """Tutup browser context"""
        if self.context:
            self.context.close()
            logger.debug("Browser context Instagram ditutup")
