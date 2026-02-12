"""Facebook authentication module using Playwright"""

import json
from pathlib import Path
from typing import Optional
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from loguru import logger

from .config import Config
from .utils import random_delay, save_cookies, load_cookies


class FacebookAuth:
    """Handle Facebook authentication"""
    
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        self.email = email or Config.FB_EMAIL
        self.password = password or Config.FB_PASSWORD
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    def login(self, browser: Browser, use_saved_cookies: bool = True) -> Page:
        """
        Login to Facebook using credentials or saved cookies
        
        Args:
            browser: Playwright browser instance
            use_saved_cookies: Whether to try loading saved cookies first
            
        Returns:
            Authenticated page
        """
        logger.info("Starting Facebook authentication...")
        
        # Try to load saved cookies first
        if use_saved_cookies:
            cookies = load_cookies()
            if cookies:
                logger.info("Loading saved cookies...")
                # Create context with cookies already loaded
                self.context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                self.context.add_cookies(cookies)
                self.page = self.context.new_page()
                
                # Navigate and check login
                self.page.goto("https://www.facebook.com", timeout=Config.REQUEST_TIMEOUT)
                random_delay(3, 5)  # Give more time for Facebook to recognize cookies
                
                # Check if still logged in
                if self._is_logged_in():
                    logger.success("Successfully authenticated using saved cookies")
                    return self.page
                else:
                    logger.warning("Saved cookies expired, proceeding with fresh login...")
                    # Close current context and create new one
                    self.context.close()
                    self.context = None
                    self.page = None
        
        # Create browser context for fresh login
        if not self.context:
            self.context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
        
        # Perform fresh login
        if not self.page:
            self.page = self.context.new_page()
        
        return self._perform_login()
    
    def _perform_login(self) -> Page:
        """Perform actual login with credentials"""
        logger.info("Performing login with credentials...")
        
        try:
            # Navigate to Facebook
            self.page.goto("https://www.facebook.com", timeout=Config.REQUEST_TIMEOUT)
            random_delay(2, 3)
            
            # Check if already on login page or need to click login button
            if self.page.query_selector('input[name="email"]'):
                logger.debug("Already on login page")
            else:
                logger.debug("Looking for login form...")
            
            # Fill email
            email_input = self.page.wait_for_selector(
                'input[name="email"]',
                timeout=10000
            )
            email_input.fill(self.email)
            random_delay(1, 2)
            
            # Fill password
            password_input = self.page.query_selector('input[name="pass"]')
            if password_input:
                password_input.fill(self.password)
                random_delay(1, 2)
            
            # Click login button
            login_button = self.page.query_selector('button[name="login"]')
            if not login_button:
                login_button = self.page.query_selector('button[type="submit"]')
            
            if login_button:
                login_button.click()
                logger.info("Login button clicked, waiting for response...")
                
                # Wait for navigation
                try:
                    self.page.wait_for_load_state("networkidle", timeout=30000)
                    random_delay(3, 5)
                except Exception as e:
                    logger.warning(f"Network idle timeout: {e}")
                    random_delay(3, 5)
                
                # CRITICAL: Check for challenge FIRST before declaring success
                # Challenge pages can look like "logged in" but aren't
                if self._check_for_captcha():
                    logger.warning("=" * 60)
                    logger.warning("⚠️  CHALLENGE/CAPTCHA TERDETEKSI!")
                    logger.warning("=" * 60)
                    logger.warning("Facebook meminta verifikasi tambahan.")
                    logger.warning("Silakan selesaikan challenge di browser:")
                    logger.warning("1. Klik tombol 'Mulai' atau selesaikan verifikasi")
                    logger.warning("2. Tunggu sampai masuk ke Facebook homepage")
                    logger.warning("3. Jangan close browser!")
                    logger.warning("=" * 60)
                    input("👉 Press ENTER setelah challenge selesai...")
                    
                    # Wait for navigation to complete after challenge
                    logger.info("Menunggu navigasi ke homepage...")
                    try:
                        # Wait for URL to change from challenge page
                        self.page.wait_for_url(lambda url: '/checkpoint/' not in url and '/authentication/' not in url, timeout=10000)
                        random_delay(3, 5)
                    except Exception as e:
                        logger.warning(f"Timeout menunggu navigasi: {e}")
                        random_delay(2, 3)
                    
                    # Re-check login after challenge with retries
                    logger.info("Memverifikasi status login...")
                    max_retries = 3
                    for attempt in range(max_retries):
                        logger.debug(f"Attempt {attempt + 1}/{max_retries}")
                        
                        is_logged_in = self._is_logged_in()
                        has_challenge = self._check_for_captcha()
                        
                        logger.debug(f"  - is_logged_in: {is_logged_in}")
                        logger.debug(f"  - has_challenge: {has_challenge}")
                        logger.debug(f"  - current_url: {self.page.url}")
                        
                        if is_logged_in and not has_challenge:
                            cookies = self.context.cookies()
                            save_cookies(cookies)
                            logger.success("✓ Login berhasil setelah menyelesaikan challenge!")
                            return self.page
                        
                        if attempt < max_retries - 1:
                            logger.debug(f"  - Retry dalam 3 detik...")
                            random_delay(2, 4)
                    
                    logger.error("✗ Login verification gagal setelah challenge.")
                    logger.error("Tips: Pastikan Anda sudah di homepage Facebook (bukan halaman verifikasi)")
                    raise Exception("Facebook login failed after challenge")
                
                # Now check if login successful (no challenge present)
                if self._is_logged_in():
                    logger.success("Login successful!")
                    
                    # Save cookies for future use
                    cookies = self.context.cookies()
                    save_cookies(cookies)
                    
                    return self.page
                else:
                    logger.warning("=" * 60)
                    logger.warning("⚠️  AUTOMATED LOGIN GAGAL!")
                    logger.warning("=" * 60)
                    logger.warning("Login otomatis tidak berhasil (mungkin password salah atau diblokir).")
                    logger.warning("Karena browser sedang terbuka (Headless=False):")
                    logger.warning("1. Silakan login secara MANUAL di jendela browser yang terbuka.")
                    logger.warning("2. Pastikan sudah masuk ke Beranda/Home Facebook.")
                    logger.warning("3. JANGAN tutup browsernya.")
                    logger.warning("=" * 60)
                    input("👉 Press ENTER setelah Anda berhasil login secara manual...")
                    
                    # Re-verify after manual login
                    if self._is_logged_in():
                        logger.success("✓ Login berhasil (verifikasi manual)!")
                        cookies = self.context.cookies()
                        save_cookies(cookies)
                        return self.page
                    else:
                        logger.error("✗ Verifikasi gagal. Pastikan Anda sudah login.")
                        raise Exception("Facebook login failed")
            else:
                logger.error("Login button not found")
                # Fallback to manual if form is there but button isn't found
                logger.warning("Mencoba fallback manual karena tombol login tidak ditemukan...")
                input("👉 Silakan login manual lalu press ENTER...")
                if self._is_logged_in():
                    return self.page
                raise Exception("Login button not found and manual fallback failed")
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise
    
    def _is_logged_in(self) -> bool:
        """Check if currently logged in to Facebook (and NOT on a challenge page)"""
        try:
            # Wait a bit for page to fully load
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                pass  # Continue even if timeout
            
            # CRITICAL: If there's a challenge, we're NOT logged in yet
            current_url = self.page.url
            challenge_url_patterns = ['/checkpoint/', '/two_step_verification/', '/authentication/']
            for pattern in challenge_url_patterns:
                if pattern in current_url.lower():
                    logger.debug(f"Challenge URL detected: {pattern} - NOT logged in")
                    return False
            
            # Check for login form - if present, we're not logged in
            login_form = self.page.query_selector('input[name="email"]')
            if login_form:
                logger.debug("Login form detected - not logged in")
                return False
            
            # Check URL - if on login page, not logged in
            if "login" in current_url.lower():
                logger.debug(f"Login page detected: {current_url}")
                return False
            
            # If we're on facebook.com and no login form, WE ARE LOGGED IN
            # Removed selector checking - it's unreliable across languages/regions
            # and causes 20+ second delays trying selectors that don't exist
            if "facebook.com" in current_url:
                logger.info("✓ On facebook.com without login form or challenge - LOGGED IN")
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False
    
    def _check_for_captcha(self) -> bool:
        """Check if CAPTCHA or challenge verification is present"""
        try:
            current_url = self.page.url
            logger.debug(f"Checking for challenge on URL: {current_url}")
            
            # CRITICAL: Check URL first - most reliable
            # Facebook challenge/verification pages have specific URL patterns
            challenge_patterns = [
                '/checkpoint/',
                '/two_step_verification/',
                '/authentication/'
            ]
            
            for pattern in challenge_patterns:
                if pattern in current_url.lower():
                    logger.info(f"Challenge page detected via URL: {pattern}")
                    return True
            
            # Traditional CAPTCHA selectors
            captcha_selectors = [
                'iframe[title*="captcha"]',
                'iframe[title*="CAPTCHA"]',
                'div[id*="captcha"]',
                'div[class*="captcha"]'
            ]
            
            for selector in captcha_selectors:
                if self.page.query_selector(selector):
                    logger.info(f"CAPTCHA detected via selector: {selector}")
                    return True
            
            # REMOVED: Text-based detection - causes FALSE POSITIVES!
            # Words like "verify", "verification" appear in normal homepage content
            # (ads, post warnings, email verification prompts, etc.)
            
            logger.debug("No challenge detected")
            return False
        except Exception as e:
            logger.error(f"Error checking for CAPTCHA: {e}")
            return False
    
    def close(self) -> None:
        """Close browser context"""
        if self.context:
            self.context.close()
            logger.info("Browser context closed")
