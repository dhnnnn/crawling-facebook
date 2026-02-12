"""JSON export operations for crawled data"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import Config
from .utils import get_timestamp_string, sanitize_filename


class JSONExporter:
    """Handle JSON export operations"""
    
    def __init__(self, export_mode: str = "single", pretty: bool = True, output_dir: Optional[str] = None):
        """
        Initialize JSON exporter
        
        Args:
            export_mode: 'single' or 'per-post'
            pretty: Whether to pretty-print JSON (indented)
            output_dir: Custom output directory (optional)
        """
        self.export_mode = export_mode or Config.EXPORT_MODE
        self.pretty = pretty
        self.output_dir = output_dir  # For future use if needed
        self.comments_data: List[Dict[str, Any]] = []
        
    def add_comments(self, comments: List[Dict[str, Any]]) -> None:
        """Add comments to the internal buffer"""
        self.comments_data.extend(comments)
        logger.debug(f"Added {len(comments)} comments to buffer. Total: {len(self.comments_data)}")
    
    def export(self, username: Optional[str] = None, post_id: Optional[str] = None) -> List[str]:
        """
        Export comments to JSON file(s)
        
        Args:
            username: Username for filename (optional)
            post_id: Post ID for per-post mode (optional)
            
        Returns:
            List of exported file paths
        """
        if not self.comments_data:
            logger.warning("No comments to export")
            return []
        
        exported_files = []
        
        if self.export_mode == "single":
            filepath = self._export_single_file(username)
            exported_files.append(filepath)
        else:  # per-post mode
            filepaths = self._export_per_post()
            exported_files.extend(filepaths)
        
        return exported_files
    
    def _export_single_file(self, username: Optional[str] = None) -> str:
        """Export all comments to a single JSON file"""
        timestamp = get_timestamp_string()
        
        if username:
            filename = f"comments_{sanitize_filename(username)}_{timestamp}.json"
        else:
            filename = f"comments_{timestamp}.json"
        
        # Use JSON subdirectory
        json_dir = Config.EXPORTS_DIR / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        filepath = json_dir / filename
        
        # Remove unnecessary fields
        clean_comments = []
        for comment in self.comments_data:
            clean_comment = {k: v for k, v in comment.items() 
                           if k not in ['post_content', 'comment_id', 'parent_comment_id']}
            clean_comments.append(clean_comment)
        
        # Prepare data structure
        export_data = {
            "metadata": {
                "total_comments": len(clean_comments),
                "exported_at": datetime.now().isoformat(),
                "username": username if username else "unknown"
            },
            "comments": clean_comments
        }
        
        # Export JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            if self.pretty:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            else:
                json.dump(export_data, f, ensure_ascii=False)
        
        logger.success(f"Exported {len(clean_comments)} comments to {filepath}")
        return str(filepath)
    
    def _export_per_post(self) -> List[str]:
        """Export comments with one JSON file per post"""
        exported_files = []
        
        # Group comments by post_url
        posts_comments = {}
        for comment in self.comments_data:
            post_url = comment.get('post_url', 'unknown')
            if post_url not in posts_comments:
                posts_comments[post_url] = []
            posts_comments[post_url].append(comment)
        
        for post_url, comments in posts_comments.items():
            # Extract post identifier from URL
            post_id = self._extract_post_id(post_url)
            timestamp = get_timestamp_string()
            
            filename = f"comments_{sanitize_filename(post_id)}_{timestamp}.json"
            
            # Use JSON subdirectory
            json_dir = Config.EXPORTS_DIR / "json"
            json_dir.mkdir(parents=True, exist_ok=True)
            filepath = json_dir / filename
            
            # Prepare data structure
            export_data = {
                "metadata": {
                    "post_url": post_url,
                    "total_comments": len(comments),
                    "exported_at": datetime.now().isoformat()
                },
                "comments": comments
            }
            
            # Export JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                if self.pretty:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                else:
                    json.dump(export_data, f, ensure_ascii=False)
            
            logger.info(f"Exported {len(comments)} comments from post {post_id} to {filepath}")
            exported_files.append(str(filepath))
        
        logger.success(f"Exported comments to {len(exported_files)} JSON files")
        return exported_files
    
    def _extract_post_id(self, post_url: str) -> str:
        """Extract post ID from Facebook post URL"""
        try:
            # Try to extract post ID from URL
            if "/posts/" in post_url:
                post_id = post_url.split("/posts/")[-1].split("/")[0].split("?")[0]
            elif "/reel/" in post_url:
                post_id = post_url.split("/reel/")[-1].split("/")[0].split("?")[0]
            elif "story_fbid=" in post_url:
                post_id = post_url.split("story_fbid=")[-1].split("&")[0]
            elif "fbid=" in post_url:
                post_id = post_url.split("fbid=")[-1].split("&")[0]
            else:
                # Use last part of URL
                post_id = post_url.rstrip('/').split('/')[-1].split('?')[0]
            
            return post_id[:50]  # Limit length
        except Exception as e:
            logger.error(f"Error extracting post ID from {post_url}: {e}")
            return "unknown"
    
    def clear_buffer(self) -> None:
        """Clear the internal comments buffer"""
        self.comments_data = []
        logger.debug("Comments buffer cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about buffered comments"""
        if not self.comments_data:
            return {
                'total_comments': 0,
                'unique_posts': 0,
                'unique_authors': 0
            }
        
        # Count unique posts and authors
        unique_posts = set()
        unique_authors = set()
        
        for comment in self.comments_data:
            if 'post_url' in comment:
                unique_posts.add(comment['post_url'])
            if 'comment_author_name' in comment:
                unique_authors.add(comment['comment_author_name'])
        
        return {
            'total_comments': len(self.comments_data),
            'unique_posts': len(unique_posts),
            'unique_authors': len(unique_authors)
        }
