# 🚀 Installation Guide

## Prerequisites

- Python 3.10+
- [llama.cpp](https://github.com/ggerganov/llama.cpp) with a GGUF model
- [gum](https://github.com/charmbracelet/gum) for interactive CLI
- Twitter API OAuth2 credentials

## Quick Install

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/threadsmith.git
cd threadsmith

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install gum (for interactive model selection)
brew install gum

# 4. Set up configuration
cp config.example.json config.json
# Edit config.json with your Twitter API credentials

# 5. Make executable
chmod +x threadsmith

# 6. Add to PATH (choose one):

# Option A: Symlink to /usr/local/bin
sudo ln -s "$(pwd)/threadsmith" /usr/local/bin/threadsmith

# Option B: Add to ~/.zshrc
echo 'export PATH="'$(pwd)':$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Twitter API Setup

### 1. Create Twitter App

1. Go to [Twitter Developer Portal](https://developer.twitter.com)
2. Create a new app (Project & App)
3. Navigate to your app settings

### 2. Configure OAuth 2.0

1. In app settings, go to "User authentication settings"
2. Set **OAuth 2.0** settings:
   - **Type of App**: Web App
   - **Callback URI / Redirect URL**: `http://localhost:3000/callback`
   - **Website URL**: `http://localhost:3000` (or your actual site)
3. Enable these scopes:
   - `tweet.read`
   - `users.read`
   - `bookmark.read`
   - `offline.access` (for refresh tokens)
4. Save settings

### 3. Get Credentials

1. Copy your **Client ID** and **Client Secret**
2. Generate OAuth 2.0 tokens using PKCE flow:
   - Use Twitter's OAuth 2.0 authorize URL
   - Redirect to `http://localhost:3000/callback`
   - Exchange code for access token + refresh token
3. Add all credentials to `config.json`:
   ```json
   {
     "oauth2_client_id": "YOUR_CLIENT_ID",
     "oauth2_client_secret": "YOUR_CLIENT_SECRET",
     "oauth2_access_token": "YOUR_ACCESS_TOKEN",
     "oauth2_refresh_token": "YOUR_REFRESH_TOKEN"
   }
   ```

**Important Notes:**
- Free tier: 1 request per 15 minutes (see `RATE_LIMITS.md`)
- Redirect URI must be exact: `http://localhost:3000/callback`
- Threadsmith auto-refreshes tokens using HTTP Basic Auth

## Llama.cpp Setup

```bash
# Install llama.cpp
brew install llama.cpp

# Download a model (e.g., Qwen3 14B)
# Models are typically in ~/Library/Caches/llama.cpp/

# Update config.json:
"llama_model_path": "~/Library/Caches/llama.cpp/qwen3-14B-Q4_K_M.gguf"
```

## Cursor Integration

To auto-load rules in all Cursor projects:

```bash
# Set output folder to Cursor's global rules directory
# In config.json:
"output_folder": "~/.cursor/rules/twitter/"
```

Cursor will automatically load all `.mdc` files from this folder in every project!

## Verify Installation

```bash
# Test CLI is available
threadsmith --help

# Test Twitter auth
threadsmith auth

# Should show:
# ✓ Authenticated! User ID: 123456789
```

## Usage

```bash
# Sync bookmarks (with interactive model selection)
threadsmith sync

# Add specific thread
threadsmith add "https://x.com/user/status/123"

# List processed threads
threadsmith ls
```

## Troubleshooting

### "threadsmith: command not found"
```bash
# Check PATH
which threadsmith

# If not found, add to PATH:
export PATH="/path/to/threadsmith:$PATH"
```

### "gum: command not found"
```bash
brew install gum
```

### "Authentication failed"
- Verify Twitter API credentials in `config.json`
- Check scopes include `bookmark.read` and `offline.access`
- Ensure redirect URI is exactly: `http://localhost:3000/callback`
- Regenerate OAuth2 tokens if needed (old tokens may be invalid)
- Run `threadsmith auth` to test
- If token expired, Threadsmith will auto-refresh using refresh token

### "Model not found"
```bash
# Check model path
ls ~/Library/Caches/llama.cpp/*.gguf

# Update config.json with correct path
```

## Uninstall

```bash
# Remove symlink (if used)
sudo rm /usr/local/bin/threadsmith

# Or remove from PATH in ~/.zshrc

# Delete repo
rm -rf /path/to/threadsmith
```

---

Happy threading! 🧵✨

