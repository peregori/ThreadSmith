# 🧵 Threadsmith

A CLI tool that syncs your **Twitter/X bookmarks**, reconstructs full threads, and converts them into **Cursor `.mdc` rules** using **local LLM inference**.

## 🧩 Overview

**Purpose:**  
Turn your saved (bookmarked) X threads into reusable `.mdc` rules for Cursor — automatically tagged, cleaned, and saved locally.

**Core principle:**  
> Local-first. Manual sync. Full control. No cloud dependencies.

## 📦 Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your `config.json` with Twitter/X OAuth2 credentials:
   - Copy `config.example.json` to `config.json`
   - Add your Twitter API credentials (OAuth2 Client ID, Client Secret)
   - Get OAuth2 tokens with proper PKCE flow
   - Redirect URI must be: `http://localhost:3000/callback`

4. Set up local LLM with llama.cpp:
   - Install llama.cpp or llama-cpp-python
   - Download a GGUF model (Qwen, Gemma, Llama, etc.)
   - Update `llama_model_path` in `config.json`

See [INSTALL.md](INSTALL.md) for detailed setup instructions.

## 🚀 Usage

### Simple Commands

```bash
# Sync your bookmarks → convert to .mdc
threadsmith sync

# Add a specific thread
threadsmith add "https://x.com/someone/status/123"

# List processed threads
threadsmith ls

# Switch models
threadsmith ls-models          # See available
threadsmith use qwen3          # Switch model

# Test credentials
threadsmith auth
```

See [USAGE_SIMPLE.md](USAGE_SIMPLE.md) for complete guide.

## ⚠️ Important: Rate Limits

Twitter's **free tier allows 1 request per 15 minutes**. 

This means:
- Processing 5 threads = ~75 minutes
- Best used: End of day batch sync
- Be patient, let it run!

See [RATE_LIMITS.md](RATE_LIMITS.md) for optimization details.

## 🎯 Cursor Integration

**Auto-load rules in all projects:**

1. Set output folder in `config.json`:
   ```json
   "output_folder": "~/.cursor/rules/"
   ```

2. Create the directory:
   ```bash
   mkdir -p ~/.cursor/rules/twitter
   ```

3. Cursor automatically loads all `.mdc` files from `~/.cursor/rules/` in **every project**!

No need to copy rules manually - they're available globally! 🎉

## 📂 Project Structure

```
threadsmith/
├── threadsmith.py           # Main application
├── threadsmith              # Shell wrapper
├── config.json              # Your credentials (create from example)
├── config.example.json      # Template
├── requirements.txt         # Python dependencies
├── data/                    # Tracking data (auto-created)
└── README.md                # This file
```

## 📖 Documentation

- [INSTALL.md](INSTALL.md) - Installation & setup
- [USAGE_SIMPLE.md](USAGE_SIMPLE.md) - Usage examples
- [RATE_LIMITS.md](RATE_LIMITS.md) - Understanding Twitter API limits

## 🐛 Troubleshooting

**"Authentication failed"**
```bash
threadsmith auth  # Test credentials
# Check config.json has valid Twitter API tokens
```

**"Rate limited"**
- Normal! Free tier = 1 req/15 min
- Be patient, let it run
- See RATE_LIMITS.md

**"gum not found"**
```bash
brew install gum
```

## 💡 Tips

- **Bookmark during day, sync at night** - Best workflow
- **Use batch mode** - Process multiple threads at once
- **Point to Cursor rules** - Auto-load in all projects
- **Be patient** - Free tier is slow but works!

## 🤝 Contributing

Issues and PRs welcome!

## 📄 License

GPL-3.0 - See [LICENSE.txt](LICENSE.txt) for details.

Copyright (C) 2025

---
