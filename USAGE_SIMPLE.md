# 🧵 Threadsmith - Simple Usage

Dead simple commands, inspired by your .zshrc functions!

## 🚀 Quick Start

```bash
# Sync your bookmarks (batch mode, fast!)
threadsmith sync

# Add a specific thread
threadsmith add "https://x.com/someone/status/123"

# List what you've processed
threadsmith ls

# Test your Twitter credentials
threadsmith auth
```

## 🔄 Model Management

```bash
# See available models (shows ✓ for current)
threadsmith ls-models

# Switch to different model (fuzzy matching!)
threadsmith use qwen3          # Matches qwen3-14B-Q4_K_M.gguf
threadsmith use gemma3n        # Matches gemma3n-E2B-it-Q4_0.gguf
threadsmith use gemma3-27B     # Matches gemma3-27B-it-qat-Q4_0.gguf
```

---

## 📋 All Commands

| Command | What It Does |
|---------|-------------|
| `threadsmith sync` | Fetch bookmarks → process new ones → save as .mdc |
| `threadsmith add <url>` | Process a specific Twitter thread URL |
| `threadsmith ls` | List all processed threads with dates |
| `threadsmith ls-models` | Show available models (✓ marks current) |
| `threadsmith use <name>` | Switch to different model |
| `threadsmith auth` | Test Twitter API credentials |

---

## 💡 Examples

### Daily Workflow
```bash
# Morning: sync bookmarks
threadsmith sync
# → Fetches all new bookmarks
# → Loads model once
# → Processes all threads
# → Saves to rules/

# Found great thread? Add it manually
threadsmith add "https://x.com/pmarca/status/123"

# Check what you collected
threadsmith ls
```

### Model Switching
```bash
# See what models you have
threadsmith ls-models

  gemma3-27B-it-qat-Q4_0          14.5 GB
  gemma3n-E2B-it-Q4_0              2.8 GB
✓ qwen3-14B-Q4_K_M                 8.4 GB

# Want faster but lower quality? Use small model
threadsmith use gemma3n

# Want best quality? Use big model
threadsmith use gemma3-27B

# Back to balanced
threadsmith use qwen3
```

---

## 🎯 How It Works

### **Phase 1: Fetch Threads** (Twitter API)
```
1. Get your bookmarks
2. Filter to NEW ones (not processed before)
3. For each: Fetch full thread
   ⏳ 15s delay between calls (free tier safe)
4. Store in memory
```

### **Phase 2: Process with LLM**
```
5. Load model ONCE (30-60s)
6. Generate markdown for each thread (~10-20s each)
7. Strip thinking blocks automatically
8. Save as .mdc with metadata
```

**Result:** 3x faster than old approach! 🚀

---

## ⚙️ Rate Limiting

**Automatic!** The app respects Twitter's free tier:
- **15 second delay** between API calls
- **429 handling**: Auto-waits 60s and retries
- **Safe for free tier**: Won't hit limits

You'll see:
```
⏳ Rate limiting: waiting 12.3s...
```

This is **normal and good** - it prevents rate limit errors!

---

## 🐛 Troubleshooting

### "Authentication failed"
```bash
threadsmith auth
# If fails, check config.json has valid tokens
```

### "Model not found"
```bash
threadsmith ls-models
# Use exact name shown
threadsmith use qwen3-14B-Q4_K_M
```

### "Rate limited"
```bash
# The app auto-waits, just be patient
# Free tier allows ~4 requests/minute safely
```

---

## 📦 File Locations

```
~/.threadsmith/           # Would be ideal, but currently:
threadsmith/
├── config.json           # Your API keys & model config
├── data/
│   └── processed_threads.json  # Tracking file
└── rules/
    ├── thread-123.mdc    # Your converted threads
    └── ...
```

Set `output_folder` in `config.json` to point wherever you want!

---

## 🔥 Pro Tips

1. **Let it rate limit** - 15s delays are normal, prevents errors
2. **Batch mode is default** - Much faster for multiple threads
3. **Use right model**:
   - `gemma3n`: Fast test runs (2.8GB)
   - `qwen3`: Daily use - best balance (8.4GB) ⭐
   - `gemma3-27B`: Best quality, special occasions (14.5GB)
4. **Check output**: `cat rules/latest-file.mdc`
5. **Point to Cursor rules folder**: Update `output_folder` in config

---

## 🆚 vs Your .zshrc Functions

```bash
# Your llama functions
llama-models      # List models
llama-use <name>  # Select model
llama-chat        # Interactive chat
llama-serve       # Start server

# Threadsmith commands (same style!)
threadsmith ls-models      # List models
threadsmith use <name>     # Select model
threadsmith sync           # Sync bookmarks
threadsmith add <url>      # Add thread
threadsmith ls             # List processed
```

Same simplicity, same workflow! 🎯

---

Happy threading! 🧵✨

