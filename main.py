"""Main entry point for Facebook Comment Crawler"""

import sys
import argparse
from pathlib import Path
from typing import List, Optional
from playwright.sync_api import sync_playwright
from loguru import logger

from src.config import Config
from src.utils import setup_logging, validate_url, extract_username_from_url
from src.auth import FacebookAuth
from src.profile_crawler import ProfileCrawler
from src.crawler import CommentCrawler
from src.csv_exporter import CSVExporter
from src.json_exporter import JSONExporter


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Facebook Comment Crawler - Crawl comments from Facebook posts and profiles"
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--url',
        type=str,
        help='Facebook post URL to crawl comments from'
    )
    input_group.add_argument(
        '--profile',
        type=str,
        help='Facebook profile URL to crawl all posts from'
    )
    input_group.add_argument(
        '--username',
        type=str,
        help='Facebook username to crawl all posts from'
    )
    input_group.add_argument(
        '--urls-file',
        type=str,
        help='File containing list of post URLs (one per line)'
    )
    input_group.add_argument(
        '--profiles-file',
        type=str,
        help='File containing list of profile URLs or usernames (one per line)'
    )
    
    # Crawler options
    parser.add_argument(
        '--max-posts',
        type=int,
        default=Config.MAX_POSTS_PER_PROFILE,
        help=f'Maximum posts to crawl per profile (default: {Config.MAX_POSTS_PER_PROFILE})'
    )
    parser.add_argument(
        '--max-comments',
        type=int,
        default=None,
        help='Maximum comments to crawl per post (default: all)'
    )
    parser.add_argument(
        '--headless',
        type=lambda x: x.lower() in ['true', '1', 'yes'],
        default=Config.HEADLESS,
        help=f'Run browser in headless mode (default: {Config.HEADLESS})'
    )
    
    # Export options
    parser.add_argument(
        '--export-mode',
        type=str,
        choices=['single', 'per-post'],
        default=Config.EXPORT_MODE,
        help=f'Export mode: single file or per-post files (default: {Config.EXPORT_MODE})'
    )
    parser.add_argument(
        '--format',
        type=str,
        choices=['csv', 'excel', 'json', 'both'],
        default=Config.EXPORT_FORMAT,
        help=f'Export format: csv, excel, json, or both (csv+json) (default: {Config.EXPORT_FORMAT})'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for exported files'
    )
    
    return parser.parse_args()


def read_urls_from_file(filepath: str) -> List[str]:
    """Read URLs from a text file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        logger.info(f"Loaded {len(urls)} URLs from {filepath}")
        return urls
    except Exception as e:
        logger.error(f"Failed to read file {filepath}: {e}")
        return []


def main():
    """Main execution function"""
    # Setup logging
    setup_logging()
    
    # Parse arguments
    args = parse_arguments()
    
    # Validate configuration
    if not Config.validate():
        logger.error("Configuration validation failed!")
        logger.error("Please set FB_EMAIL and FB_PASSWORD in .env file")
        logger.info("You can copy .env.example to .env and fill in your credentials")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("Facebook Comment Crawler")
    logger.info("=" * 60)
    
    # Initialize exporters based on format
    csv_exporter = None
    json_exporter = None
    
    if args.format in ['csv', 'both']:
        csv_exporter = CSVExporter(
            export_mode=args.export_mode,
            export_format='csv',
            output_dir=args.output_dir
        )
    
    if args.format in ['json', 'both']:
        json_exporter = JSONExporter(
            export_mode=args.export_mode,
            pretty=True,
            output_dir=args.output_dir
        )
    
    if args.format == 'excel':
        csv_exporter = CSVExporter(
            export_mode=args.export_mode,
            export_format='excel',
            output_dir=args.output_dir
        )
    
    # Determine what to crawl
    post_urls = []
    username_for_filename = None
    
    if args.url:
        post_urls = [args.url]
    elif args.profile:
        username_for_filename = extract_username_from_url(args.profile)
    elif args.username:
        username_for_filename = args.username
    elif args.urls_file:
        post_urls = read_urls_from_file(args.urls_file)
    elif args.profiles_file:
        profiles = read_urls_from_file(args.profiles_file)
    
    try:
        with sync_playwright() as p:
            # Launch browser
            logger.info(f"Launching browser (headless={args.headless})...")
            browser = p.chromium.launch(headless=args.headless)
            
            # Authenticate
            auth = FacebookAuth()
            page = auth.login(browser)
            
            # If we need to get posts from profile
            if username_for_filename or args.profiles_file:
                profile_crawler = ProfileCrawler(page)
                
                if username_for_filename:
                    # Single profile
                    post_urls = profile_crawler.get_posts_from_username(
                        username_for_filename,
                        max_posts=args.max_posts
                    )
                else:
                    # Multiple profiles
                    for profile in profiles:
                        logger.info(f"\nProcessing profile: {profile}")
                        profile_username = extract_username_from_url(profile) if 'http' in profile else profile
                        urls = profile_crawler.get_posts_from_username(
                            profile_username,
                            max_posts=args.max_posts
                        )
                        post_urls.extend(urls)
            
            if not post_urls:
                logger.error("No posts to crawl!")
                sys.exit(1)
            
            logger.info(f"\nTotal posts to crawl: {len(post_urls)}")
            
            # Crawl comments from all posts
            comment_crawler = CommentCrawler(page)
            
            for idx, post_url in enumerate(post_urls, 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"Post {idx}/{len(post_urls)}: {post_url}")
                logger.info(f"{'='*60}")
                
                try:
                    comments = comment_crawler.crawl_post_comments(
                        post_url,
                        max_comments=args.max_comments
                    )
                    
                    if comments:
                        # Add to all active exporters
                        if csv_exporter:
                            csv_exporter.add_comments(comments)
                        if json_exporter:
                            json_exporter.add_comments(comments)
                        logger.info(f"✓ Collected {len(comments)} comments")
                    else:
                        logger.warning("✗ No comments found")
                        
                except Exception as e:
                    logger.error(f"✗ Error crawling post: {e}")
                    continue
            
            # Export results
            logger.info(f"\n{'='*60}")
            logger.info("Exporting results...")
            logger.info(f"{'='*60}")
            
            # Get stats from first available exporter
            active_exporter = csv_exporter if csv_exporter else json_exporter
            stats = active_exporter.get_stats()
            logger.info(f"Total comments collected: {stats['total_comments']}")
            logger.info(f"Unique posts: {stats['unique_posts']}")
            logger.info(f"Unique authors: {stats['unique_authors']}")
            
            exported_files = []
            
            # Export CSV/Excel
            if csv_exporter:
                files = csv_exporter.export(username=username_for_filename)
                exported_files.extend(files)
            
            # Export JSON
            if json_exporter:
                files = json_exporter.export(username=username_for_filename)
                exported_files.extend(files)
            
            if exported_files:
                logger.success(f"\n✓ Export complete!")
                logger.info(f"Files created:")
                for filepath in exported_files:
                    logger.info(f"  - {filepath}")
            else:
                logger.warning("No files exported (no comments collected)")
            
            # Cleanup
            auth.close()
            browser.close()
            
            logger.info(f"\n{'='*60}")
            logger.success("Crawling completed successfully!")
            logger.info(f"{'='*60}")
            
    except KeyboardInterrupt:
        logger.warning("\n\nCrawling interrupted by user")
        # Export progress from all active exporters
        exported_files = []
        if csv_exporter:
            logger.info("Saving CSV progress...")
            exported_files.extend(csv_exporter.export(username=username_for_filename))
        if json_exporter:
            logger.info("Saving JSON progress...")
            exported_files.extend(json_exporter.export(username=username_for_filename))
        
        if exported_files:
            logger.success("Current progress saved:")
            for f in exported_files:
                logger.info(f"  - {f}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
