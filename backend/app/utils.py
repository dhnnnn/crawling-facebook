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
    """Muat cookies dari file JSON. Mendukung format standar & extension Chrome."""
    try:
        if not filepath.exists():
            logger.info(f"File cookies tidak ditemukan: {filepath}")
            return None
            
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # J2TEAM format terkadang membungkus cookies di dalam object {"url": "...", "cookies": [...]}
        cookies = data.get("cookies", data) if isinstance(data, dict) else data
        
        if not isinstance(cookies, list):
            logger.error(f"Format cookies tidak valid di {filepath}")
            return None

        # Transformasi format extension Chrome (J2TEAM, dsb) ke Playwright
        cleaned_cookies = []
        for c in cookies:
            cookie = {
                "name": c.get("name"),
                "value": c.get("value"),
                "domain": c.get("domain"),
                "path": c.get("path", "/"),
            }
            
            # Playwright butuh 'expires' (int), Chrome extension pakai 'expirationDate' (float)
            if "expirationDate" in c:
                cookie["expires"] = int(c["expirationDate"])
            elif "expires" in c:
                cookie["expires"] = int(c["expires"])
            
            if "httpOnly" in c: cookie["httpOnly"] = c["httpOnly"]
            if "secure" in c: cookie["secure"] = c["secure"]
            
            # SameSite harus: 'Strict', 'Lax', atau 'None'
            if "sameSite" in c:
                val = str(c["sameSite"]).capitalize()
                if val in ["Strict", "Lax", "None"]:
                    cookie["sameSite"] = val
                else:
                    cookie["sameSite"] = "Lax" # Default aman
            
            cleaned_cookies.append(cookie)

        logger.info(f"Cookies dimuat dari: {filepath} ({len(cleaned_cookies)} item)")
        return cleaned_cookies
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
def save_crawl_result(platform: str, crawl_type: str, result) -> None:
    """Save CrawlResult to a JSON file under data/crawling/<platform>/<crawl_type>/ with timestamp.
    crawl_type should be 'comment' or 'hashtag'."""
    try:
        from datetime import datetime
        import json
        from pathlib import Path
        
        # Validasi crawl_type agar folder tertata ('comment' atau 'hashtag')
        c_type = "comment" if crawl_type == "username" else "hashtag"
        
        base_dir = Path(__file__).resolve().parents[2] / "data" / "crawling" / platform.lower() / c_type
        base_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
        filename = f"{platform.lower()}_{timestamp}.json"
        
        file_path = base_dir / filename
        data = result.dict() if hasattr(result, "dict") else result
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"[Utils] Crawl result saved: {file_path}")
    except Exception as e:
        logger.error(f"[Utils] Failed to save crawl result: {e}")


def load_crawl_results(platform: str, crawl_type: str):
    """Load all JSON crawl result files for a platform and crawl_type (Full Data)."""
    try:
        from pathlib import Path
        import json
        
        base_dir = Path(__file__).resolve().parents[2] / "data" / "crawling" / platform.lower() / crawl_type
        if not base_dir.exists():
            return []
            
        results = []
        files = sorted(base_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        for file in files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    results.append(json.load(f))
            except Exception:
                continue
        return results
    except Exception as e:
        logger.error(f"[Utils] Failed to load crawl results: {e}")
        return []


def list_crawl_results_metadata(platform: str, crawl_type: str):
    """List metadata (summary) for all crawl results of a platform and type."""
    try:
        from pathlib import Path
        import json
        
        base_dir = Path(__file__).resolve().parents[2] / "data" / "crawling" / platform.lower() / crawl_type
        if not base_dir.exists():
            return []
            
        metadata_list = []
        files = sorted(base_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        for file in files:
            try:
                # Baca sedikit bagian awal file untuk mendapatkan metadata penting (target, status, crawled_at)
                with open(file, "r", encoding="utf-8") as f:
                    # Bukan cara terefisien tapi paling simpel mengingat struktur JSON
                    data = json.load(f)
                    metadata_list.append({
                        "id": file.name,
                        "target": data.get("target"),
                        "platform": data.get("platform"),
                        "crawl_type": data.get("crawl_type"),
                        "total_comments": data.get("total_comments", 0),
                        "crawled_at": data.get("crawled_at"),
                        "status": data.get("status")
                    })
            except Exception:
                continue
        return metadata_list
    except Exception as e:
        logger.error(f"[Utils] Failed to list crawl metadata: {e}")
        return []


def get_crawl_result_detail(platform: str, crawl_type: str, filename: str):
    """Get full content of a specific crawl result file."""
    try:
        from pathlib import Path
        import json
        
        file_path = Path(__file__).resolve().parents[2] / "data" / "crawling" / platform.lower() / crawl_type / filename
        if not file_path.exists():
            return None
            
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[Utils] Failed to get crawl detail: {e}")
        return None
