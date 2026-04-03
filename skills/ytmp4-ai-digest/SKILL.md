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
| Single video URL analysis, batch digests | `digest-writer` (sonnet) | Summarizes + launches viewer for single URLs; handles batch digests |
| Multi-video comparison (2+ URLs) | `video-comparator` (opus) | Cross-video reasoning, disagreements, deep analysis |

**IMPORTANT:** When the user provides a **single** video URL, route to `digest-writer` — it creates a session, fills analysis, and launches the viewer at Sonnet cost. Only use `video-comparator` for **2+ URLs** where cross-video analysis is needed. The viewer must always launch regardless of which agent handles the request.

## Workflow

```bash
cd ${CLAUDE_PLUGIN_ROOT}

# Fetch recent videos (last N days)
python scripts/fetch_videos.py --days 3             # Default: AI keyword filter
python scripts/fetch_videos.py --days 3 --all       # All topics, no filter
python scripts/fetch_videos.py --keyword "blender"   # Custom topic

# Analyze video(s) — works with 1 or more URLs
python scripts/compare_videos.py --urls URL1 [URL2 URL3 ...]
# Always launch the interactive viewer after analysis:
python scripts/compare_server.py --port 5123 --session SESSION_ID

# Batch digest from subscribed channels (fetches transcripts, Claude fills summaries)
python scripts/digest_all.py --days 3 --limit 10

# Standalone transcript fetch (for digest workflow, not direct user requests)
python scripts/get_transcript.py --video-id VIDEO_ID
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

## Video Analysis

### Single Video (digest-writer)
The digest-writer agent handles single video URL analysis end-to-end:
1. Runs `compare_videos.py --urls URL` to create a session and fetch transcript
2. Fills comparison_data.json with summary, topics, key moments
3. **Launches the viewer automatically and provides the link**
4. Also outputs the summary directly in chat

### Multiple Videos (video-comparator)
The video-comparator agent handles multi-video comparison end-to-end:
1. Runs `compare_videos.py --urls URL1 URL2 ...` to fetch all video data and transcripts
2. Reads ALL transcripts and fills comparison_data.json with complete cross-video analysis
3. **Launches the viewer automatically and provides the link** — no second prompt needed

The agent fills these required fields (viewer tabs are empty without them):
- **Per-video `summary`** — added to each video object for the By Video tab
- **Unified Summary** — cross-video synthesis paragraph
- **Topics** — with `name`, `entries` (video_id, timestamp, quote), `video_coverage`, `consensus`
- **Disagreements** — where creators differ, both sides stated
- **Key Moments** — with `video_id`, `timestamp`, `label`, `description`
- **Stats** — counts for topics, disagreements, key moments

**IMPORTANT:** The video-comparator agent must complete ALL of these in a single pass and launch the viewer at the end. Do not return to the user between steps.

Frame screenshots: Claude auto-identifies key moments; users can also click timeline in the viewer.

## Channels Config

Edit `${CLAUDE_PLUGIN_ROOT}/data/channels.json` — array of `{"name": "...", "id": "CHANNEL_ID"}` objects.

## Intent Routing

| User Says | Action |
|-----------|--------|
| "Find recent AI videos" | `fetch_videos.py --days 3`, display results |
| "What's new in Blender?" | `fetch_videos.py --keyword "blender"` |
| "Create a digest" | `digest_all.py`, read output, generate summaries |
| "Summarize this video: URL" | `digest-writer`: `compare_videos.py --urls URL`, summarize, launch viewer |
| "Summarize video #3" (from fetched list) | `digest-writer`: `compare_videos.py --urls URL`, summarize, launch viewer |
| "Show all videos, no filter" | `fetch_videos.py --days 3 --all` |
| "Compare these videos: URL1, URL2" | `video-comparator`: `compare_videos.py --urls URL1 URL2`, analyze, launch viewer |
| "What do they disagree on?" | Reference disagreements in comparison data |
| "Capture the chart at 4:21" | `capture_frames.py` for that timestamp |
| "Show me all sessions" | Launch viewer showing session history |
