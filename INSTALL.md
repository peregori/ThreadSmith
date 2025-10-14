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

1. Go to [Twitter Developer Portal](https://developer.twitter.com)
2. Create a new app
3. Enable OAuth 2.0 with these scopes:
   - `tweet.read`
   - `users.read`
   - `bookmark.read`
   - `offline.access`
4. Get your credentials:
   - Client ID
   - Client Secret
   - Access Token (use OAuth flow)
   - Refresh Token
5. Add to `config.json`

**Note:** Free tier has strict limits (1 request per 15 minutes). See `RATE_LIMITS.md` for details.

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
- Run `threadsmith auth` to test

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

