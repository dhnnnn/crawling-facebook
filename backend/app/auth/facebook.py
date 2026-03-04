"""Autentikasi Facebook — adaptasi dari src/auth.py yang sudah ada"""

import json
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page
from loguru import logger

from ..config import Config
from ..utils import random_delay, save_cookies, load_cookies


class FacebookAuth:
    """Mengelola autentikasi ke Facebook menggunakan Playwright"""

    def __init__(self):
        self.email = Config.FB_EMAIL
        self.password = Config.FB_PASSWORD
        self.cookies_path = Config.get_cookies_path("facebook")
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def login(self, browser: Browser) -> Page:
        """
        Login ke Facebook. Prioritas:
        1. Gunakan cookies yang tersimpan jika masih valid
        2. Login otomatis dengan email/password
        
        Returns:
            Page yang sudah terautentikasi
        """
        logger.info("=== Memulai autentikasi Facebook ===")

        # Coba load cookies yang sudah ada
        cookies = load_cookies(self.cookies_path)
        if cookies:
            logger.info("Mencoba login menggunakan cookies tersimpan...")
            page = self._login_with_cookies(browser, cookies)
            if page:
                return page
            logger.warning("Cookies expired atau tidak valid. Login ulang...")

        # Login otomatis dengan kredensial
        if not self.email or not self.password:
            raise ValueError(
                "FB_EMAIL dan FB_PASSWORD harus diisi di file .env "
                "untuk dapat login ke Facebook."
            )

        return self._login_with_credentials(browser)

    def _login_with_cookies(self, browser: Browser, cookies: list) -> Optional[Page]:
        """Coba login menggunakan cookies yang tersimpan"""
        try:
            self.context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=Config.USER_AGENT,
            )
            self.context.add_cookies(cookies)
            self.page = self.context.new_page()

            self.page.goto("https://www.facebook.com", timeout=Config.REQUEST_TIMEOUT)
            random_delay(3, 5)

            if self._is_logged_in():
                logger.success("✓ Login Facebook berhasil via cookies tersimpan")
                return self.page

            # Cookies tidak valid, bersihkan context
            self.context.close()
            self.context = None
            self.page = None
            return None

        except Exception as e:
            logger.error(f"Error saat login dengan cookies: {e}")
            if self.context:
                self.context.close()
                self.context = None
            return None

    def _login_with_credentials(self, browser: Browser) -> Page:
        """Login otomatis menggunakan email dan password"""
        logger.info("Login menggunakan kredensial (email/password)...")

        self.context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=Config.USER_AGENT,
        )
        self.page = self.context.new_page()

        try:
            self.page.goto("https://www.facebook.com", timeout=Config.REQUEST_TIMEOUT)
            random_delay(2, 3)

            # Isi email
            email_input = self.page.wait_for_selector('input[name="email"]', timeout=10000)
            email_input.fill(self.email)
            random_delay(1, 2)

            # Isi password
            pass_input = self.page.query_selector('input[name="pass"]')
            if pass_input:
                pass_input.fill(self.password)
                random_delay(1, 2)

            # Klik tombol login
            login_btn = self.page.query_selector('button[name="login"]') or \
                        self.page.query_selector('button[type="submit"]')
            if login_btn:
                login_btn.click()
                logger.info("Tombol login diklik, menunggu respons...")

                try:
                    self.page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass
                random_delay(3, 5)

                # Cek challenge/CAPTCHA
                if self._has_challenge():
                    logger.warning("⚠️  Challenge terdeteksi! Selesaikan secara manual di browser.")
                    input("👉 Tekan ENTER setelah menyelesaikan verifikasi...")
                    random_delay(2, 3)

                if self._is_logged_in():
                    cookies = self.context.cookies()
                    save_cookies(cookies, self.cookies_path)
                    logger.success("✓ Login Facebook berhasil! Cookies disimpan.")
                    return self.page
                else:
                    raise Exception("Login Facebook gagal — cek email/password di .env")
            else:
                raise Exception("Tombol login tidak ditemukan")

        except Exception as e:
            logger.error(f"Error login Facebook: {e}")
            raise

    def _is_logged_in(self) -> bool:
        """Cek apakah saat ini sudah login ke Facebook"""
        try:
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass

            current_url = self.page.url

            # Cek URL challenge
            for pattern in ["/checkpoint/", "/two_step_verification/", "/authentication/"]:
                if pattern in current_url.lower():
                    return False

            # Cek halaman login
            if "login" in current_url.lower():
                return False
            if self.page.query_selector('input[name="email"]'):
                return False

            # Jika di facebook.com dan tidak ada form login → sudah login
            return "facebook.com" in current_url

        except Exception as e:
            logger.debug(f"Error cek status login: {e}")
            return False

    def _has_challenge(self) -> bool:
        """Cek apakah ada halaman verifikasi/CAPTCHA"""
        try:
            url = self.page.url
            for pattern in ["/checkpoint/", "/two_step_verification/", "/authentication/"]:
                if pattern in url.lower():
                    return True
            return False
        except Exception:
            return False

    def close(self) -> None:
        """Tutup browser context"""
        if self.context:
            self.context.close()
            logger.debug("Browser context Facebook ditutup")
