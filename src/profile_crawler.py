"""Profile crawler to discover posts from Facebook user profiles"""

from typing import List, Optional
from playwright.sync_api import Page
from loguru import logger

from .config import Config
from .utils import random_delay, human_like_scroll, extract_username_from_url


class ProfileCrawler:
    """Crawl Facebook profile to discover post URLs"""
    
    def __init__(self, page: Page):
        self.page = page
        self.max_posts = Config.MAX_POSTS_PER_PROFILE
        self.scroll_limit = Config.PROFILE_SCROLL_LIMIT
        self.target_username = None  # Track target profile username for filtering
    
    def get_posts_from_profile(
        self, 
        profile_url: str, 
        max_posts: Optional[int] = None
    ) -> List[str]:
        """
        Get list of post URLs from a Facebook profile
        
        Args:
            profile_url: URL of the Facebook profile
            max_posts: Maximum number of posts to collect
            
        Returns:
            List of post URLs
        """
        max_posts = max_posts or self.max_posts
        logger.info(f"Crawling profile: {profile_url}")
        logger.info(f"Target: {max_posts} posts")
        
        try:
            # Extract target username from profile URL for filtering
            self.target_username = self._extract_username_from_url(profile_url)
            logger.info(f"Target username: {self.target_username}")
            
            # Navigate to profile
            self.page.goto(profile_url, timeout=Config.REQUEST_TIMEOUT)
            random_delay(3, 5)
            
            # Scroll to load posts
            post_urls = set()
            scroll_count = 0
            no_new_posts_count = 0
            
            while len(post_urls) < max_posts and scroll_count < self.scroll_limit:
                # Get current post count
                previous_count = len(post_urls)
                
                # Find all post links on the page
                new_urls = self._extract_post_urls()
                post_urls.update(new_urls)
                
                logger.debug(f"Found {len(post_urls)} posts so far (scroll {scroll_count + 1}/{self.scroll_limit})")
                
                # Check if we have enough posts already
                if len(post_urls) >= max_posts:
                    logger.info(f"Reached target of {max_posts} posts")
                    break
                
                # Check if we found new posts
                if len(post_urls) == previous_count:
                    no_new_posts_count += 1
                    if no_new_posts_count >= 3:
                        logger.info("No new posts found after 3 scrolls, stopping...")
                        break
                else:
                    no_new_posts_count = 0
                
                # Verify we're still on profile page (not homepage or other page)
                current_url = self.page.url
                if 'facebook.com/' not in current_url or current_url == 'https://www.facebook.com/' or '/home' in current_url:
                    logger.warning(f"Not on profile page anymore (URL: {current_url}), stopping...")
                    break
                
                # Scroll down to load more posts
                human_like_scroll(self.page, scroll_amount=500)
                random_delay(2, 4)
                
                scroll_count += 1
            
            # Convert set to list and limit to max_posts
            post_urls_list = list(post_urls)[:max_posts]
            
            logger.success(f"Collected {len(post_urls_list)} post URLs from profile")
            return post_urls_list
            
        except Exception as e:
            logger.error(f"Error crawling profile: {e}")
            return []
    
    def _extract_username_from_url(self, url: str) -> str:
        """Extract username from Facebook profile URL"""
        try:
            # https://www.facebook.com/MasRusdisutejo.N1 -> MasRusdisutejo.N1
            # https://www.facebook.com/profile.php?id=123 -> 123
            if '/profile.php?' in url:
                # Extract numeric ID
                if 'id=' in url:
                    user_id = url.split('id=')[-1].split('&')[0]
                    return user_id
            else:
                # Extract username from URL path
                parts = url.rstrip('/').split('/')
                for part in reversed(parts):
                    if part and part not in ['www.facebook.com', 'facebook.com', 'http:', 'https:']:
                        return part
            return ""
        except Exception as e:
            logger.error(f"Error extracting username from URL: {e}")
            return ""
    
    def _extract_post_urls(self) -> List[str]:
        """Extract post URLs from current page"""
        post_urls = []
        
        try:
            # Find all links that look like posts
            # Facebook post URLs usually contain /posts/, /story.php, /permalink.php, /reel/, etc.
            link_selectors = [
                'a[href*="/posts/"]',
                'a[href*="/story.php"]',
                'a[href*="/permalink.php"]',
                'a[href*="/videos/"]',
                'a[href*="/reel/"]',  # Reels (Instagram-style short videos)
                'a[href*="/photo"]'
            ]
            
            for selector in link_selectors:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    try:
                        href = element.get_attribute('href')
                        if href and self._is_valid_post_url(href):
                            # NOTE: We're already on the profile page, so all posts found here
                            # are from the target user. No need to filter by username in URL
                            # (especially since Reels don't have username in URL)
                            
                            # Normalize URL
                            if href.startswith('/'):
                                href = f"https://www.facebook.com{href}"
                            
                            # Clean URL - remove ALL query parameters for cleaner URLs
                            href = href.split('?')[0]
                            
                            post_urls.append(href)
                    except Exception as e:
                        logger.debug(f"Error extracting href: {e}")
                        continue
            
            return list(set(post_urls))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error extracting post URLs: {e}")
            return []
    
    def _is_valid_post_url(self, url: str) -> bool:
        """Check if URL is a valid Facebook post URL"""
        try:
            # Filter out non-post URLs
            invalid_patterns = [
                '/about',
                '/friends',
                '/photos',
                '/videos/?',  # videos tab, not individual video
                '/groups',
                '/events',
                'photo.php?fbid',  # photo viewer, not post
                '/reels?',  # reels tab (plural), not individual reel
                '/watch'
            ]
            
            for pattern in invalid_patterns:
                if pattern in url:
                    return False
            
            # Must contain facebook.com
            if 'facebook.com' not in url and not url.startswith('/'):
                return False
            
            # Should contain post indicators
            valid_patterns = [
                '/posts/',
                '/story.php?',
                '/permalink.php?',
                '/videos/',
                '/reel/',  # Individual reel (singular)
                '/photo.php?'
            ]
            
            return any(pattern in url for pattern in valid_patterns)
            
        except Exception as e:
            logger.debug(f"Error validating URL: {e}")
            return False
    
    def get_posts_from_username(
        self, 
        username: str, 
        max_posts: Optional[int] = None
    ) -> List[str]:
        """
        Get posts from a Facebook username
        
        Args:
            username: Facebook username
            max_posts: Maximum number of posts to collect
            
        Returns:
            List of post URLs
        """
        # Construct profile URL from username
        if username.startswith('http'):
            username = extract_username_from_url(username)
        
        profile_url = f"https://www.facebook.com/{username}"
        return self.get_posts_from_profile(profile_url, max_posts)
