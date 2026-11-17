# System Requirements Specification: GTA 6 AI Clip Factory

---

## 1. Functional Requirements

### 1.1 Permission & Legal Safety (PERM)
* **PERM-01 [Streamer Registration]**: The system shall register content creators with unique IDs, channel identifiers, display names, and profile metadata.
* **PERM-02 [Permission Record Tracking]**: Every creator must have an associated explicit permission record containing status (`ACTIVE`, `PENDING`, `REVOKED`), grant date, expiration date, authorized media channels, and terms documentation.
* **PERM-03 [Ingestion Permission Gate]**: The ingestion pipeline shall strictly abort and refuse to process any media source or recording whose associated streamer lacks an `ACTIVE` permission status.
* **PERM-04 [Revocation Cascade]**: If a streamer's permission is revoked, all pending jobs for that streamer must be canceled immediately, and exported clips must be flagged with a revocation banner.
* **PERM-05 [Zero Unauthorized Scraping]**: The system shall contain zero DRM-bypassing, hidden URL extracting, or unauthorized YouTube video downloading code. Live status checking and media ingestion must remain architecturally separated.
* **PERM-06 [Zero Auto-Publishing]**: Under no circumstances shall the application automatically push, upload, or publish clips to any external social media platform (TikTok, YouTube Shorts, Instagram Reels). Human download and approval are mandatory.

### 1.2 YouTube Live Monitoring (YT)
* **YT-01 [Channel Status Check]**: The system shall poll the official YouTube Data API v3 (`videos.list` / `search.list`) at configurable intervals to detect when registered creators go live.
* **YT-02 [Live Stream Metadata]**: Upon detecting an active broadcast, capture stream metadata: YouTube Video ID, title, start timestamp, thumbnail URL, and active viewer count.
* **YT-03 [Category Verification]**: Verify if the active broadcast category matches Grand Theft Auto VI (or GTA series tags).
* **YT-04 [Graceful Quota Handling]**: Implement token-bucket rate limiting and exponential backoff to ensure API calls remain strictly within the daily 10,000 unit YouTube API quota.

### 1.3 Media Ingestion & Spooling (INGEST)
* **INGEST-01 [Local Video Ingestion]**: Provide a file dropzone and API endpoint to ingest authorized pre-recorded MP4/MKV/MOV gameplay recordings.
* **INGEST-02 [Media Feed Ingestion]**: Support ingesting authorized local capture cards or RTMP/SRT stream recordings.
* **INGEST-03 [Integrity & Hash Validation]**: Verify video file readability via `ffprobe`, compute a SHA-256 integrity hash, and record duration, frame rate, resolution, and audio channels.
* **INGEST-04 [Chunked Storage & Retention]**: Spool incoming raw video in configured storage paths (`./data/recordings/`) and enforce automated disk cleanup based on retention policy.

### 1.4 Audio Analysis Engine (AUD)
* **AUD-01 [Loudness & Energy Curve]**: Compute Root-Mean-Square (RMS) audio energy and spectral flux in 500ms time windows across the entire recording.
* **AUD-02 [Vocal Reaction Classifier]**: Detect streamer vocal reactions (shouting, sudden laughter, gasp, pitch jumps) by identifying volume spikes $\ge 2.5\sigma$ above baseline.
* **AUD-03 [Word-Level Transcription]**: Run `faster-whisper` locally on GPU/CPU to transcribe streamer speech and generate exact word-level start/end timestamps.
* **AUD-04 [Silence & Dead-Air Filtering]**: Identify extended periods of silence or low-energy monologue to exclude from highlight candidates.

### 1.5 Visual Analysis Engine (VIS)
* **VIS-01 [Scene Cut Detection]**: Run PySceneDetect content-aware thresholding to extract major cut boundaries and prevent clipping across unrelated scenes.
* **VIS-02 [Gameplay Motion Energy]**: Compute optical flow or frame differencing across downsampled keyframes to locate action-heavy gameplay (car chases, explosions, crashes, combat).
* **VIS-03 [Streamer Facecam Detection]**: Inspect video frame corners using MediaPipe FaceLandmarker to detect streamer facecam presence and calculate its bounding box.
* **VIS-04 [Facecam Stability Lock]**: Apply temporal smoothing to facecam bounding coordinates across clips to prevent jitter during vertical reframing.

### 1.6 Highlight Scoring & Deduplication (SCORE)
* **SCORE-01 [Candidate Windowing]**: Synthesize audio spikes and visual action events into candidate clip windows between 15 and 60 seconds duration.
* **SCORE-02 [Boundary Snapping]**: Automatically snap clip start and end boundaries to natural speech pauses or visual scene cuts.
* **SCORE-03 [Multi-Modal Scoring Metric]**: Calculate a composite score $S \in [0, 100]$:
  $$S = 0.35 \cdot S_{\text{audio}} + 0.35 \cdot S_{\text{visual}} + 0.30 \cdot S_{\text{context}}$$
* **SCORE-04 [VLM Context Reasoning]**: When cloud keys (Gemini / OpenAI) are present, evaluate keyframe sequences with a VLM prompt to score viral potential, humor, and action coherence. When offline, use local heuristic scoring.
* **SCORE-05 [Non-Maximum Suppression]**: Apply temporal NMS with an IoU threshold of 0.30 to eliminate redundant overlapping candidate clips.
* **SCORE-06 [Candidate Ranking]**: Rank all candidate clips by composite score and present top candidates in the Processing Queue.

### 1.7 FFmpeg Vertical Editing & Rendering (EDIT)
* **EDIT-01 [Vertical 9:16 Format]**: Render final clips strictly in vertical 1080x1920 MP4 (H.264 video, AAC audio, 30 fps).
* **EDIT-02 [Preset 1: Viral Gaming]**: Smart center-crop with dynamic motion-tracking pans, zoomed in on core action with prominent burned-in subtitles.
* **EDIT-03 [Preset 2: Clean Gameplay]**: Vertical layout with 16:9 gameplay placed in the center, blurred background reflection top and bottom, and clean subtitles.
* **EDIT-04 [Preset 3: Reaction Focus]**: Split-screen stack: cropped streamer facecam placed on top (1:1 or 4:5 ratio), cropped gameplay placed on bottom.
* **EDIT-05 [Dynamic Animated Subtitles]**: Generate styled ASS/SSA subtitle scripts with word-by-word active highlighting (karaoke style) rendered crisply over video.
* **EDIT-06 [Audio Normalization]**: Apply two-pass EBU R128 (`loudnorm`) filtering to achieve consistent broadcast audio loudness (-16 LUFS, -1 dB true peak).
* **EDIT-07 [Thumbnail & Catchy Title]**: Automatically capture the peak keyframe as a JPEG thumbnail and generate 3 catchy title suggestions.

### 1.8 Production Dashboard (DASH)
The frontend application shall provide 10 functional, high-density pages:
* **DASH-01 [Overview]**: Production KPIs, active streams, recent clips, GPU/CPU utilization, and queue status.
* **DASH-02 [Stream Monitor]**: Real-time monitoring cards for registered streamers, live status badges, viewer counters, and manual capture triggers.
* **DASH-03 [Streamers]**: Streamer roster with channel IDs, avatars, platform links, and permission states.
* **DASH-04 [Clip Library]**: Filterable media grid of rendered clips with video preview, title, score badge, duration, and download action.
* **DASH-05 [Clip Editor]**: Interactive waveform trimmer, preset switcher, subtitle editor, and manual re-render button.
* **DASH-06 [Processing Queue]**: Real-time job table displaying progress bars, active stages, latency, and cancel/retry controls.
* **DASH-07 [Analytics]**: Performance charts (clip generation yield over time, score distribution, average processing speed).
* **DASH-08 [Permissions]**: Comprehensive legal consent management with audit logs and revocation controls.
* **DASH-09 [Storage]**: Disk usage breakdown (recordings vs clips vs thumbnails) with retention rules and 1-click purge.
* **DASH-10 [Settings & Integrations]**: API key configuration, hardware selector, render presets, and secret masking.

### 1.9 Database & Storage (DATA)
* **DATA-01 [PostgreSQL Schema]**: Implement relational models for: `Streamer`, `Permission`, `Stream`, `MediaSource`, `Recording`, `DetectedEvent`, `ClipCandidate`, `Clip`, `Thumbnail`, `ProcessingJob`, `UserSettings`, and `AuditLog`.
* **DATA-02 [Alembic Migrations]**: Maintain version-controlled Alembic migration scripts ensuring seamless database upgrades.
* **DATA-03 [Local Filesystem Storage]**: All binary video files, audio tracks, thumbnails, and subtitle files must reside on disk, referenced only by relative paths in the database.
* **DATA-04 [Storage Quotas & Cleanup]**: Configurable retention limits to automatically purge raw recordings older than $N$ days while preserving finalized clips.

### 1.10 External APIs & Integrations (API)
* **API-01 [Centralized Environment Config]**: All credentials managed via `.env` with strict type validation at boot.
* **API-02 [Zero Secret Leakage]**: Frontend and API status endpoints must mask keys (e.g. `sk-...4a1b`).
* **API-03 [Graceful Degradation]**: If external APIs are absent or exceed quota, smoothly fall back to local offline modules without failing the pipeline.
* **API-04 [Credential Pre-Flight Verification]**: Interactive or programmatic test endpoint validating keys before initiating external workloads.

---

## 2. Non-Functional Requirements

* **HW-01 [VRAM Budget Guard]**: Total GPU memory consumption must not exceed 4.5 GB on the RTX 3050. Pipeline stages must execute sequentially and trigger garbage collection between passes.
* **HW-02 [Windows 11 Compatibility]**: File paths must handle Windows backslashes properly, subprocess commands must avoid Unix-only signals, and PyAV audio bindings must apply the `_safe_av_open` patch.
* **PERF-01 [Processing Latency]**: A 10-minute gameplay recording must be fully analyzed, scored, and clipped into top candidates within $< 5$ minutes on the RTX 3050.
* **RELIABILITY-01 [Job Recovery]**: Any processing job interrupted by an unexpected crash or server reboot must restart or transition to `FAILED` with actionable error logs upon restart.
* **ACCURACY-01 [Zero Hallucination]**: Every stream status, clip candidate, and performance metric displayed on the dashboard must correspond to real database records and physical disk files.

