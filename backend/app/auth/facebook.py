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
        self.cookies_path = Config.get_cookies_path("facebook")
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def login(self, browser: Browser) -> Page:
        """
        Login ke Facebook. Prioritas:
        1. Gunakan cookies yang tersimpan jika masih valid
        2. Login manual via browser (user login sendiri)
        """
        logger.info("=== Memulai autentikasi Facebook ===")

        # Coba load cookies yang sudah ada
        cookies = load_cookies(self.cookies_path)
        if cookies:
            logger.info("Mencoba login menggunakan cookies tersimpan...")
            page = self._login_with_cookies(browser, cookies)
            if page:
                return page

            # Cookies expired — beri instruksi jelas
            logger.warning("=" * 60)
            logger.warning("🔴 COOKIES FACEBOOK SUDAH EXPIRED!")
            logger.warning("=" * 60)
            logger.warning("Cookies lama tidak valid, perlu login ulang.")
            logger.warning("Jika ada proses crawl lain yang sedang berjalan,")
            logger.warning("HENTIKAN SERVER dulu (Ctrl+C) lalu jalankan ulang.")
            logger.warning("=" * 60)

        # Login manual — browser terbuka, user login sendiri
        return self._login_manual(browser)


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

    def _login_manual(self, browser: Browser) -> Page:
        """
        Login Facebook secara manual — sama seperti Instagram.
        Browser dibuka agar user bisa login sendiri,
        cookies disimpan otomatis setelah berhasil.
        """
        logger.warning("=" * 60)
        logger.warning("⚠️  LOGIN FACEBOOK MANUAL DIPERLUKAN")
        logger.warning("=" * 60)
        logger.warning("Silakan login manual di browser yang akan terbuka:")
        logger.warning("  1. Browser terbuka di halaman Facebook")
        logger.warning("  2. Masukkan email/password atau gunakan metode lain")
        logger.warning("  3. Tunggu sampai masuk ke beranda Facebook")
        logger.warning("  4. JANGAN tutup browser!")
        logger.warning("=" * 60)

        self.context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=Config.USER_AGENT,
        )
        self.page = self.context.new_page()

        try:
            self.page.goto("https://www.facebook.com/login/", timeout=Config.REQUEST_TIMEOUT)
            random_delay(2, 3)

            input("👉 Tekan ENTER setelah berhasil login ke beranda Facebook...")

            random_delay(2, 3)

            # Tunggu sampai benar-benar di beranda
            try:
                self.page.wait_for_url(
                    lambda url: (
                        "facebook.com" in url
                        and "/login" not in url
                        and "/checkpoint" not in url
                    ),
                    timeout=15000,
                )
                logger.info(f"✓ URL sekarang: {self.page.url}")
            except Exception:
                logger.warning(f"Timeout redirect, URL saat ini: {self.page.url}")

            random_delay(2, 3)

            # Simpan cookies selama URL bukan halaman login
            current_url = self.page.url
            if "/login" not in current_url and "/checkpoint" not in current_url:
                cookies = self.context.cookies()
                save_cookies(cookies, self.cookies_path)
                logger.success("✓ Cookies Facebook tersimpan ke cookies_facebook.json")
                logger.info(f"   Total cookies: {len(cookies)}")
                logger.info("   Sesi berikutnya akan otomatis menggunakan cookies tersimpan.")
                return self.page
            else:
                raise Exception(
                    f"Login Facebook gagal. URL saat ini: {current_url}. "
                    "Pastikan sudah masuk ke beranda Facebook sebelum tekan Enter."
                )

        except Exception as e:
            logger.error(f"Error login Facebook manual: {e}")
            raise



    def _is_logged_in(self) -> bool:
        """
        Cek apakah saat ini sudah login ke Facebook.
        
        Facebook terkadang membuka halaman profil publik meski belum login
        sambil menampilkan popup login — URL tetap facebook.com/username.
        Perlu cek elemen UI untuk memastikan benar-benar sudah login.
        """
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

            # Cek halaman login eksplisit
            if "login" in current_url.lower():
                return False

            if "facebook.com" not in current_url:
                return False

            # Cek kehadiran form login (termasuk popup/modal di atas halaman profil)
            # Facebook menampilkan ini walau URL = facebook.com/username saat belum login
            login_indicators = [
                'input[name="email"]',
                'input[name="pass"]',
                'input[placeholder*="Email"]',
                'input[placeholder*="Nomor Telepon"]',
                'input[placeholder*="Phone"]',
                'form[data-testid="royal_login_form"]',
                '[data-testid="royal_login_form"]',
                # Tombol Masuk/Login di bagian atas halaman
                'a[href*="/login/"]',
            ]
            for sel in login_indicators:
                try:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        logger.debug(f"[FB] Ditemukan elemen login: {sel} — belum login")
                        return False
                except Exception:
                    continue

            # Cek indikator sudah login: avatar/profile di navbar atas
            logged_in_indicators = [
                '[aria-label="Akun Anda"]',
                '[aria-label="Your account"]',
                '[aria-label="Profil"]',
                '[data-testid="nav-small-profile-link"]',
            ]
            for sel in logged_in_indicators:
                try:
                    el = self.page.query_selector(sel)
                    if el:
                        logger.debug(f"[FB] Indikator login: {sel} ✓")
                        return True
                except Exception:
                    continue

            # Jika tidak ada form login dan ada di facebook.com → asumsi login
            # (merupakan fallback jika selector berubah)
            logger.debug("[FB] Tidak ada form login terdeteksi, anggap sudah login")
            return True

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
