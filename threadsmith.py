#!/usr/bin/env python3
"""
Threadsmith - Twitter/X bookmark to Cursor rule converter
A CLI tool that syncs your Twitter/X bookmarks, reconstructs full threads,
and converts them into Cursor .mdc rules using local LLM inference.
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import requests
from requests_oauthlib import OAuth2Session
from slugify import slugify
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(help="🧵 Threadsmith - Twitter bookmarks to Cursor rules")
console = Console()

# Global model override for all commands
model_override: Optional[str] = None


class ThreadSmith:
    """Core Threadsmith functionality"""
    
    def __init__(self, config_path: str = "config.json", model_override: str = None):
        """Initialize ThreadSmith with configuration."""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # Override model if specified
        if model_override:
            self.config['llama_model_path'] = model_override
        
        self.base_dir = Path(__file__).parent.absolute()
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Set up processed threads tracking
        self.processed_file = Path(self.config.get(
            "processed_threads_file", 
            "./data/processed_threads.json"
        ))
        self.processed_file.parent.mkdir(exist_ok=True, parents=True)
        self.processed_tweets = self._load_processed_tweets()
        
        # Rate limiting (Twitter free tier: 1 request per 15 minutes!)
        self.last_api_call = 0
        self.min_delay = 900  # 900 seconds = 15 minutes between calls
        
        # Cache user_id to avoid extra API calls
        self.cached_user_id = None
        
    def _load_config(self) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Validate required fields
            required = ['oauth2_client_id', 'oauth2_access_token']
            missing = [field for field in required if field not in config]
            if missing:
                console.print(f"[red]❌ Missing required config fields: {missing}[/red]")
                sys.exit(1)
            
            return config
        except FileNotFoundError:
            console.print(f"[red]❌ Config file '{self.config_path}' not found.[/red]")
            sys.exit(1)
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ Invalid JSON in config file: {e}[/red]")
            sys.exit(1)
    
    def _save_config(self):
        """Save configuration back to JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _load_processed_tweets(self) -> set:
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
    
    def _check_and_refresh_token(self) -> bool:
        """Check if access token is expired and refresh if needed."""
        if 'oauth2_refresh_token' not in self.config:
            return True  # No refresh token, assume token is valid
        
        # Try to make a simple API call to test the token
        headers = {"Authorization": f"Bearer {self.config['oauth2_access_token']}"}
        try:
            response = requests.get("https://api.twitter.com/2/users/me", headers=headers)
            if response.status_code == 200:
                return True  # Token is valid
            
            if response.status_code == 401:
                console.print("[yellow]🔄 Access token expired, refreshing...[/yellow]")
                return self._refresh_access_token()
        except:
            pass
        
        return True
    
    def _refresh_access_token(self) -> bool:
        """Refresh the OAuth2 access token using refresh token."""
        if 'oauth2_refresh_token' not in self.config:
            console.print("[red]❌ No refresh token available. Please re-authenticate.[/red]")
            return False
        
        token_url = "https://api.twitter.com/2/oauth2/token"
        
        # Use HTTP Basic Auth with client credentials
        import base64
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
                self._save_config()
                console.print("[green]✓ Token refreshed successfully[/green]")
                return True
            else:
                console.print(f"[red]❌ Token refresh failed: {response.text}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]❌ Token refresh error: {e}[/red]")
            return False
    
    def _rate_limit_wait(self):
        """Wait if needed to respect rate limits (15 min = 900s between calls!)."""
        elapsed = time.time() - self.last_api_call
        if self.last_api_call > 0 and elapsed < self.min_delay:
            wait_time = self.min_delay - elapsed
            wait_mins = wait_time / 60
            console.print(f"[yellow]⏳ Rate limit: waiting {wait_mins:.1f} minutes ({wait_time:.0f}s)...[/yellow]")
            console.print(f"[dim]   Free tier allows 1 request per 15 minutes[/dim]")
            time.sleep(wait_time)
        self.last_api_call = time.time()
    
    def _get_user_id(self) -> Optional[str]:
        """Get the authenticated user's ID (cached to avoid extra API calls)."""
        # Return cached if available
        if self.cached_user_id:
            return self.cached_user_id
        
        if not self._check_and_refresh_token():
            return None
        
        self._rate_limit_wait()
        
        url = "https://api.twitter.com/2/users/me"
        headers = {"Authorization": f"Bearer {self.config['oauth2_access_token']}"}
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                self.cached_user_id = response.json()['data']['id']
                return self.cached_user_id
            elif response.status_code == 429:
                console.print("[yellow]⚠️  Rate limited! Waiting 15 minutes...[/yellow]")
                time.sleep(900)
                return self._get_user_id()  # Retry
            else:
                console.print(f"[red]❌ Failed to get user ID: {response.text}[/red]")
                return None
        except Exception as e:
            console.print(f"[red]❌ Error getting user ID: {e}[/red]")
            return None
    
    def fetch_bookmarks(self) -> List[Dict]:
        """Fetch user's bookmarked tweets from Twitter API."""
        if not self._check_and_refresh_token():
            return []
        
        user_id = self._get_user_id()
        if not user_id:
            return []
        
        self._rate_limit_wait()
        
        max_results = self.config.get('max_results', 50)
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
            
            if response.status_code == 200:
                data = response.json()
                bookmarks = data.get('data', [])
                
                # Attach username information
                if 'includes' in data and 'users' in data['includes']:
                    users_map = {u['id']: u for u in data['includes']['users']}
                    for bookmark in bookmarks:
                        author_id = bookmark.get('author_id')
                        if author_id in users_map:
                            bookmark['author_username'] = users_map[author_id]['username']
                
                console.print(f"[green]✓ Found {len(bookmarks)} bookmarks[/green]")
                return bookmarks
            else:
                console.print(f"[red]❌ Failed to fetch bookmarks: {response.text}[/red]")
                return []
        except Exception as e:
            console.print(f"[red]❌ Error fetching bookmarks: {e}[/red]")
            return []
    
    def fetch_thread(self, tweet_id: str, conversation_id: str, author_id: str) -> List[Dict]:
        """Fetch all tweets in a thread by the same author (OPTIMIZED: 1 API call only!)."""
        if not self._check_and_refresh_token():
            return []
        
        self._rate_limit_wait()
        
        # OPTIMIZATION: Skip individual tweet fetch, use conversation search directly
        # This saves 1 API call per thread (15 minutes saved!)
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
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    tweets = data['data']
                    # Sort chronologically
                    sorted_tweets = sorted(tweets, key=lambda x: x.get('created_at', ''))
                    return sorted_tweets
            elif response.status_code == 429:
                console.print("[yellow]⚠️  Rate limited! Waiting 15 minutes...[/yellow]")
                time.sleep(900)
                return self.fetch_thread(tweet_id, conversation_id, author_id)
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not fetch thread: {e}[/yellow]")
        
        return []
    
    def _check_llm_server(self) -> bool:
        """Check if llama-server is running on localhost:8080"""
        try:
            response = requests.get("http://localhost:8080/health", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _generate_with_server(self, prompt: str) -> Optional[str]:
        """Use running llama-server (fastest!)"""
        url = "http://localhost:8080/completion"
        data = {
            "prompt": prompt,
            "n_predict": self.config.get('llama_max_tokens', 3000),
            "temperature": self.config.get('llama_temperature', 0.7),
            "stop": ["</s>"]  # Don't stop at "---" (markdown tables)
        }
        
        try:
            response = requests.post(url, json=data, timeout=180)
            if response.status_code == 200:
                result = response.json()
                return result.get('content', '').strip()
        except:
            pass
        return None
    
    def _load_llm_model(self):
        """Load LLM model once and return instance for reuse."""
        try:
            from llama_cpp import Llama
            
            model_path = self.config.get('llama_model_path')
            
            llm = Llama(
                model_path=model_path,
                n_ctx=self.config.get('llama_context_size', 8192),
                n_gpu_layers=-1,
                verbose=False
            )
            console.print("[green]✓ Model loaded and ready[/green]")
            return llm
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not load model: {e}[/yellow]")
            return None
    
    def _generate_with_python(self, prompt: str, model_path: str, llm_instance=None) -> Optional[str]:
        """Use llama-cpp-python (good balance)"""
        try:
            from llama_cpp import Llama
            
            # Use provided instance or load new one
            if llm_instance is None:
                console.print("[cyan]   Loading model into memory...[/cyan]")
                llm = Llama(
                    model_path=model_path,
                    n_ctx=self.config.get('llama_context_size', 8192),
                    n_gpu_layers=-1,
                    verbose=False
                )
                console.print("[cyan]   Generating response...[/cyan]")
            else:
                llm = llm_instance
                console.print("[cyan]   Generating with pre-loaded model...[/cyan]")
            
            output = llm(
                prompt,
                max_tokens=self.config.get('llama_max_tokens', 3000),
                temperature=self.config.get('llama_temperature', 0.7),
                stop=["</s>"],  # Don't stop at "---" (markdown tables)
                echo=False
            )
            
            return output['choices'][0]['text'].strip()
            
        except ImportError:
            console.print("[yellow]⚠️  llama-cpp-python not installed (pip install llama-cpp-python)[/yellow]")
            return None
        except Exception as e:
            console.print(f"[yellow]⚠️  Python bindings failed: {e}[/yellow]")
            return None
    
    def _generate_mdc(self, thread_text: str, tweet_url: str, llm_instance=None) -> Optional[str]:
        """Internal generation method that accepts pre-loaded LLM."""
        model_path = self.config.get('llama_model_path')
        
        if not model_path or not Path(model_path).exists():
            console.print(f"[red]❌ LLM model not found at: {model_path}[/red]")
            return None
        
        prompt = self._create_prompt(thread_text)
        
        # Strategy 1: Try llama-server if running
        if self._check_llm_server():
            console.print("[green]✓ Using llama-server[/green]")
            output = self._generate_with_server(prompt)
            if output:
                return self._clean_llm_output(output)
        
        # Strategy 2: Try llama-cpp-python with optional pre-loaded model
        output = self._generate_with_python(prompt, model_path, llm_instance)
        if output:
            return self._clean_llm_output(output)
        
        console.print("[red]❌ All LLM strategies failed[/red]")
        return None
    
    def generate_mdc_with_llm(self, thread_text: str, tweet_url: str) -> Optional[str]:
        """Generate .mdc content using local LLM with smart strategy selection."""
        return self._generate_mdc(thread_text, tweet_url, llm_instance=None)
    
    def _create_prompt(self, thread_text: str) -> str:
        """Create the LLM prompt."""
        return f"""You are converting a Twitter thread into a Cursor .mdc rule file.

Output ONLY the markdown content with:
- A clear H1 title
- A brief summary paragraph
- H2/H3 sections
- Bullet points and checklists
- Code examples if relevant

DO NOT include:
- YAML frontmatter (---)
- Explanations of what you're doing

Thread:
{thread_text}

Markdown content:"""
    
    def _clean_llm_output(self, output: str) -> str:
        """Clean up LLM output to extract just the markdown content."""
        # Remove any leading/trailing whitespace
        output = output.strip()
        
        # Remove thinking tags if present (Qwen3 and other reasoning models)
        if '<think>' in output or '</think>' in output:
            # Extract content after </think>
            parts = output.split('</think>')
            if len(parts) > 1:
                output = parts[-1].strip()
            # Remove any remaining <think> tags
            output = output.replace('<think>', '').replace('</think>', '').strip()
        
        # Remove any yaml frontmatter if present
        if output.startswith('---'):
            parts = output.split('---', 2)
            if len(parts) >= 3:
                output = parts[2].strip()
        
        return output
    
    def save_as_mdc(self, content: str, tweet_url: str, title: str = None) -> Optional[Path]:
        """Save content as .mdc file with metadata."""
        output_folder = Path(self.config.get('output_folder', './rules/'))
        output_folder.mkdir(exist_ok=True, parents=True)
        
        # Generate filename from title or URL
        if title:
            filename = slugify(title) + '.mdc'
        else:
            # Extract tweet ID from URL for filename
            tweet_id = tweet_url.split('/')[-1].split('?')[0]
            filename = f"twitter-thread-{tweet_id}.mdc"
        
        filepath = output_folder / filename
        
        # Create YAML frontmatter
        frontmatter = f"""---
alwaysApply: false
source: "{tweet_url}"
synced: "{datetime.now().isoformat()}"
---

"""
        
        # Combine frontmatter and content
        full_content = frontmatter + content
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(full_content)
            console.print(f"[green]✓ Saved: {filepath}[/green]")
            return filepath
        except Exception as e:
            console.print(f"[red]❌ Error saving file: {e}[/red]")
            return None
    
    def process_bookmark(self, bookmark: Dict) -> bool:
        """Process a single bookmark: fetch thread, generate .mdc."""
        tweet_id = bookmark['id']
        
        # Check if already processed
        if tweet_id in self.processed_tweets:
            return False
        
        console.print(f"\n[cyan]📝 Processing tweet {tweet_id}...[/cyan]")
        
        # Get thread information
        conversation_id = bookmark.get('conversation_id', tweet_id)
        author_id = bookmark.get('author_id')
        author_username = bookmark.get('author_username', 'unknown')
        
        # Fetch full thread
        thread_tweets = self.fetch_thread(tweet_id, conversation_id, author_id)
        
        if not thread_tweets:
            console.print(f"[yellow]⚠️  No tweets found in thread[/yellow]")
            return False
        
        console.print(f"[green]✓ Found {len(thread_tweets)} tweets in thread[/green]")
        
        # Combine thread text
        thread_text = "\n\n".join([
            f"Tweet {i+1}:\n{tweet.get('text', '')}"
            for i, tweet in enumerate(thread_tweets)
        ])
        
        # Generate tweet URL
        tweet_url = f"https://x.com/{author_username}/status/{tweet_id}"
        
        # Generate .mdc content with LLM
        mdc_content = self.generate_mdc_with_llm(thread_text, tweet_url)
        
        if not mdc_content:
            console.print("[red]❌ Failed to generate .mdc content[/red]")
            return False
        
        # Extract title from first line of content if it's a heading
        title = None
        lines = mdc_content.split('\n')
        if lines and lines[0].startswith('# '):
            title = lines[0][2:].strip()
        
        # Save as .mdc
        saved_path = self.save_as_mdc(mdc_content, tweet_url, title)
        
        if saved_path:
            # Mark as processed
            self.processed_tweets.add(tweet_id)
            self._save_processed_tweets()
            return True
        
        return False
    
    def sync_bookmarks(self, batch_mode: bool = True):
        """Main sync command: fetch new bookmarks and convert to .mdc."""
        console.print("[bold cyan]🔄 Starting bookmark sync...[/bold cyan]")
        
        # Fetch bookmarks
        bookmarks = self.fetch_bookmarks()
        
        if not bookmarks:
            console.print("[yellow]No bookmarks found or error fetching[/yellow]")
            return
        
        # Filter to new bookmarks only
        new_bookmarks = [b for b in bookmarks if b['id'] not in self.processed_tweets]
        
        if not new_bookmarks:
            console.print("[green]✓ All bookmarks already processed[/green]")
            return
        
        console.print(f"[cyan]📚 Found {len(new_bookmarks)} new bookmarks to process[/cyan]")
        
        if batch_mode and len(new_bookmarks) > 1:
            # BATCH MODE: Fetch all threads first, then process with LLM
            console.print("[cyan]🔄 Phase 1: Fetching all threads from Twitter...[/cyan]")
            thread_data = []
            
            for i, bookmark in enumerate(new_bookmarks, 1):
                console.print(f"   Fetching thread {i}/{len(new_bookmarks)}...", end=" ")
                
                tweet_id = bookmark['id']
                conversation_id = bookmark.get('conversation_id', tweet_id)
                author_id = bookmark.get('author_id')
                author_username = bookmark.get('author_username', 'unknown')
                
                # Fetch thread tweets
                thread_tweets = self.fetch_thread(tweet_id, conversation_id, author_id)
                
                if thread_tweets:
                    thread_text = "\n\n".join([
                        f"Tweet {j+1}:\n{tweet.get('text', '')}"
                        for j, tweet in enumerate(thread_tweets)
                    ])
                    tweet_url = f"https://x.com/{author_username}/status/{tweet_id}"
                    
                    thread_data.append({
                        'tweet_id': tweet_id,
                        'tweet_url': tweet_url,
                        'thread_text': thread_text,
                        'thread_count': len(thread_tweets)
                    })
                    console.print(f"[green]✓ ({len(thread_tweets)} tweets)[/green]")
                else:
                    console.print("[yellow]⚠️  Failed[/yellow]")
                
                # Rate limiting handled by _rate_limit_wait() in fetch_thread()
            
            console.print(f"\n[cyan]🧠 Phase 2: Processing {len(thread_data)} threads with LLM...[/cyan]")
            
            # Load LLM once if using llama-cpp-python
            llm_instance = None
            use_python_bindings = not self._check_llm_server()
            
            if use_python_bindings:
                console.print("[cyan]   Loading model into memory (one time)...[/cyan]")
                llm_instance = self._load_llm_model()
            
            # Process all threads
            processed_count = 0
            for i, data in enumerate(thread_data, 1):
                console.print(f"\n[bold]Generating .mdc {i}/{len(thread_data)}[/bold]")
                
                # Generate with pre-loaded model
                mdc_content = self._generate_mdc(data['thread_text'], data['tweet_url'], llm_instance)
                
                if mdc_content:
                    # Extract title
                    title = None
                    lines = mdc_content.split('\n')
                    if lines and lines[0].startswith('# '):
                        title = lines[0][2:].strip()
                    
                    # Save
                    saved_path = self.save_as_mdc(mdc_content, data['tweet_url'], title)
                    if saved_path:
                        self.processed_tweets.add(data['tweet_id'])
                        self._save_processed_tweets()
                        processed_count += 1
            
            console.print(f"\n[bold green]✓ Sync complete! Processed {processed_count} new threads[/bold green]")
        else:
            # SEQUENTIAL MODE: One at a time (old behavior)
            processed_count = 0
            for i, bookmark in enumerate(new_bookmarks, 1):
                console.print(f"\n[bold]Processing {i}/{len(new_bookmarks)}[/bold]")
                if self.process_bookmark(bookmark):
                    processed_count += 1
                
                if i < len(new_bookmarks):
                    time.sleep(2)
            
            console.print(f"\n[bold green]✓ Sync complete! Processed {processed_count} new threads[/bold green]")
    
    def process_url(self, url: str) -> bool:
        """Process a single Twitter/X URL manually."""
        # Extract tweet ID from URL
        tweet_id = self._extract_tweet_id(url)
        
        if not tweet_id:
            console.print(f"[red]❌ Could not extract tweet ID from URL: {url}[/red]")
            return False
        
        console.print(f"[cyan]Processing tweet: {tweet_id}[/cyan]")
        
        # Fetch the tweet to get metadata
        if not self._check_and_refresh_token():
            return False
        
        api_url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        headers = {"Authorization": f"Bearer {self.config['oauth2_access_token']}"}
        params = {
            "tweet.fields": "conversation_id,created_at,author_id,text",
            "expansions": "author_id",
            "user.fields": "username"
        }
        
        try:
            response = requests.get(api_url, headers=headers, params=params)
            if response.status_code != 200:
                console.print(f"[red]❌ Failed to fetch tweet: {response.text}[/red]")
                return False
            
            data = response.json()
            tweet_data = data.get('data')
            
            if not tweet_data:
                console.print("[red]❌ Tweet not found[/red]")
                return False
            
            # Get author username
            author_username = 'unknown'
            if 'includes' in data and 'users' in data['includes']:
                users = data['includes']['users']
                if users:
                    author_username = users[0]['username']
            
            # Create bookmark-like structure
            bookmark = {
                'id': tweet_id,
                'conversation_id': tweet_data.get('conversation_id', tweet_id),
                'author_id': tweet_data.get('author_id'),
                'author_username': author_username,
                'text': tweet_data.get('text', '')
            }
            
            return self.process_bookmark(bookmark)
            
        except Exception as e:
            console.print(f"[red]❌ Error processing URL: {e}[/red]")
            return False
    
    def _extract_tweet_id(self, url: str) -> Optional[str]:
        """Extract tweet ID from Twitter/X URL."""
        # Handle various URL formats
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
        
        # If it's just a number, assume it's a tweet ID
        if url.isdigit():
            return url
        
        return None
    
    def list_processed(self):
        """List all processed threads."""
        output_folder = Path(self.config.get('output_folder', './rules/'))
        
        if not output_folder.exists():
            console.print("[yellow]No rules folder found[/yellow]")
            return
        
        mdc_files = sorted(output_folder.glob('*.mdc'), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not mdc_files:
            console.print("[yellow]No .mdc files found[/yellow]")
            return
        
        table = Table(title="📚 Processed Threads")
        table.add_column("File", style="cyan")
        table.add_column("Modified", style="green")
        table.add_column("Source", style="blue")
        
        for mdc_file in mdc_files:
            # Read metadata
            try:
                with open(mdc_file, 'r') as f:
                    content = f.read()
                    # Extract source from frontmatter
                    source = "N/A"
                    if content.startswith('---'):
                        parts = content.split('---', 2)
                        if len(parts) >= 2:
                            frontmatter = parts[1]
                            for line in frontmatter.split('\n'):
                                if line.startswith('source:'):
                                    source = line.split('source:')[1].strip().strip('"')
                                    break
                
                mtime = datetime.fromtimestamp(mdc_file.stat().st_mtime)
                table.add_row(
                    mdc_file.name,
                    mtime.strftime("%Y-%m-%d %H:%M"),
                    source
                )
            except:
                continue
        
        console.print(table)
        console.print(f"\n[green]Total: {len(mdc_files)} files[/green]")


# CLI Commands - Ultra Simple (Like .zshrc)

def _select_model_with_gum() -> Optional[Path]:
    """Use gum to interactively select a model."""
    cache_dir = Path.home() / "Library/Caches/llama.cpp"
    models = sorted(cache_dir.glob("*.gguf"))
    
    if not models:
        console.print("[yellow]No models found[/yellow]")
        return None
    
    # Get current model
    try:
        with open("config.json") as f:
            config = json.load(f)
            current = Path(config.get('llama_model_path', ''))
    except:
        current = None
    
    # Prepare choices with sizes
    choices = []
    for model in models:
        size_gb = model.stat().st_size / (1024**3)
        marker = "✓ " if model == current else "  "
        choice = f"{marker}{model.stem} ({size_gb:.1f} GB)"
        choices.append(choice)
    
    # Use gum to select
    try:
        result = subprocess.run(
            ["gum", "choose", "--header", "💬 Select a model:"] + choices,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            selected = result.stdout.strip()
            # Extract model name from choice
            model_name = selected.split('(')[0].strip().replace('✓ ', '').strip()
            
            # Find the model
            for model in models:
                if model.stem == model_name:
                    return model
        return None
    except FileNotFoundError:
        console.print("[yellow]⚠️  gum not found, install with: brew install gum[/yellow]")
        # Fallback: use first model
        return models[0] if models else None


@app.command(name="sync")
def cmd_sync():
    """Sync bookmarks → convert to .mdc rules"""
    # Use global model override if provided, otherwise interactive selection
    if model_override:
        selected_model = Path(model_override)
        if not selected_model.exists():
            console.print(f"[red]❌ Model not found: {model_override}[/red]")
            raise typer.Exit(code=1)
    else:
        # Interactive model selection with gum
        console.print("[cyan]🔍 Select model for processing...[/cyan]")
        selected_model = _select_model_with_gum()
        
        if not selected_model:
            console.print("[red]❌ No model selected[/red]")
            raise typer.Exit(code=1)
    
    size_gb = selected_model.stat().st_size / (1024**3)
    console.print(f"[green]✓ Using: {selected_model.name} ({size_gb:.1f} GB)[/green]\n")
    
    # Initialize with selected model
    smith = ThreadSmith(model_override=str(selected_model))
    smith.sync_bookmarks()


@app.command(name="add")
def cmd_add(url: str):
    """Add a thread: threadsmith add <url>"""
    # Use global model override if provided, otherwise interactive selection
    if model_override:
        selected_model = Path(model_override)
        if not selected_model.exists():
            console.print(f"[red]❌ Model not found: {model_override}[/red]")
            raise typer.Exit(code=1)
    else:
        # Interactive model selection with gum
        console.print("[cyan]🔍 Select model for processing...[/cyan]")
        selected_model = _select_model_with_gum()
        
        if not selected_model:
            console.print("[red]❌ No model selected[/red]")
            raise typer.Exit(code=1)
    
    size_gb = selected_model.stat().st_size / (1024**3)
    console.print(f"[green]✓ Using: {selected_model.name} ({size_gb:.1f} GB)[/green]\n")
    
    smith = ThreadSmith(model_override=str(selected_model))
    if smith.process_url(url):
        console.print("[green]✓ Done![/green]")
    else:
        raise typer.Exit(code=1)


@app.command(name="ls")
def cmd_ls():
    """List processed threads"""
    smith = ThreadSmith()
    smith.list_processed()


@app.command(name="status")
def cmd_status():
    """Check Twitter API connection status"""
    smith = ThreadSmith()
    
    console.print("[cyan]🔍 Checking Twitter API status...[/cyan]")
    
    # Test the current token
    if smith._check_and_refresh_token():
        user_id = smith._get_user_id()
        if user_id:
            console.print("[green]✅ Twitter API connection successful![/green]")
            console.print(f"[green]User ID: {user_id}[/green]")
        else:
            console.print("[red]❌ Failed to get user ID[/red]")
    else:
        console.print("[red]❌ Token refresh failed. Run 'threadsmith reauth' to re-authenticate.[/red]")


@app.command(name="reauth")
def cmd_reauth():
    """Re-authenticate with Twitter (manual OAuth flow)"""
    console.print("[cyan]🔄 Starting Twitter OAuth2 re-authentication...[/cyan]")
    
    # Load current config
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        console.print("[red]❌ config.json not found. Please set up your configuration first.[/red]")
        raise typer.Exit(code=1)
    
    client_id = config.get('oauth2_client_id')
    client_secret = config.get('oauth2_client_secret')
    
    if not client_id or not client_secret:
        console.print("[red]❌ Missing client_id or client_secret in config.json[/red]")
        raise typer.Exit(code=1)
    
    # Manual OAuth2 flow
    console.print("\n[yellow]📋 Manual OAuth2 Flow:[/yellow]")
    console.print("1. Visit the authorization URL below")
    console.print("2. Authorize the application")
    console.print("3. You'll be redirected to http://localhost:3000/callback with a code parameter")
    console.print("4. Copy the authorization code from the URL and paste it here")
    console.print("\n[green]✅ Using your registered redirect URI: http://localhost:3000/callback[/green]\n")
    
    # Generate authorization URL manually
    import secrets
    import hashlib
    import base64
    
    # Generate PKCE parameters
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    state = secrets.token_urlsafe(32)
    
    # Build authorization URL with PKCE
    auth_params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': 'http://localhost:3000/callback',
        'scope': 'tweet.read users.read bookmark.read offline.access',
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }
    
    from urllib.parse import urlencode
    auth_url = "https://twitter.com/i/oauth2/authorize?" + urlencode(auth_params)
    
    console.print(f"[cyan]Authorization URL:[/cyan]")
    console.print(f"[blue]{auth_url}[/blue]\n")
    
    # Get authorization code from user
    redirect_url = input("Enter the full redirect URL or just the authorization code: ").strip()
    
    if not redirect_url:
        console.print("[red]❌ No redirect URL or authorization code provided[/red]")
        raise typer.Exit(code=1)
    
    # Extract authorization code from URL if full URL was provided
    if redirect_url.startswith('http'):
        try:
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(redirect_url)
            query_params = parse_qs(parsed_url.query)
            
            if 'code' not in query_params:
                console.print("[red]❌ No authorization code found in redirect URL[/red]")
                raise typer.Exit(code=1)
            
            auth_code = query_params['code'][0]
            console.print(f"[green]✓ Extracted authorization code: {auth_code[:20]}...[/green]")
        except Exception as e:
            console.print(f"[red]❌ Error parsing redirect URL: {e}[/red]")
            raise typer.Exit(code=1)
    else:
        # Assume it's just the authorization code
        auth_code = redirect_url
    
    try:
        # Exchange authorization code for tokens
        token_url = "https://api.twitter.com/2/oauth2/token"
        
        # Use HTTP Basic Auth with client credentials
        import base64
        client_credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(client_credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': 'http://localhost:3000/callback',
            'code_verifier': code_verifier
        }
        
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Update config with new tokens
            config['oauth2_access_token'] = token_data['access_token']
            if 'refresh_token' in token_data:
                config['oauth2_refresh_token'] = token_data['refresh_token']
            
            # Save updated config
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=2)
            
            console.print("[green]✅ Authentication successful! Tokens updated.[/green]")
            console.print("[green]You can now use threadsmith commands.[/green]")
        else:
            console.print(f"[red]❌ Token exchange failed: {response.text}[/red]")
            raise typer.Exit(code=1)
        
    except Exception as e:
        console.print(f"[red]❌ Authentication failed: {e}[/red]")
        raise typer.Exit(code=1)


def main(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Path to LLM model file")
):
    """🧵 Threadsmith - Twitter bookmarks to Cursor rules"""
    global model_override
    model_override = model

if __name__ == "__main__":
    app.callback()(main)
    app()
