# GTA 6 AI Clip Factory - Project Specification

---

## 1. Vision & Executive Summary
Grand Theft Auto VI is anticipated to be the most massive cultural entertainment launch of the decade, generating petabytes of live broadcast content daily. However, human video editors cannot manually watch four-hour livestreams, locate peak moments, crop 16:9 gameplay to 9:16 vertical short-form video, detect streamer facecams, transcribe dialogue with word-level animated subtitles, and package viral clips at scale.

**GTA 6 AI Clip Factory** is a local-first, autonomous production system that transforms long-form, authorized GTA 6 streamer broadcasts into 30–50 high-retention vertical MP4 clips (1080x1920) per 4-hour stream.

### Core Architectural Pillars
1. **Local-First Processing:** Runs entirely on local consumer hardware (optimized for Windows 11 and NVIDIA RTX 3050 6GB GPU) using FFmpeg, OpenCV, faster-whisper, and PyTorch, with graceful CPU fallback.
2. **Permission-Gated Ingestion:** Enforces explicit creator permission records and verified intake channels. Separates YouTube live monitoring from authorized media feeds. Zero DRM bypass or unauthorized scraping.
3. **Multi-Stage AI Highlight Engine:** Rejects brute-force LLM processing of entire videos. Utilizes lightweight audio energy and visual scene-change detection to isolate candidate segments, followed by targeted VLM context scoring and facecam tracking.
4. **Professional Production Dashboard:** A dark gaming-production interface (Next.js 15, Tailwind CSS, Lucide React, Recharts) featuring 10 functional modules for monitoring streams, reviewing candidates, fine-tuning cuts, and exporting finished clips.
5. **Zero Automatic Social Publishing:** All clip publishing requires human review, manual download, or explicit export.

---

## 2. Core Architecture & Component Diagram

```
[ Authorized GTA 6 Stream / Local Recording ]
                       │
                       ▼
         [ Stream & Media Ingestion Manager ]
   (Permission Verification ➔ SHA-256 Hash ➔ Disk Spooling)
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
 [ Audio Feature Pipeline ]     [ Visual Feature Pipeline ]
  - RMS Loudness & Spectral Flux  - PySceneDetect / OpenCV Differencing
  - Laughter / Screaming Classifier - Action & Chaos Spike Detection
  - faster-whisper Word Timestamps - MediaPipe Streamer Facecam Tracker
        │                             │
        └──────────────┬──────────────┘
                       ▼
        [ Candidate Generation & Temporal Clustering ]
         - Window Merging (15s – 60s target duration)
         - Boundary Snapping to natural pauses
                       │
                       ▼
         [ Multi-Modal Highlight Scoring Engine ]
          - Audio Excitement Weight (35%)
          - Visual Action & Motion Weight (35%)
          - VLM Context & Hook Weight (30%) (Gemini / OpenAI / Heuristic)
          - Non-Maximum Suppression (Deduplication)
                       │
                       ▼
         [ FFmpeg Vertical Clipping & Rendering Core ]
          - Smart 9:16 Pan-and-Scan / Dynamic Reframe
          - Multi-Layer Reaction Focus (Facecam top + Game bottom)
          - Burned-in ASS Subtitles (Karaoke-style word highlight)
          - EBU R128 Audio Loudness Normalization
          - Thumbnail Capture & Title Generation
                       │
                       ▼
     [ Local Filesystem Storage (`./data/clips/`) ]
                       │
                       ▼
   [ Next.js 15 Dark Gaming Production Dashboard ]
 (10 Functional Pages: Monitor, Library, Editor, Queue, Analytics)
```

---

## 3. Technology Stack & Implementation Choices

### Backend & API
* **Language & Runtime:** Python 3.13 (64-bit Windows)
* **Framework:** FastAPI with asynchronous ASGI architecture
* **Data Validation:** Pydantic v2 with strict type annotations
* **Database & ORM:** PostgreSQL + SQLAlchemy 2.0 with modern `psycopg` (v3) driver
* **Database Migrations:** Alembic with autogenerate support
* **Task Dispatcher:** Async background worker queue (FastAPI BackgroundTasks + Celery/Redis ready)

### Video & AI Processing Core
* **Video Transformation:** FFmpeg 6/7 static Windows 64-bit binary with NVENC hardware acceleration (fallback to libx264)
* **Computer Vision:** OpenCV 5.0.0 for frame differencing and motion analysis
* **Scene Boundary Detection:** PySceneDetect (content-aware HSV thresholding)
* **Facecam Tracking:** MediaPipe `FaceLandmarker` adapted for offline video frame crops
* **Speech-to-Text & Subtitles:** `faster-whisper` (CTranslate2 float16 on CUDA, int8 on CPU) with word-level timestamps and PyAV >= 14 patch
* **Audio Engineering:** SciPy signal processing + Librosa algorithms for RMS energy, spectral centroid, and zero-crossing rates
* **Vision-Language Intelligence:** Hybrid engine — Google Gemini 1.5 Flash / OpenAI GPT-4o-mini with local deterministic heuristic fallback

### Frontend Production Dashboard
* **Framework:** Next.js 15 (React 19, App Router)
* **Styling & Theme:** Tailwind CSS with custom Dark Gaming Navy/Cyan production palette
* **Icons:** Lucide React
* **Data Visualization:** Recharts for stream metrics, audio energy graphs, and score distributions
* **Video Preview:** HTML5 custom-skinned video player with frame-stepping and audio waveform display

---

## 4. Hardware Profile & Resource Budget

The application is explicitly engineered for the host workstation:
* **Operating System:** Windows 11 64-bit
* **GPU:** NVIDIA GeForce RTX 3050 6GB Laptop GPU (6,144 MB VRAM, CUDA 13.2)
* **CPU:** Multi-core modern x86_64 host processor
* **VRAM Allocation Budget (Maximum 4,500 MB concurrent):**
  * `faster-whisper` (base model, float16): ~350 MB VRAM
  * MediaPipe Face Detection: ~250 MB VRAM / CPU offload
  * FFmpeg NVENC Encoder: ~400 MB VRAM
  * PyTorch Frame Feature Extraction: ~1,500 MB VRAM
  * Safety Headroom: >3,500 MB free for OS and display buffers
* **Sequential Staged Processing:** Heavy stages execute in discrete passes (Audio Pass ➔ Visual Keyframe Pass ➔ Candidate Selection ➔ FFmpeg Render) to eliminate Out-Of-Memory (OOM) spikes.

---

## 5. Key Performance Indicators & Acceptance Targets

1. **Clip Yield:** 30–50 candidate highlights extracted per 4-hour stream when gameplay activity supports it.
2. **Output Quality:** Valid 1080x1920 9:16 MP4 (H.264/AAC), 30 fps, bitrate 5–8 Mbps, EBU R128 (-16 LUFS) normalized audio.
3. **Render Speed:** FFmpeg rendering at $\ge 2.0\times$ realtime speed using NVENC acceleration on RTX 3050.
4. **Transcription Accuracy:** Accurate word-level timestamps with synchronous burned-in subtitle highlighting.
5. **Zero Data Hallucination:** 100% of dashboard metrics, streamers, jobs, and clips ground directly in database state and physical files.
