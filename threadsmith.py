#!/usr/bin/env python3
"""
Threadsmith v2 - Modular Twitter thread fetcher
A CLI tool that syncs your Twitter/X bookmarks and saves threads locally.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.twitter_client import TwitterClient
from src.thread_manager import ThreadManager
from src.storage import ThreadStorage

app = typer.Typer(help="🧵 Threadsmith - Twitter thread fetcher")
console = Console()


class Threadsmith:
    """Main Threadsmith application."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize Threadsmith with configuration."""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # Initialize components
        self.twitter_client = TwitterClient(self.config)
        self.thread_manager = ThreadManager(self.twitter_client)
        
        # Set up storage
        self.data_dir = Path("./data")
        self.threads_dir = Path(self.config.get('threads_folder', './data/threads'))
        self.storage = ThreadStorage(self.data_dir, self.threads_dir)
    
    def _load_config(self):
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
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
    
    def sync_bookmarks(self):
        """Sync bookmarks and save threads locally."""
        console.print("[bold cyan]🔄 Starting bookmark sync...[/bold cyan]\n")
        
        # Fetch bookmarks
        max_results = self.config.get('max_results', 50)
        bookmarks = self.twitter_client.fetch_bookmarks(max_results)
        
        # Save config if token was refreshed
        if self.twitter_client.config != self.config:
            self.config = self.twitter_client.config
            self._save_config()
            console.print("[dim]✓ Updated config with refreshed token[/dim]")
        
        if not bookmarks:
            console.print("[yellow]No bookmarks found or error fetching[/yellow]")
            return
        
        # Filter new bookmarks
        new_bookmarks = [b for b in bookmarks if not self.storage.is_processed(b['id'])]
        
        if not new_bookmarks:
            console.print("[green]✓ All bookmarks already processed[/green]")
            return
        
        console.print(f"[cyan]📚 Found {len(new_bookmarks)} new bookmarks to process[/cyan]\n")
        
        # Process each bookmark
        processed_count = 0
        for i, bookmark in enumerate(new_bookmarks, 1):
            console.print(f"[bold]Processing {i}/{len(new_bookmarks)}[/bold]")
            
            tweet_id = bookmark['id']
            conversation_id = bookmark.get('conversation_id', tweet_id)
            author_id = bookmark.get('author_id')
            author_username = bookmark.get('author_username', 'unknown')
            
            # Fetch thread
            thread_tweets = self.thread_manager.fetch_thread(
                tweet_id, conversation_id, author_id
            )
            
            if not thread_tweets:
                console.print("[yellow]⚠️  Skipping - no tweets found[/yellow]\n")
                continue
            
            # Build metadata
            metadata = self.thread_manager.build_thread_metadata(
                thread_tweets, tweet_id, author_username
            )
            
            # Generate clean markdown for LLM processing
            markdown_content = self.thread_manager.reconstruct_thread_markdown(
                thread_tweets, author_username
            )
            
            # Save thread (both JSON and Markdown)
            saved_path = self.storage.save_thread(metadata, markdown_content)
            if saved_path:
                processed_count += 1
            
            console.print()  # Empty line for spacing
        
        console.print(f"[bold green]✅ Sync complete! Processed {processed_count} new threads[/bold green]")
        
        # Show stats
        stats = self.storage.get_stats()
        console.print(f"[dim]Total threads saved: {stats['total_threads']}[/dim]")
        console.print(f"[dim]Storage: {stats['storage_path']}[/dim]")
    
    def add_thread(self, url: str) -> bool:
        """Add a single thread by URL."""
        console.print(f"[cyan]📥 Adding thread from URL...[/cyan]\n")
        
        # Extract tweet ID
        tweet_id = self.thread_manager.extract_tweet_id(url)
        if not tweet_id:
            console.print(f"[red]❌ Could not extract tweet ID from URL: {url}[/red]")
            return False
        
        # Check if already processed
        if self.storage.is_processed(tweet_id):
            console.print(f"[yellow]⚠️  Tweet {tweet_id} already processed[/yellow]")
            return False
        
        # Fetch tweet metadata
        tweet = self.twitter_client.fetch_single_tweet(tweet_id)
        if not tweet:
            console.print("[red]❌ Failed to fetch tweet[/red]")
            return False
        
        conversation_id = tweet.get('conversation_id', tweet_id)
        author_id = tweet.get('author_id')
        
        # Fetch thread
        thread_tweets = self.thread_manager.fetch_thread(
            tweet_id, conversation_id, author_id
        )
        
        if not thread_tweets:
            console.print("[red]❌ Failed to fetch thread[/red]")
            return False
        
        # Build metadata (extract username from URL if possible)
        author_username = None
        import re
        username_match = re.search(r'(?:twitter|x)\.com/(\w+)/status', url)
        if username_match:
            author_username = username_match.group(1)
        
        metadata = self.thread_manager.build_thread_metadata(
            thread_tweets, tweet_id, author_username
        )
        
        # Generate clean markdown for LLM processing
        markdown_content = self.thread_manager.reconstruct_thread_markdown(
            thread_tweets, author_username
        )
        
        # Save thread (both JSON and Markdown)
        saved_path = self.storage.save_thread(metadata, markdown_content)
        
        # Save config if token was refreshed
        if self.twitter_client.config != self.config:
            self.config = self.twitter_client.config
            self._save_config()
            console.print("[dim]✓ Updated config with refreshed token[/dim]")
        
        if saved_path:
            console.print(f"\n[green]✅ Thread saved successfully![/green]")
            return True
        
        return False
    
    def list_threads(self):
        """List all saved threads."""
        threads = self.storage.list_threads()
        
        if not threads:
            console.print("[yellow]No threads found[/yellow]")
            return
        
        table = Table(title="📚 Saved Threads")
        table.add_column("Author", style="cyan")
        table.add_column("Tweet ID", style="yellow")
        table.add_column("Tweets", style="green")
        table.add_column("Saved", style="blue")
        table.add_column("File", style="dim")
        
        for thread in threads:
            table.add_row(
                thread['author'],
                thread['tweet_id'],
                str(thread['tweet_count']),
                thread['saved_at'][:19] if thread['saved_at'] else 'N/A',
                thread['filename']
            )
        
        console.print(table)
        console.print(f"\n[green]Total: {len(threads)} threads[/green]")
        
        # Show stats
        stats = self.storage.get_stats()
        console.print(f"[dim]Storage: {stats['storage_path']}[/dim]")
    
    def test_auth(self):
        """Test Twitter API authentication."""
        console.print("[cyan]🔍 Testing Twitter API authentication...[/cyan]\n")
        
        user_id = self.twitter_client.get_user_id()
        if user_id:
            console.print("[green]✅ Authentication successful![/green]")
            console.print(f"[green]User ID: {user_id}[/green]")
            
            # Update config if token was refreshed
            if self.twitter_client.config != self.config:
                self.config = self.twitter_client.config
                self._save_config()
                console.print("[green]✓ Updated config with refreshed token[/green]")
        else:
            console.print("[red]❌ Authentication failed[/red]")


@app.command(name="sync")
def cmd_sync():
    """Sync bookmarks → save threads locally"""
    smith = Threadsmith()
    smith.sync_bookmarks()


@app.command(name="add")
def cmd_add(url: str):
    """Add a specific thread: threadsmith add <url>"""
    smith = Threadsmith()
    if smith.add_thread(url):
        console.print("[green]✓ Done![/green]")
    else:
        raise typer.Exit(code=1)


@app.command(name="ls")
def cmd_ls():
    """List saved threads"""
    smith = Threadsmith()
    smith.list_threads()


@app.command(name="reauth")
def cmd_reauth():
    """Get fresh OAuth2 tokens (run once if refresh token expired)"""
    console.print("[bold cyan]🔐 Twitter OAuth2 Authentication[/bold cyan]\n")
    
    # Load config
    config_path = Path("config.json")
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    client_id = config.get('oauth2_client_id')
    
    if not client_id:
        console.print("[red]❌ oauth2_client_id not found in config.json[/red]")
        raise typer.Exit(code=1)
    
    # Build auth URL
    auth_url = f"https://twitter.com/i/oauth2/authorize?response_type=code&client_id={client_id}&redirect_uri=http://localhost:3000/callback&scope=tweet.read%20users.read%20bookmark.read%20offline.access&state=state&code_challenge=challenge&code_challenge_method=plain"
    
    # Open browser automatically
    console.print("🌐 Opening browser for Twitter authorization...\n")
    import webbrowser
    webbrowser.open(auth_url)
    
    console.print("[green]✓ Browser opened![/green]")
    console.print("After authorizing, you'll be redirected to a localhost URL.\n")
    console.print("Copy the ENTIRE redirect URL (or just the code from it)\n")
    
    user_input = typer.prompt("Paste redirect URL or code here")
    
    # Extract code from URL if full URL was pasted
    from urllib.parse import urlparse, parse_qs
    if 'code=' in user_input:
        parsed = urlparse(user_input)
        params = parse_qs(parsed.query)
        code = params.get('code', [user_input])[0]
    else:
        code = user_input
    
    # Exchange code for tokens
    import base64
    client_secret = config.get('oauth2_client_secret')
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    
    token_url = "https://api.twitter.com/2/oauth2/token"
    headers = {
        'Authorization': f'Basic {encoded}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'http://localhost:3000/callback',
        'code_verifier': 'challenge'
    }
    
    import requests
    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code == 200:
        tokens = response.json()
        config['oauth2_access_token'] = tokens['access_token']
        config['oauth2_refresh_token'] = tokens['refresh_token']
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        console.print("\n[green]✅ Success! Tokens saved to config.json[/green]")
        console.print("[dim]From now on, tokens will auto-refresh automatically[/dim]")
    else:
        console.print(f"\n[red]❌ Failed: {response.text}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

