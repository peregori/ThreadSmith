# ⏱️ Twitter API Rate Limits & Optimization

## 🚨 The Problem: Free Tier is SLOW

Twitter API Free Tier: **1 request per 15 minutes** (900 seconds)

### Old Approach (Terrible!)
```
For 10 threads:
- Get user_id: 1 call (15 min)
- Get bookmarks: 1 call (15 min)
- For each thread:
  - Get tweet: 1 call (15 min)
  - Search conversation: 1 call (15 min)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 2 + (10 × 2) = 22 calls
Time: 22 × 15 minutes = 330 minutes = 5.5 hours!
```

### New Approach (Optimized!)
```
For 10 threads:
- Get user_id: 1 call (cached forever!)
- Get bookmarks: 1 call (15 min)
- For each thread:
  - Search conversation: 1 call (15 min)
    (Skip individual tweet fetch!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 1 + 1 + (10 × 1) = 12 calls
Time: 12 × 15 minutes = 180 minutes = 3 hours
```

**Saved: 2.5 hours!** 🎉

---

## 💡 Optimizations Applied

### 1. **Cache User ID**
```python
self.cached_user_id = None  # Cached after first fetch
```
- Fetched once per session
- Saves 1 API call = 15 minutes

### 2. **Single Search Query**
```python
# OLD: 2 calls per thread
GET /tweets/{id}              # 15 min
GET /search?conversation_id   # 15 min

# NEW: 1 call per thread
GET /search?conversation_id AND from:author_id  # 15 min
```
- Combined query using `from:author_id` filter
- Saves 1 API call per thread = 15 min × N threads

### 3. **Batch Processing Architecture**
```
Phase 1: Fetch ALL threads from Twitter (15 min per thread)
Phase 2: Process with LLM (no API calls, instant!)
```
- All Twitter calls upfront
- LLM processing happens locally (no waiting)

---

## 📊 Real Example: 5 Threads

### Before Optimization
```
1. Get user_id     →  0:00 - 0:15  ✓
2. Get bookmarks   →  0:15 - 0:30  ✓
3. Thread 1 tweet  →  0:30 - 0:45  ✓
4. Thread 1 search →  0:45 - 1:00  ✓
5. Thread 2 tweet  →  1:00 - 1:15  ✓
6. Thread 2 search →  1:15 - 1:30  ✓
...
12. Thread 5 search → 2:45 - 3:00  ✓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 3 hours
```

### After Optimization
```
1. Get user_id (cached)  →  instant!
2. Get bookmarks         →  0:00 - 0:15  ✓
3. Thread 1 search       →  0:15 - 0:30  ✓
4. Thread 2 search       →  0:30 - 0:45  ✓
5. Thread 3 search       →  0:45 - 1:00  ✓
6. Thread 4 search       →  1:00 - 1:15  ✓
7. Thread 5 search       →  1:15 - 1:30  ✓
8. LLM processing        →  1:30 - 1:40  (all threads, instant!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 1.5 hours (50% faster!)
```

---

## 🎯 Best Practices

### 1. **Process in Batches**
```bash
# Don't do this:
threadsmith add url1  # 30 min
threadsmith add url2  # 30 min
threadsmith add url3  # 30 min
# = 90 minutes

# Do this instead:
# Bookmark all threads in browser
threadsmith sync      # 45 min for all 3
# = 45 minutes
```

### 2. **Bookmark First, Sync Later**
- Browse Twitter normally
- Bookmark interesting threads
- Run `threadsmith sync` once at end of day
- Process all at once

### 3. **Use Saved Sessions**
- User ID cached per session
- Don't restart unnecessarily
- Reuse same terminal session

### 4. **Plan Ahead**
- Free tier = ~4 threads per hour max
- Plan your syncs accordingly
- Best: End of day batch

---

## ⚠️ What to Expect

When you run `threadsmith sync`:

```
🔍 Select model for processing...
💬 Select a model:
  gemma3n-E2B-it-Q4_0 (2.8 GB)
✓ qwen3-14B-Q4_K_M (8.4 GB)
  gemma3-27B-it-qat-Q4_0 (14.5 GB)

✓ Using: qwen3-14B-Q4_K_M.gguf (8.4 GB)

🔄 Starting bookmark sync...
✓ Found 10 bookmarks
📚 Found 3 new bookmarks to process

🔄 Phase 1: Fetching all threads from Twitter...
   Fetching thread 1/3... ⏳ Rate limit: waiting 0.0 minutes (0s)...
✓ (5 tweets)
   Fetching thread 2/3... ⏳ Rate limit: waiting 15.0 minutes (900s)...
✓ (8 tweets)
   Fetching thread 3/3... ⏳ Rate limit: waiting 15.0 minutes (900s)...
✓ (3 tweets)

🧠 Phase 2: Processing 3 threads with LLM...
   Loading model into memory (one time)...
✓ Model loaded and ready

Generating .mdc 1/3
   Generating with pre-loaded model...
✓ Saved: rules/seo-growth-tactics.mdc

Generating .mdc 2/3
   Generating with pre-loaded model...
✓ Saved: rules/product-feedback-loop.mdc

Generating .mdc 3/3
   Generating with pre-loaded model...
✓ Saved: rules/startup-hiring-guide.mdc

✓ Sync complete! Processed 3 new threads
```

**Total time: ~30 minutes** (2 × 15 min for API + 5 min for LLM)

---

## 🤔 Why So Slow?

Twitter's free tier is designed for testing, not production use.

**Options:**
1. **Use free tier wisely** - Batch daily, be patient
2. **Upgrade to Basic** - $100/month, 10K tweets/month
3. **Upgrade to Pro** - $5K/month, unlimited

For personal use, free tier is fine if you:
- Process 5-10 threads per day max
- Run once daily (end of day)
- Be patient during sync

---

## 📈 Future Improvements

Possible optimizations (not implemented yet):
1. **Save threads to queue** - Fetch later in background
2. **Parallel user sessions** - Multiple Twitter accounts (🤔)
3. **Smart scheduling** - Auto-sync during night
4. **Cached conversations** - Save thread data locally

For now: **Be patient, let it run, go grab coffee!** ☕

---

Built with patience and optimization! 🧵⏱️

