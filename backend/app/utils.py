"""Utilitas bersama untuk semua crawler: delay acak, scroll, cookies"""

import json
import time
import random
from pathlib import Path
from typing import List, Optional

from loguru import logger
from playwright.sync_api import Page


def random_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> None:
    """Jeda acak menyerupai perilaku manusia"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def human_like_scroll(page: Page, scroll_amount: int = 500) -> None:
    """
    Scroll halaman menyerupai perilaku manusia.
    Dilakukan secara bertahap dengan variasi kecepatan.
    """
    try:
        # Tutup popup yang mungkin muncul sebelum scroll
        _dismiss_popups(page)

        # Scroll bertahap
        steps = random.randint(3, 6)
        per_step = scroll_amount // steps
        for _ in range(steps):
            actual_amount = per_step + random.randint(-30, 30)
            page.evaluate(f"window.scrollBy(0, {actual_amount})")
            time.sleep(random.uniform(0.1, 0.3))
    except Exception as e:
        logger.debug(f"Error saat scroll: {e}")


def _dismiss_popups(page: Page) -> None:
    """Tutup popup/dialog yang mungkin mengganggu proses crawl"""
    popup_selectors = [
        '[aria-label="Close"]',
        '[aria-label="Tutup"]',
        'div[role="dialog"] button',
        '[data-testid="cookie-policy-manage-dialog-accept-button"]',
    ]
    for selector in popup_selectors:
        try:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                btn.click()
                time.sleep(0.5)
        except Exception:
            continue


def save_cookies(cookies: List[dict], filepath: Path) -> None:
    """Simpan cookies ke file JSON"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        logger.info(f"Cookies disimpan ke: {filepath}")
    except Exception as e:
        logger.error(f"Gagal menyimpan cookies: {e}")


def load_cookies(filepath: Path) -> Optional[List[dict]]:
    """Muat cookies dari file JSON. Return None jika tidak ada."""
    try:
        if not filepath.exists():
            logger.info(f"File cookies tidak ditemukan: {filepath}")
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        logger.info(f"Cookies dimuat dari: {filepath} ({len(cookies)} item)")
        return cookies
    except Exception as e:
        logger.error(f"Gagal memuat cookies: {e}")
        return None


def extract_username_from_url(url: str) -> str:
    """
    Ekstrak username dari URL profil media sosial.

    Contoh:
        https://www.facebook.com/NamaProfil → NamaProfil
        https://www.instagram.com/namaprofil/ → namaprofil
        https://www.tiktok.com/@namaprofil → namaprofil
    """
    try:
        # Hapus trailing slash
        url = url.rstrip("/")

        # TikTok: hapus @ prefix
        if "tiktok.com" in url:
            parts = url.split("/")
            for part in reversed(parts):
                if part.startswith("@"):
                    return part[1:]  # buang '@'
                if part and "tiktok.com" not in part:
                    return part

        # Facebook profile.php?id=XXX
        if "profile.php" in url and "id=" in url:
            return url.split("id=")[-1].split("&")[0]

        # Semua platform lain: ambil segmen terakhir dari URL
        parts = url.split("/")
        for part in reversed(parts):
            if part and part not in [
                "www.facebook.com", "facebook.com",
                "www.instagram.com", "instagram.com",
                "www.tiktok.com", "tiktok.com",
                "http:", "https:"
            ]:
                return part
        return ""
    except Exception as e:
        logger.error(f"Error ekstrak username dari URL: {e}")
        return ""
