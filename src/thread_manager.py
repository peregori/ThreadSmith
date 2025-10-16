#!/usr/bin/env python3
"""
Thread Manager - Handles thread fetching and reconstruction
"""

import re
from typing import Dict, List, Optional
from rich.console import Console

from .twitter_client import TwitterClient

console = Console()


class ThreadManager:
    """Manages thread fetching and reconstruction."""
    
    def __init__(self, twitter_client: TwitterClient):
        """Initialize thread manager with Twitter client."""
        self.client = twitter_client
    
    def fetch_thread(self, tweet_id: str, conversation_id: str, author_id: str) -> List[Dict]:
        """
        Fetch all tweets in a thread.
        
        Args:
            tweet_id: The ID of the bookmarked tweet
            conversation_id: The conversation ID
            author_id: The author's user ID
            
        Returns:
            List of tweet dictionaries, sorted chronologically
        """
        console.print(f"[cyan]📝 Fetching thread for tweet {tweet_id}...[/cyan]")
        
        # Try conversation search first (works for tweets < 7 days old on free tier)
        thread_tweets = self.client.search_conversation(conversation_id, author_id)
        
        if thread_tweets:
            console.print(f"[green]✓ Found {len(thread_tweets)} tweets via search[/green]")
            return thread_tweets
        
        # Fallback: fetch single tweet (works for older tweets)
        console.print("[yellow]⚠️  Thread search failed (likely >7 days old). Fetching single tweet...[/yellow]")
        single_tweet = self.client.fetch_single_tweet(tweet_id, skip_rate_limit=True)
        
        if single_tweet:
            console.print("[green]✓ Fetched single tweet[/green]")
            return [single_tweet]
        
        console.print("[red]❌ Failed to fetch thread[/red]")
        return []
    
    def reconstruct_thread_text(self, tweets: List[Dict]) -> str:
        """
        Reconstruct thread as formatted text.
        
        Args:
            tweets: List of tweet dictionaries
            
        Returns:
            Formatted thread text
        """
        if not tweets:
            return ""
        
        thread_parts = []
        for i, tweet in enumerate(tweets, 1):
            text = tweet.get('text', '')
            thread_parts.append(f"Tweet {i}:\n{text}")
        
        return "\n\n".join(thread_parts)
    
    def reconstruct_thread_markdown(self, tweets: List[Dict], author_username: str = None) -> str:
        """
        Reconstruct thread as clean markdown (for LLM processing).
        
        Args:
            tweets: List of tweet dictionaries
            author_username: Author's username (optional)
            
        Returns:
            Clean markdown text with no metadata contamination
        """
        if not tweets:
            return ""
        
        parts = []
        
        # Add header if we have author info
        if author_username:
            parts.append(f"# Thread by @{author_username}\n")
        
        # Add each tweet cleanly
        for i, tweet in enumerate(tweets, 1):
            text = tweet.get('text', '').strip()
            if len(tweets) > 1:
                # Number tweets only if it's actually a thread
                parts.append(f"**{i}/**\n{text}")
            else:
                # Single tweet, no numbering
                parts.append(text)
        
        return "\n\n".join(parts)
    
    def extract_tweet_id(self, url: str) -> Optional[str]:
        """
        Extract tweet ID from Twitter/X URL.
        
        Args:
            url: Twitter/X URL or tweet ID
            
        Returns:
            Tweet ID or None if not found
        """
        patterns = [
            r'twitter\.com/\w+/status/(\d+)',
            r'x\.com/\w+/status/(\d+)',
            r'twitter\.com/i/web/status/(\d+)',
            r'x\.com/i/web/status/(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Check if it's already just a tweet ID
        if url.isdigit():
            return url
        
        return None
    
    def build_thread_metadata(self, tweets: List[Dict], tweet_id: str, author_username: str = None) -> Dict:
        """
        Build metadata for a thread.
        
        Args:
            tweets: List of tweet dictionaries
            tweet_id: The bookmarked tweet ID
            author_username: The author's username
            
        Returns:
            Metadata dictionary
        """
        if not tweets:
            return {}
        
        first_tweet = tweets[0]
        last_tweet = tweets[-1]
        
        # Extract author info
        author_id = first_tweet.get('author_id', 'unknown')
        if not author_username and 'author_username' in first_tweet:
            author_username = first_tweet['author_username']
        elif not author_username:
            author_username = 'unknown'
        
        metadata = {
            'tweet_id': tweet_id,
            'conversation_id': first_tweet.get('conversation_id', tweet_id),
            'author_id': author_id,
            'author_username': author_username,
            'tweet_count': len(tweets),
            'first_tweet_time': first_tweet.get('created_at'),
            'last_tweet_time': last_tweet.get('created_at'),
            'url': f"https://x.com/{author_username}/status/{tweet_id}",
            'tweets': tweets
        }
        
        return metadata

