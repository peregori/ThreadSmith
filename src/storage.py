#!/usr/bin/env python3
"""
Storage - Handles thread persistence and tracking
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from rich.console import Console
from slugify import slugify

console = Console()


class ThreadStorage:
    """Handles thread storage and tracking."""
    
    def __init__(self, data_dir: Path, threads_dir: Path):
        """
        Initialize storage.
        
        Args:
            data_dir: Directory for tracking data
            threads_dir: Directory for thread JSON files
        """
        self.data_dir = Path(data_dir)
        self.threads_dir = Path(threads_dir)
        
        # Create directories
        self.data_dir.mkdir(exist_ok=True, parents=True)
        self.threads_dir.mkdir(exist_ok=True, parents=True)
        
        self.processed_file = self.data_dir / "processed_threads.json"
        self.processed_tweets = self._load_processed_tweets()
    
    def _load_processed_tweets(self) -> Set[str]:
        """Load set of already processed tweet IDs."""
        if self.processed_file.exists():
            try:
                with open(self.processed_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('processed_tweet_ids', []))
            except:
                return set()
        return set()
    
    def _save_processed_tweets(self):
        """Save processed tweet IDs to file."""
        with open(self.processed_file, 'w') as f:
            json.dump({
                'processed_tweet_ids': list(self.processed_tweets),
                'last_sync': datetime.now().isoformat()
            }, f, indent=2)
    
    def is_processed(self, tweet_id: str) -> bool:
        """Check if a tweet has been processed."""
        return tweet_id in self.processed_tweets
    
    def mark_processed(self, tweet_id: str):
        """Mark a tweet as processed."""
        self.processed_tweets.add(tweet_id)
        self._save_processed_tweets()
    
    def save_thread(self, thread_metadata: Dict, markdown_content: str = None) -> Optional[Path]:
        """
        Save thread in dual format: JSON (metadata) + Markdown (clean content).
        
        Args:
            thread_metadata: Thread metadata dictionary
            markdown_content: Clean markdown content for LLM processing (optional)
            
        Returns:
            Path to saved JSON file or None on error
        """
        tweet_id = thread_metadata.get('tweet_id')
        author_username = thread_metadata.get('author_username', 'unknown')
        
        if not tweet_id:
            console.print("[red]❌ No tweet ID in metadata[/red]")
            return None
        
        # Create base filename from author and tweet ID
        base_filename = f"{author_username}_{tweet_id}"
        json_filepath = self.threads_dir / f"{base_filename}.json"
        md_filepath = self.threads_dir / f"{base_filename}.md"
        
        # Add storage metadata
        save_data = {
            **thread_metadata,
            'saved_at': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        try:
            # Save JSON (metadata + full tweet data)
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            console.print(f"[green]✓ Saved JSON: {json_filepath.name}[/green]")
            
            # Save Markdown (clean content for LLM)
            if markdown_content:
                with open(md_filepath, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                console.print(f"[green]✓ Saved Markdown: {md_filepath.name}[/green]")
            
            # Mark as processed
            self.mark_processed(tweet_id)
            
            return json_filepath
        except Exception as e:
            console.print(f"[red]❌ Error saving thread: {e}[/red]")
            return None
    
    def load_thread(self, tweet_id: str) -> Optional[Dict]:
        """
        Load thread metadata from JSON file.
        
        Args:
            tweet_id: Tweet ID to load
            
        Returns:
            Thread metadata or None if not found
        """
        # Find file matching tweet_id
        for filepath in self.threads_dir.glob(f"*_{tweet_id}.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                continue
        return None
    
    def load_thread_markdown(self, tweet_id: str) -> Optional[str]:
        """
        Load clean markdown content for LLM processing.
        
        Args:
            tweet_id: Tweet ID to load
            
        Returns:
            Markdown content or None if not found
        """
        # Find file matching tweet_id
        for filepath in self.threads_dir.glob(f"*_{tweet_id}.md"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return f.read()
            except:
                continue
        return None
    
    def list_threads(self) -> List[Dict]:
        """
        List all saved threads with metadata.
        
        Returns:
            List of thread info dictionaries
        """
        threads = []
        
        for filepath in sorted(self.threads_dir.glob("*.json"), 
                               key=lambda x: x.stat().st_mtime, 
                               reverse=True):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    threads.append({
                        'filename': filepath.name,
                        'tweet_id': data.get('tweet_id'),
                        'author': data.get('author_username'),
                        'tweet_count': data.get('tweet_count'),
                        'url': data.get('url'),
                        'saved_at': data.get('saved_at'),
                        'filepath': filepath
                    })
            except:
                continue
        
        return threads
    
    def get_stats(self) -> Dict:
        """Get storage statistics."""
        threads = self.list_threads()
        return {
            'total_threads': len(threads),
            'total_processed': len(self.processed_tweets),
            'storage_path': str(self.threads_dir)
        }

