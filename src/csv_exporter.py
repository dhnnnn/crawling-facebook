"""CSV/Excel export operations for crawled data"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import Config
from .utils import get_timestamp_string, sanitize_filename


class CSVExporter:
    """Handle CSV and Excel export operations"""
    
    def __init__(self, export_mode: str = "single", export_format: str = "csv", output_dir: Optional[str] = None):
        """
        Initialize exporter
        
        Args:
            export_mode: 'single' or 'per-post'
            export_format: 'csv' or 'excel'
            output_dir: Custom output directory (optional, for future use)
        """
        self.export_mode = export_mode or Config.EXPORT_MODE
        self.export_format = export_format or Config.EXPORT_FORMAT
        self.output_dir = output_dir  # For future use if needed
        self.comments_data: List[Dict[str, Any]] = []
        
    def add_comments(self, comments: List[Dict[str, Any]]) -> None:
        """Add comments to the internal buffer"""
        self.comments_data.extend(comments)
        logger.debug(f"Added {len(comments)} comments to buffer. Total: {len(self.comments_data)}")
    
    def export(self, username: Optional[str] = None, post_id: Optional[str] = None) -> List[str]:
        """
        Export comments to file(s)
        
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
        """Export all comments to a single file"""
        timestamp = get_timestamp_string()
        
        if username:
            filename = f"comments_{sanitize_filename(username)}_{timestamp}"
        else:
            filename = f"comments_{timestamp}"
        
        if self.export_format == "excel":
            filename += ".xlsx"
        else:
            filename += ".csv"
        
        # Use CSV subdirectory
        csv_dir = Config.EXPORTS_DIR / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        filepath = csv_dir / filename
        
        # Create DataFrame
        df = pd.DataFrame(self.comments_data)
        
        # Ensure columns are in a logical order
        column_order = [
            'post_url', 'post_author', 'post_timestamp',
            'comment_author_name', 'comment_author_url',
            'comment_text', 'comment_timestamp',
            'likes_count', 'replies_count', 'crawled_at'
        ]
        
        # Reorder columns (only include existing columns)
        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns]
        
        # Export
        if self.export_format == "excel":
            df.to_excel(filepath, index=False, engine='openpyxl')
        else:
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        logger.success(f"Exported {len(df)} comments to {filepath}")
        return str(filepath)
    
    def _export_per_post(self) -> List[str]:
        """Export comments with one file per post"""
        exported_files = []
        
        # Group comments by post_url
        df = pd.DataFrame(self.comments_data)
        
        if 'post_url' not in df.columns:
            logger.error("post_url column not found, cannot export per-post")
            return []
        
        grouped = df.groupby('post_url')
        
        for post_url, group_df in grouped:
            # Extract post identifier from URL
            post_id = self._extract_post_id(post_url)
            timestamp = get_timestamp_string()
            
            filename = f"comments_{sanitize_filename(post_id)}_{timestamp}"
            
            if self.export_format == "excel":
                filename += ".xlsx"
            else:
                filename += ".csv"
            
            # Use CSV subdirectory
            csv_dir = Config.EXPORTS_DIR / "csv"
            csv_dir.mkdir(parents=True, exist_ok=True)
            filepath = csv_dir / filename
            
            # Ensure columns are in a logical order
            column_order = [
                'post_url', 'post_author', 'post_timestamp',
                'comment_author_name', 'comment_author_url',
                'comment_text', 'comment_timestamp',
                'likes_count', 'replies_count', 'crawled_at'
            ]
            
            existing_columns = [col for col in column_order if col in group_df.columns]
            group_df = group_df[existing_columns]
            
            # Export
            if self.export_format == "excel":
                group_df.to_excel(filepath, index=False, engine='openpyxl')
            else:
                group_df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            logger.info(f"Exported {len(group_df)} comments from post {post_id} to {filepath}")
            exported_files.append(str(filepath))
        
        logger.success(f"Exported comments to {len(exported_files)} files")
        return exported_files
    
    def _extract_post_id(self, post_url: str) -> str:
        """Extract post ID from Facebook post URL"""
        try:
            # Try to extract post ID from URL
            if "/posts/" in post_url:
                post_id = post_url.split("/posts/")[-1].split("/")[0].split("?")[0]
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
        
        df = pd.DataFrame(self.comments_data)
        
        return {
            'total_comments': len(df),
            'unique_posts': df['post_url'].nunique() if 'post_url' in df.columns else 0,
            'unique_authors': df['comment_author_name'].nunique() if 'comment_author_name' in df.columns else 0
        }
