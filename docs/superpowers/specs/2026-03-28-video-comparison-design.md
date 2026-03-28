# Video Comparison Feature — Design Spec

## Overview

Add a multi-video comparison feature to the ytmp4-ai-digest plugin that lets users supply multiple YouTube video URLs on the same topic and receive a unified cross-video analysis with interactive browsing, timestamps, frame screenshots, and an agentic chat interface.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trigger model | Hybrid: Claude-driven + interactive viewer | Claude orchestrates via conversation, results open in a rich HTML viewer |
| Video count | Flexible 2-10+ | Dashboard scales from quick 2-video comparisons to comprehensive surveys |
| Screenshot capture | Auto + on-demand | Claude auto-captures key moments; user can click any timestamp for more |
| Results layout | Dashboard with topic/video toggle | Overview dashboard, then switch between By Topic and By Video views |
| Collapsed history panel | Tooltip on hover | Clean icon-only strip with badge counts, tooltip shows session title |
| Chat widget | Expanding bottom-right bubble | Agentic chat for follow-up questions about the current session |
| Tech stack | Python core + self-contained HTML viewer | Two-layer: works in Claude Code (Flask server) and Claude Desktop (static artifact) |

## Architecture

### Two-Layer Design

**Core Layer (Python scripts)** — handles all data fetching, processing, and frame capture:

- `compare_videos.py` — orchestrator: accepts multiple URLs/IDs, calls transcript + frame scripts, outputs `comparison_data.json`
- `capture_frames.py` — ffmpeg wrapper for extracting video frames at specific timestamps
- `compare_server.py` — Flask server for Claude Code mode (serves viewer + on-demand screenshot API)

**Viewer Layer (HTML + JS)** — self-contained single-file interactive dashboard:

- `viewer.html` — reads `comparison_data.json`, renders the full UI
- No build step, no external dependencies, all CSS/JS inline

### Environment Adaptation

| Environment | Behavior |
|-------------|----------|
| **Claude Code** | `compare_server.py` (Flask) serves viewer at localhost + provides `/api/screenshot` endpoint for on-demand frame capture via ffmpeg |
| **Claude Desktop** | Pre-captures all key moment screenshots, embeds as base64 in JSON, outputs viewer as HTML artifact |

### Data Flow

```
User: "Compare these 4 videos about GPT-5: URL1, URL2, URL3, URL4"
  │
  ▼
Claude runs: compare_videos.py --urls URL1 URL2 URL3 URL4
  │
  ├─► get_transcript.py (for each video) → transcripts
  ├─► capture_frames.py (key moments from transcripts) → screenshots
  │
  ▼
Claude reads transcripts, generates cross-video analysis
  │
  ▼
Output: comparison_data.json
  │
  ▼
Claude Code: compare_server.py serves viewer.html at localhost:PORT
Claude Desktop: viewer.html output as artifact with embedded data
```

### comparison_data.json Schema

```json
{
  "session": {
    "id": "uuid",
    "title": "GPT-5 Announcements",
    "created_at": "2026-03-28T14:30:00Z",
    "video_count": 4
  },
  "videos": [
    {
      "id": "video_id",
      "title": "Video Title",
      "channel": "Channel Name",
      "url": "https://youtube.com/watch?v=...",
      "duration": "18:42",
      "upload_date": "2026-03-25",
      "view_count": 342000,
      "thumbnail_base64": "...",
      "transcript": [
        {"start": 0, "text": "..."},
        {"start": 15, "text": "..."}
      ]
    }
  ],
  "analysis": {
    "unified_summary": "All four creators agree that...",
    "topics": [
      {
        "name": "Reasoning Capability",
        "video_coverage": ["video_id_1", "video_id_2", "video_id_3", "video_id_4"],
        "consensus": "agreement",
        "entries": [
          {
            "video_id": "video_id_1",
            "timestamp": 261,
            "quote": "GPT-5 scores 92% on ARC-AGI...",
            "screenshot_base64": "..."
          }
        ]
      }
    ],
    "disagreements": [
      {
        "topic": "Safety & Alignment",
        "sides": [
          {"video_ids": ["v1", "v2"], "position": "Praised new alignment approach"},
          {"video_ids": ["v3", "v4"], "position": "Skeptical of evaluation methodology"}
        ]
      }
    ],
    "key_moments": [
      {
        "video_id": "video_id_1",
        "timestamp": 261,
        "label": "Benchmark Comparison Chart",
        "description": "Shows ARC-AGI scores comparison",
        "screenshot_base64": "..."
      }
    ]
  },
  "stats": {
    "total_videos": 4,
    "common_topics": 6,
    "disagreements": 3,
    "key_moments": 12
  }
}
```

## UI Design

### Overall Layout

```
┌──────────────────────────────────────────────────────┐
│ [History Panel]  │  [Nav: ytmp4 | Session Title]     │
│                  │  [Dashboard] [By Topic] [By Video]│
│  Session list    │                                   │
│  (collapsible)   │  ┌─ Main Content Area ──────────┐ │
│                  │  │                               │ │
│  Expanded:       │  │  (varies by active tab)       │ │
│  - grouped by    │  │                               │ │
│    date          │  │                               │ │
│  - search bar    │  │                               │ │
│  - video count   │  │                               │ │
│    badges        │  │                               │ │
│                  │  └───────────────────────────────┘ │
│  Collapsed:      │                            [Chat] │
│  - icon strip    │                            bubble │
│  - tooltip on    │                                   │
│    hover         │                                   │
└──────────────────────────────────────────────────────┘
```

### Dashboard Tab

- **Stats row** — 4 cards: Videos, Common Topics, Disagreements, Key Moments
- **Unified Summary** — Claude's cross-video synthesis paragraph
- **Topic Map** — horizontal bar chart showing topic coverage across videos (e.g., "Reasoning Capability 4/4")
- **Videos Compared** — card list with thumbnails, titles, channels, durations
- **Key Moments** — screenshot grid with timestamps, labels, color-coded by source video

### By Topic Tab

- **Accordion layout** — each topic is an expandable section
- **Topic header** — colored indicator bar, topic name, video coverage count, consensus status (agreement/divided/skeptical)
- **Expanded content** — per-video entries showing: screenshot thumbnail, timestamp, creator name, key quote from transcript
- **Topics sorted** by coverage count (most videos first)

### By Video Tab

- **Split layout** — video selector sidebar (left) + detail panel (right)
- **Sidebar** — thumbnail cards for each video, active video highlighted with blue border
- **Detail panel**:
  - Video header: thumbnail, title, channel, date, views, per-video summary
  - Topic tags: colored pills showing which topics this video covers
  - Interactive timeline bar: colored dots at key moments, clickable anywhere for on-demand frame capture
  - Moment entries: frame screenshot, timestamp, label, description

### Session History Panel

- **Expanded state** (~260px): grouped by Today/Yesterday/This Week, search bar, session cards with title + video count badge (purple for multi-video, blue for single) + channel names
- **Collapsed state** (~48px): icon-only strip with video count badges, tooltip on hover shows full session title
- **Active session** highlighted with purple left border
- **Toggle** via chevron button in panel header

### Chat Widget

- **Collapsed** — purple gradient circle in bottom-right corner with green "AI" indicator dot
- **Expanded** — 380px wide chat panel overlaying bottom-right:
  - Header: Claude avatar, status ("Analyzing 4 videos"), expand-to-full + close buttons
  - Message thread: Claude messages (left-aligned, dark bg) and user messages (right-aligned, purple bg)
  - Claude can reference clickable timestamps that navigate to moments in the viewer
  - Input bar: "Ask about these videos..." placeholder + send button
- **Backend**: chat messages route through the Flask API which has access to all transcripts and can trigger additional screenshot captures

## New Files

### Scripts

| File | Purpose |
|------|---------|
| `scripts/compare_videos.py` | Orchestrator: accepts multiple URLs, fetches transcripts + metadata, triggers frame capture, outputs `comparison_data.json` |
| `scripts/capture_frames.py` | ffmpeg wrapper: downloads a short video segment and extracts a frame at a specific timestamp, returns base64 PNG |
| `scripts/compare_server.py` | Flask server: serves `viewer.html`, provides REST API for on-demand screenshots and chat |

### Viewer

| File | Purpose |
|------|---------|
| `viewer/viewer.html` | Self-contained single-file HTML/CSS/JS dashboard that reads `comparison_data.json` |

### Data

| File | Purpose |
|------|---------|
| `${CLAUDE_PLUGIN_DATA}/sessions/` | Persistent directory storing `comparison_data.json` per session for history |
| `${CLAUDE_PLUGIN_DATA}/sessions/index.json` | Session index for the history panel (id, title, date, video count) |

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `ffmpeg` | System binary | Frame extraction from video streams |
| `flask` | pip package | Local server for Claude Code mode |
| `yt-dlp` | pip package | Already installed — video/transcript fetching |

## SKILL.md Updates

Add new trigger phrases and workflow documentation for the comparison feature:
- "compare these videos"
- "compare video X and Y"
- "what's the difference between these videos"
- "cross-video analysis"

Add a new section documenting the `compare_videos.py` workflow and the viewer.

## Session Persistence

Sessions are stored in `${CLAUDE_PLUGIN_DATA}/sessions/`:

```
sessions/
├── index.json                          # [{id, title, created_at, video_count}, ...]
├── 2026-03-28_gpt5-announcements/
│   └── comparison_data.json
├── 2026-03-28_claude4-opus/
│   └── comparison_data.json
└── 2026-03-27_sora-vs-veo/
    └── comparison_data.json
```

The history panel reads `index.json` to populate the sidebar. Clicking a past session loads its `comparison_data.json` into the viewer.

## Flask API Endpoints (Claude Code mode)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /` | GET | Serve `viewer.html` |
| `GET /api/sessions` | GET | List all sessions for history panel |
| `GET /api/session/:id` | GET | Load a specific session's data |
| `POST /api/screenshot` | POST | Capture frame at timestamp: `{video_id, timestamp}` → returns base64 PNG |
| `POST /api/chat` | POST | Send chat message with session context, returns Claude's response |

## Out of Scope (Future)

- Real-time video playback in the viewer (would require embedding YouTube player)
- Export comparison as PDF or shareable link
- Collaborative sessions (multiple users viewing same comparison)
- Auto-triggering comparisons from the daily digest (e.g., "3 videos about the same topic detected")
