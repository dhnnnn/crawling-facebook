"""Core comment crawler for Facebook posts"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from loguru import logger

from .config import Config
from .utils import random_delay, human_like_scroll, parse_facebook_date


class CommentCrawler:
    """Crawl comments from Facebook posts"""
    
    def __init__(self, page: Page):
        self.page = page
        self.comments_data: List[Dict[str, Any]] = []
    
    def crawl_post_comments(
        self, 
        post_url: str,
        max_comments: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Crawl all comments from a Facebook post
        
        Args:
            post_url: URL of the Facebook post
            max_comments: Maximum number of comments to crawl (None for all)
            
        Returns:
            List of comment dictionaries
        """
        logger.info(f"Crawling comments from: {post_url}")
        
        try:
            # Navigate to post
            self.page.goto(post_url, timeout=Config.REQUEST_TIMEOUT)
            random_delay(3, 5)
            
            # Get post information
            post_info = self._extract_post_info()
            
            # Expand all comments
            self._expand_all_comments(max_comments)
            
            # Extract comments
            comments = self._extract_comments(post_info)
            
            logger.success(f"Extracted {len(comments)} comments from post")
            return comments
            
        except Exception as e:
            logger.error(f"Error crawling post {post_url}: {e}")
            return []
    
    def _extract_post_info(self) -> Dict[str, Any]:
        """Extract basic post information"""
        post_info = {
            'post_url': self.page.url,
            'post_author': '',
            'post_content': '',
            'post_timestamp': ''
        }
        
        try:
            # Try to extract post author
            author_selectors = [
                'h2 a',
                'h3 a',
                '[data-ad-preview="message"] a',
                'a[role="link"]'
            ]
            
            for selector in author_selectors:
                element = self.page.query_selector(selector)
                if element:
                    post_info['post_author'] = element.text_content().strip()
                    if post_info['post_author']:
                        break
            
            # Try to extract post content
            content_selectors = [
                '[data-ad-preview="message"]',
                'div[data-ad-comet-preview="message"]',
                '[dir="auto"]'
            ]
            
            for selector in content_selectors:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    text = element.text_content().strip()
                    if text and len(text) > len(post_info['post_content']):
                        post_info['post_content'] = text
                        break
                if post_info['post_content']:
                    break
            
            # Limit content length
            if len(post_info['post_content']) > 500:
                post_info['post_content'] = post_info['post_content'][:500] + '...'
            
            logger.debug(f"Post info: author={post_info['post_author']}, content_length={len(post_info['post_content'])}")
            
        except Exception as e:
            logger.warning(f"Could not extract post info: {e}")
        
        return post_info
    
    def _open_comment_section(self) -> bool:
        """Open comment section if it's collapsed/hidden"""
        try:
            # Try to find and click "View comments" button
            comment_button_selectors = [
                'text=/View.*comment/i',
                'text=/Lihat.*komentar/i',
                '[aria-label*="comment"]',
                '[aria-label*="Comment"]',
                '[aria-label*="Komentar"]',
                'div[role="button"]:has-text("Comment")',
                'div[role="button"]:has-text("Komentar")'
            ]
            
            for selector in comment_button_selectors:
                try:
                    button = self.page.wait_for_selector(selector, timeout=3000)
                    if button and button.is_visible():
                        logger.info(f"Clicking comment button: {selector}")
                        button.click()
                        random_delay(2, 3)
                        return True
                except:
                    continue
            
            # If no button found, comments might already be visible
            logger.debug("No comment button found - comments may already be visible")
            return False
            
        except Exception as e:
            logger.warning(f"Error opening comment section: {e}")
            return False
    
    def _expand_all_comments(self, max_comments: Optional[int] = None) -> None:
        """Expand all comments and replies"""
        logger.info("Expanding comments...")
        
        try:
            # First, try to open comment section if collapsed
            self._open_comment_section()
            random_delay(1, 2)
            
            # Scroll to load more comments
            scroll_attempts = 0
            max_scrolls = Config.MAX_SCROLL_ATTEMPTS
            
            while scroll_attempts < max_scrolls:
                # Scroll down (utils.py now handles popup detection automatically)
                human_like_scroll(self.page, scroll_amount=600)
                random_delay(2, 3)
                
                # Try to click "View more comments" buttons
                more_comments_clicked = self._click_view_more_buttons()
                
                scroll_attempts += 1
                
                # If we have max_comments set and reached it, stop
                if max_comments:
                    current_count = self._count_visible_comments()
                    if current_count >= max_comments:
                        logger.info(f"Reached target of {max_comments} comments")
                        break
                
                # If no more buttons to click and scrolled enough, stop
                if not more_comments_clicked and scroll_attempts > 5:
                    logger.info("No more comments to load")
                    break
            
            # Expand all replies
            self._expand_all_replies()
            
            # CRITICAL: Expand truncated comment text (See more buttons)
            self._expand_see_more_in_comments()
            
        except Exception as e:
            logger.warning(f"Error expanding comments: {e}")
    
    def _click_view_more_buttons(self) -> bool:
        """Click all 'View more comments' type buttons"""
        clicked = False
        
        try:
            # Selectors for "view more" buttons (both English and Indonesian)
            selectors = [
                'text=/View more comments/i',
                'text=/Lihat komentar lainnya/i',
                'text=/View previous comments/i',
                'text=/Lihat komentar sebelumnya/i',
                '[aria-label*="more comment"]',
                '[aria-label*="komentar lainnya"]'
            ]
            
            for selector in selectors:
                try:
                    buttons = self.page.query_selector_all(selector)
                    for button in buttons:
                        try:
                            if button.is_visible():
                                button.click()
                                clicked = True
                                random_delay(1, 2)
                        except Exception:
                            continue
                except Exception:
                    continue
            
        except Exception as e:
            logger.debug(f"Error clicking view more buttons: {e}")
        
        return clicked
    
    def _expand_all_replies(self) -> None:
        """Expand all reply threads"""
        logger.info("Expanding reply threads...")
        
        try:
            # Selectors for "view replies" buttons
            selectors = [
                'text=/View.*repl/i',
                'text=/Lihat.*balas/i',
                'text=/\\d+ repl/i',
                'text=/\\d+ balas/i',
                '[aria-label*="repl"]',
                '[aria-label*="balas"]'
            ]
            
            for selector in selectors:
                try:
                    buttons = self.page.query_selector_all(selector)
                    for button in buttons[:50]:  # Limit to avoid infinite loops
                        try:
                            if button.is_visible():
                                button.scroll_into_view_if_needed()
                                random_delay(0.5, 1)
                                button.click()
                                random_delay(1, 2)
                        except Exception:
                            continue
                except Exception:
                    continue
            
        except Exception as e:
            logger.debug(f"Error expanding replies: {e}")
    
    def _expand_see_more_in_comments(self) -> None:
        """Click 'See more'/'Lihat selengkapnya' buttons to expand truncated comment text"""
        logger.info("Expanding truncated comments (See more buttons)...")
        
        try:
            # Selectors for "see more" / "lihat selengkapnya" buttons
            see_more_selectors = [
                'text=/See more/i',
                'text=/Lihat selengkapnya/i',
                'div[role="button"]:has-text("See more")',
                'div[role="button"]:has-text("Lihat selengkapnya")',
                '[aria-label*="See more"]',
                '[aria-label*="Lihat selengkapnya"]'
            ]
            
            expanded_count = 0
            
            for selector in see_more_selectors:
                try:
                    buttons = self.page.query_selector_all(selector)
                    logger.debug(f"Found {len(buttons)} 'See more' buttons with selector: {selector}")
                    
                    for button in buttons:
                        try:
                            # Check if button is visible and contains see more text
                            if button.is_visible():
                                button_text = button.text_content().strip()
                                # Only click if it's actually a "see more" button
                                if any(text in button_text.lower() for text in ['see more', 'lihat selengkapnya']):
                                    button.scroll_into_view_if_needed()
                                    random_delay(0.3, 0.6)
                                    button.click()
                                    expanded_count += 1
                                    random_delay(0.5, 1)
                        except Exception as e:
                            logger.debug(f"Error clicking see more button: {e}")
                            continue
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            logger.info(f"Expanded {expanded_count} truncated comments")
            
        except Exception as e:
            logger.warning(f"Error expanding see more buttons: {e}")
    
    def _count_visible_comments(self) -> int:
        """Count currently visible comments"""
        try:
            # Count comment containers
            comment_selectors = [
                '[role="article"]',
                'div[aria-label*="Comment"]',
                'div[aria-label*="Komentar"]'
            ]
            
            for selector in comment_selectors:
                comments = self.page.query_selector_all(selector)
                if comments:
                    return len(comments)
            
            return 0
        except Exception:
            return 0
    
    def _extract_comments(self, post_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all visible comments"""
        logger.info("Extracting comment data...")
        comments = []
        
        try:
            # Wait for comments to load
            random_delay(1, 2)
            
            # Try multiple selectors for comment elements
            # Facebook structure varies between posts, reels, photos, etc.
            comment_selectors = [
                # Most specific - actual comment containers
                'div[aria-label*="Comment by"]',
                'div[aria-label*="Komentar oleh"]',
                # Comment containers with role
                'div[role="article"] div[dir="auto"]',
                # Fallback - any article that contains comment-like structure
                '[role="article"]'
            ]
            
            comment_elements = []
            for selector in comment_selectors:
                elements = self.page.query_selector_all(selector)
                if elements:
                    logger.debug(f"Found {len(elements)} elements with selector: {selector}")
                    comment_elements = elements
                    break
            
            logger.info(f"Found {len(comment_elements)} potential comment elements")
            
            if len(comment_elements) == 0:
                # Try to capture page HTML for debugging
                logger.warning("No comment elements found. Page URL: " + self.page.url)
            
            for idx, element in enumerate(comment_elements):
                try:
                    comment_data = self._extract_single_comment(element, post_info)
                    if comment_data:
                        comment_data['comment_id'] = f"comment_{idx}"
                        comments.append(comment_data)
                except Exception as e:
                    logger.debug(f"Error extracting comment {idx}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error extracting comments: {e}")
        
        return comments
    
    def _extract_single_comment(
        self, 
        element, 
        post_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract data from a single comment element"""
        try:
            # Extract author name - try multiple selectors
            author_name = ""
            author_url = ""
            
            # Try different selectors for author
            author_selectors = [
                'a[role="link"]',
                'a[href*="/user/"]',
                'a[href*="/profile"]',
                'a[aria-label]',
                'span[dir="auto"] a',
                'h4 a',
                'strong a'
            ]
            
            for selector in author_selectors:
                try:
                    author_link = element.query_selector(selector)
                    if author_link:
                        text = author_link.text_content().strip()
                        if text and len(text) > 0:
                            author_name = text
                            author_url = author_link.get_attribute('href') or ""
                            break
                except:
                    continue
            
            # If still no author, try to find ANY link text in the element
            if not author_name:
                try:
                    all_links = element.query_selector_all('a')
                    for link in all_links:
                        text = link.text_content().strip()
                        # First non-empty link is likely the author
                        if text and len(text) > 2 and text not in ['Like', 'Reply', 'Suka', 'Balas']:
                            author_name = text
                            author_url = link.get_attribute('href') or ""
                            break
                except:
                    pass
            
            # Extract comment text - try multiple approaches
            comment_text = ""
            
            # Strategy 1: Look for div[dir="auto"] with substantial text
            text_elements = element.query_selector_all('div[dir="auto"], span[dir="auto"]')
            for text_elem in text_elements:
                text = text_elem.text_content().strip()
                # Filter out author name, button text, etc.
                if text and len(text) > 5:
                    # Skip if it's just the author name or button text
                    if text not in [author_name, 'Like', 'Reply', 'Suka', 'Balas', 'Komentar', 'Comment']:
                        if len(text) > len(comment_text):
                            comment_text = text
            
            # Strategy 2: If no text found, get all text from element and clean it
            if not comment_text:
                full_text = element.text_content().strip()
                # Remove author name and common buttons from text
                for noise in [author_name, 'Like', 'Reply', 'Suka', 'Balas', '·', 'Just now', 'yang lalu']:
                    full_text = full_text.replace(noise, '')
                comment_text = full_text.strip()
            
            # CRITICAL: Remove URLs from comment text
            # User only wants the text, not any links
            if comment_text:
                # Remove all URLs (http, https, www)
                comment_text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', comment_text)
                comment_text = re.sub(r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', comment_text)
                # Clean up extra spaces
                comment_text = ' '.join(comment_text.split()).strip()
            
            # Log if we couldn't extract key data
            if not author_name and not comment_text:
                logger.debug(f"Skipping element - no author or text found")
                return None
            
            # If we have text but no author, use a placeholder
            if not author_name:
                author_name = "Unknown User"
            
            # Skip if comment is too short (likely not actual comment)
            if len(comment_text) < 2:
                logger.debug(f"Skipping short comment: '{comment_text}'")
                return None
            
            # Extract timestamp
            timestamp = ""
            time_elements = element.query_selector_all('a, span')
            for time_elem in time_elements:
                text = time_elem.text_content().strip()
                
                # Skip if this is actually the comment text (too long)
                if len(text) > 50:
                    continue
                    
                # Skip if it's author name or comment text
                if text == author_name or text == comment_text:
                    continue
                
                # Look for time-like text (e.g., "5m", "2h", "1d", "3 hari", etc.)
                if re.search(r'\d+\s*(m|h|d|j|w|hari|jam|menit|minggu|bulan|tahun|detik|s)', text, re.IGNORECASE) or \
                   re.search(r'just now|ago|yang lalu|baru saja', text, re.IGNORECASE):
                    timestamp = text
                    break
            
            # If no timestamp found, leave it empty (don't use comment_text as fallback!)
            
            # Extract likes count
            likes_count = 0
            try:
                like_elements = element.query_selector_all('[aria-label*="eaction"]')
                for like_elem in like_elements:
                    aria_label = like_elem.get_attribute('aria-label') or ""
                    # Extract number from aria-label
                    match = re.search(r'(\d+)', aria_label)
                    if match:
                        likes_count = int(match.group(1))
                        break
            except Exception:
                pass
            
            # Extract replies count
            replies_count = 0
            try:
                reply_buttons = element.query_selector_all('text=/\\d+ repl|\\d+ balas/i')
                for reply_btn in reply_buttons:
                    text = reply_btn.text_content()
                    match = re.search(r'(\d+)', text)
                    if match:
                        replies_count = int(match.group(1))
                        break
            except Exception:
                pass
            
            # Build comment data
            comment_data = {
                **post_info,
                'comment_author_name': author_name,
                'comment_author_url': author_url,
                'comment_text': comment_text,
                'comment_timestamp': timestamp,
                'parent_comment_id': '',  # Could be enhanced to detect reply threads
                'likes_count': likes_count,
                'replies_count': replies_count,
                'crawled_at': datetime.now().isoformat()
            }
            
            logger.debug(f"Extracted comment: {author_name[:20]}... | {comment_text[:50]}...")
            return comment_data
            
        except Exception as e:
            logger.debug(f"Error parsing comment element: {e}")
            return None
