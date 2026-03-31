---
name: ytmp4-ai-digest
description: Browse subscribed YouTube channels, fetch transcripts, and generate summary digests in Markdown. Also supports multi-video comparison — cross-video analysis with interactive dashboard, frame screenshots, and agentic chat. Use this skill whenever the user mentions "YouTube videos", "video digest", "summarize YouTube", "video summary", "youtube digest", "latest videos", "compare these videos", "compare video X and Y", "what's the difference between these videos", "cross-video analysis", "recap videos", "catch up on videos", or wants to browse, summarize, or compare YouTube content on any topic (AI, 3D modeling, coding, etc.).
---

# YouTube Video Digest

Browse subscribed YouTube channels, fetch transcripts, and generate Markdown summary digests. Works with any topic.

**Plugin root:** `${CLAUDE_PLUGIN_ROOT}` | **Data:** `${CLAUDE_PLUGIN_DATA}`

## Agent Routing

Route tasks to the right agent for optimal speed and cost:

| Task | Agent | Why |
|------|-------|-----|
| Fetch videos, list channels, simple queries | `video-fetcher` (haiku) | Fast, cheap — no reasoning needed |
| Summarize transcripts, write digests | `digest-writer` (sonnet) | Good balance of quality and speed |
| Cross-video comparison, deep analysis | `video-comparator` (opus) | Needs deep reasoning across sources |

## Workflow

```bash
cd ${CLAUDE_PLUGIN_ROOT}

# Fetch recent videos (last N days)
python scripts/fetch_videos.py --days 3             # Default: AI keyword filter
python scripts/fetch_videos.py --days 3 --all       # All topics, no filter
python scripts/fetch_videos.py --keyword "blender"   # Custom topic

# Single video transcript + summary
python scripts/get_transcript.py --video-id VIDEO_ID

# Batch digest (fetches transcripts, Claude fills summaries)
python scripts/digest_all.py --days 3 --limit 10

# Single video report with thumbnail
python scripts/generate_report.py --video-id VIDEO_ID --output ~/reports/

# Compare multiple videos
python scripts/compare_videos.py --urls URL1 URL2 URL3
# Then launch interactive viewer:
python scripts/compare_server.py --port 5123 --session SESSION_ID
```

**Output locations:**
- Videos list: `${CLAUDE_PLUGIN_DATA}/videos.json`
- Transcripts: `${CLAUDE_PLUGIN_DATA}/transcript_VIDEO_ID.txt` (.json also)
- Digest: `${CLAUDE_PLUGIN_DATA}/output/ai_digest_YYYYMMDD.md`
- Comparison: `${CLAUDE_PLUGIN_DATA}/comparison_data.json`

## Summarization Rules

After fetching transcript content, Claude proactively completes (no further prompting needed):

1. Read the full transcript or digest file
2. For each video output: **Core Takeaway** (2-3 sentences, state conclusions directly), **Key Points** (3-5 bullets with specifics), **Why It Matters** (why worth watching)
3. If transcript quality is poor, say so honestly

Style: concise, information-dense. No filler openings like "This video discusses..." — lead with actual content.

## Comparison Analysis

After `compare_videos.py` outputs comparison_data.json, Claude reads transcripts and fills:
- **Unified Summary** — cross-video synthesis
- **Topics** — shared themes with per-video timestamps, quotes, consensus status
- **Disagreements** — where creators differ, both sides stated
- **Key Moments** — notable timestamps for frame capture

Frame screenshots: Claude auto-identifies key moments; users can also click timeline in the viewer.

## Channels Config

Edit `${CLAUDE_PLUGIN_ROOT}/data/channels.json` — array of `{"name": "...", "id": "CHANNEL_ID"}` objects.

## Intent Routing

| User Says | Action |
|-----------|--------|
| "Find recent AI videos" | `fetch_videos.py --days 3`, display results |
| "What's new in Blender?" | `fetch_videos.py --keyword "blender"` |
| "Create a digest" | `digest_all.py`, read output, generate summaries |
| "Summarize video #3" | `get_transcript.py`, then summarize |
| "Show all videos, no filter" | `fetch_videos.py --days 3 --all` |
| "Compare these videos: URL1, URL2" | `compare_videos.py`, analyze, launch viewer |
| "What do they disagree on?" | Reference disagreements in comparison data |
| "Capture the chart at 4:21" | `capture_frames.py` for that timestamp |
| "Show me all sessions" | Launch viewer showing session history |
