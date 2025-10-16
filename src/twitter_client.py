#!/usr/bin/env python3
"""
Twitter API Client - Handles all Twitter API interactions
"""

import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from rich.console import Console

console = Console()


class TwitterClient:
    """Twitter API client with OAuth2 and rate limiting."""
    
    def __init__(self, config: Dict):
        """Initialize Twitter client with configuration."""
        self.config = config
        self.cached_user_id = None
        self.last_api_call = 0
        self.min_delay = 900  # 15 minutes for free tier
        self.rate_limit_reset = {}  # Track reset times per endpoint
        self.just_refreshed_token = False
        
    def _check_and_refresh_token(self) -> bool:
        """Check if access token is expired and refresh if needed."""
        if 'oauth2_refresh_token' not in self.config:
            return True
        
        # Skip validation if we just refreshed
        if self.just_refreshed_token:
            self.just_refreshed_token = False
            return True
        
        headers = {"Authorization": f"Bearer {self.config['oauth2_access_token']}"}
        try:
            response = requests.get("https://api.twitter.com/2/users/me", headers=headers)
            if response.status_code == 200:
                return True
            
            if response.status_code == 401:
                console.print("[yellow]🔄 Access token expired, refreshing...[/yellow]")
                return self._refresh_access_token()
        except:
            pass
        
        return True
    
    def _refresh_access_token(self) -> bool:
        """Refresh OAuth2 token using HTTP Basic Auth with PKCE."""
        if 'oauth2_refresh_token' not in self.config:
            console.print("[red]❌ No refresh token available. Please re-authenticate.[/red]")
            return False
        
        token_url = "https://api.twitter.com/2/oauth2/token"
        
        client_credentials = f"{self.config['oauth2_client_id']}:{self.config['oauth2_client_secret']}"
        encoded_credentials = base64.b64encode(client_credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.config['oauth2_refresh_token']
        }
        
        try:
            response = requests.post(token_url, headers=headers, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.config['oauth2_access_token'] = token_data['access_token']
                if 'refresh_token' in token_data:
                    self.config['oauth2_refresh_token'] = token_data['refresh_token']
                self.just_refreshed_token = True
                console.print("[green]✓ Token refreshed successfully[/green]")
                return True
            else:
                console.print(f"[red]❌ Token refresh failed: {response.text}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]❌ Token refresh error: {e}[/red]")
            return False
    
    def _extract_rate_limit_info(self, response, endpoint_key: str):
        """Extract and store rate limit info from response headers."""
        if 'x-rate-limit-remaining' in response.headers:
            remaining = int(response.headers.get('x-rate-limit-remaining', 0))
            reset_time = int(response.headers.get('x-rate-limit-reset', 0))
            
            if remaining == 0 and reset_time > 0:
                self.rate_limit_reset[endpoint_key] = reset_time
    
    def _rate_limit_wait(self, endpoint_key: str = "default"):
        """Smart rate limiting using actual API response headers when available."""
        current_time = time.time()
        
        # Check if we have a specific reset time for this endpoint
        if endpoint_key in self.rate_limit_reset:
            reset_time = self.rate_limit_reset[endpoint_key]
            if current_time < reset_time:
                wait_time = reset_time - current_time
                wait_mins = wait_time / 60
                console.print(f"[yellow]⏳ Rate limit: waiting {wait_mins:.1f} minutes ({wait_time:.0f}s)...[/yellow]")
                console.print(f"[dim]   API quota resets at {datetime.fromtimestamp(reset_time).strftime('%H:%M:%S')}[/dim]")
                time.sleep(wait_time)
                del self.rate_limit_reset[endpoint_key]
                self.last_api_call = time.time()
                return
        
        # Fallback to conservative timing if no header info
        elapsed = current_time - self.last_api_call
        if self.last_api_call > 0 and elapsed < self.min_delay:
            wait_time = self.min_delay - elapsed
            wait_mins = wait_time / 60
            console.print(f"[yellow]⏳ Rate limit: waiting {wait_mins:.1f} minutes ({wait_time:.0f}s)...[/yellow]")
            console.print(f"[dim]   Free tier allows 1 request per 15 minutes[/dim]")
            time.sleep(wait_time)
        
        self.last_api_call = time.time()
    
    def get_user_id(self) -> Optional[str]:
        """Get authenticated user's ID (cached)."""
        if self.cached_user_id:
            return self.cached_user_id
        
        if not self._check_and_refresh_token():
            return None
        
        self._rate_limit_wait("users_me")
        
        url = "https://api.twitter.com/2/users/me"
        headers = {"Authorization": f"Bearer {self.config['oauth2_access_token']}"}
        
        try:
            response = requests.get(url, headers=headers)
            self._extract_rate_limit_info(response, "users_me")
            
            if response.status_code == 200:
                self.cached_user_id = response.json()['data']['id']
                return self.cached_user_id
            elif response.status_code == 429:
                reset_time = int(response.headers.get('x-rate-limit-reset', time.time() + 900))
                self.rate_limit_reset["users_me"] = reset_time
                console.print("[yellow]⚠️  Rate limited! Waiting for quota reset...[/yellow]")
                return self.get_user_id()
            else:
                console.print(f"[red]❌ Failed to get user ID: {response.text}[/red]")
                return None
        except Exception as e:
            console.print(f"[red]❌ Error getting user ID: {e}[/red]")
            return None
    
    def fetch_bookmarks(self, max_results: int = 50) -> List[Dict]:
        """Fetch user's bookmarked tweets."""
        if not self._check_and_refresh_token():
            return []
        
        user_id = self.get_user_id()
        if not user_id:
            return []
        
        self._rate_limit_wait("bookmarks")
        
        url = f"https://api.twitter.com/2/users/{user_id}/bookmarks"
        headers = {"Authorization": f"Bearer {self.config['oauth2_access_token']}"}
        params = {
            "max_results": min(max_results, 100),
            "tweet.fields": "conversation_id,created_at,author_id,text",
            "expansions": "author_id",
            "user.fields": "username"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            self._extract_rate_limit_info(response, "bookmarks")
            
            if response.status_code == 200:
                data = response.json()
                bookmarks = data.get('data', [])
                
                # Add author usernames
                if 'includes' in data and 'users' in data['includes']:
                    users_map = {u['id']: u for u in data['includes']['users']}
                    for bookmark in bookmarks:
                        author_id = bookmark.get('author_id')
                        if author_id in users_map:
                            bookmark['author_username'] = users_map[author_id]['username']
                
                console.print(f"[green]✓ Found {len(bookmarks)} bookmarks[/green]")
                return bookmarks
            elif response.status_code == 429:
                reset_time = int(response.headers.get('x-rate-limit-reset', time.time() + 900))
                self.rate_limit_reset["bookmarks"] = reset_time
                console.print("[yellow]⚠️  Rate limited! Waiting for quota reset...[/yellow]")
                return self.fetch_bookmarks(max_results)
            else:
                console.print(f"[red]❌ Failed to fetch bookmarks: {response.text}[/red]")
                return []
        except Exception as e:
            console.print(f"[red]❌ Error fetching bookmarks: {e}[/red]")
            return []
    
    def fetch_single_tweet(self, tweet_id: str, skip_rate_limit: bool = False) -> Optional[Dict]:
        """Fetch a single tweet by ID."""
        if not self._check_and_refresh_token():
            return None
        
        if not skip_rate_limit:
            self._rate_limit_wait("tweets")
        
        headers = {"Authorization": f"Bearer {self.config['oauth2_access_token']}"}
        url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        params = {
            "tweet.fields": "created_at,text,author_id,conversation_id"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            self._extract_rate_limit_info(response, "tweets")
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    return data['data']
            elif response.status_code == 429:
                reset_time = int(response.headers.get('x-rate-limit-reset', time.time() + 900))
                self.rate_limit_reset["tweets"] = reset_time
                console.print("[yellow]⚠️  Rate limited! Waiting for quota reset...[/yellow]")
                return self.fetch_single_tweet(tweet_id, skip_rate_limit=False)
            else:
                console.print(f"[yellow]⚠️  API error {response.status_code}: {response.text}[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not fetch tweet: {e}[/yellow]")
        
        return None
    
    def search_conversation(self, conversation_id: str, author_id: str) -> List[Dict]:
        """Search for all tweets in a conversation."""
        if not self._check_and_refresh_token():
            return []
        
        self._rate_limit_wait("search")
        
        headers = {"Authorization": f"Bearer {self.config['oauth2_access_token']}"}
        search_url = "https://api.twitter.com/2/tweets/search/recent"
        search_params = {
            "query": f"conversation_id:{conversation_id} from:{author_id} -is:retweet",
            "max_results": 100,
            "tweet.fields": "created_at,text,author_id,conversation_id",
            "sort_order": "recency"
        }
        
        try:
            response = requests.get(search_url, headers=headers, params=search_params)
            self._extract_rate_limit_info(response, "search")
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    tweets = data['data']
                    sorted_tweets = sorted(tweets, key=lambda x: x.get('created_at', ''))
                    return sorted_tweets
                else:
                    return []
            elif response.status_code == 429:
                reset_time = int(response.headers.get('x-rate-limit-reset', time.time() + 900))
                self.rate_limit_reset["search"] = reset_time
                console.print("[yellow]⚠️  Rate limited! Waiting for quota reset...[/yellow]")
                return self.search_conversation(conversation_id, author_id)
            else:
                console.print(f"[yellow]⚠️  Search API error {response.status_code}: {response.text}[/yellow]")
                return []
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not search conversation: {e}[/yellow]")
            return []

