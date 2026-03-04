"""Konfigurasi global Backend Multi-Platform Social Media Crawler"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables dari .env
load_dotenv()


class Config:
    """Konfigurasi aplikasi yang dibaca dari file .env"""

    # --- Path ---
    # Root dari project Facebook (satu level di atas folder backend/)
    BASE_DIR = Path(__file__).parent.parent.parent
    COOKIES_DIR = Path(os.getenv("COOKIES_DIR", str(BASE_DIR / "data" / "cookies")))

    # --- Autentikasi ---
    # Tidak ada kredensial tersimpan — semua platform login MANUAL via browser
    # Cookies disimpan otomatis setelah login berhasil


    # --- Browser ---
    HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"
    MIN_DELAY: float = float(os.getenv("MIN_DELAY", "2"))
    MAX_DELAY: float = float(os.getenv("MAX_DELAY", "5"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30000"))
    MAX_SCROLL_ATTEMPTS: int = int(os.getenv("MAX_SCROLL_ATTEMPTS", "10"))

    # --- Crawler ---
    MAX_POSTS_DEFAULT: int = int(os.getenv("MAX_POSTS_DEFAULT", "5"))

    # User-Agent browser
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @classmethod
    def get_cookies_path(cls, platform: str) -> Path:
        """Dapatkan path file cookies berdasarkan nama platform"""
        nama_file = {
            "facebook": "cookies_facebook.json",
            "instagram": "cookies_instagram.json",
            "tiktok": "cookies_tiktok.json",
        }
        return cls.COOKIES_DIR / nama_file.get(platform, f"cookies_{platform}.json")

    @classmethod
    def ensure_directories(cls) -> None:
        """Pastikan semua direktori yang diperlukan sudah ada"""
        cls.COOKIES_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_platform(cls, platform: str) -> bool:
        """Validasi apakah platform yang diminta didukung"""
        return platform in ["facebook", "instagram", "tiktok"]


# Pastikan direktori cookies ada saat modul diimport
Config.ensure_directories()
