# External API Integrations Specification

**Project:** GTA 6 AI Clip Factory  
**Version:** 1.0.0  
**Status:** Approved Architectural Standard  

---

## 1. Overview & Core Philosophy

The GTA 6 AI Clip Factory is designed with a **Hybrid Edge-First Architecture**:
* **Local Processing First:** Heavy video editing, audio analysis, facecam tracking, and transcription run locally via FFmpeg, OpenCV, faster-whisper, and PyTorch (accelerated by the onboard NVIDIA RTX 3050 6GB GPU).
* **Targeted Cloud Intelligence:** External APIs are leveraged specifically where they provide high value: YouTube Live Stream status monitoring, channel metadata resolution, and state-of-the-art vision-language model reasoning (generating viral titles, hooks, and context evaluation).
* **Zero Breakage on Missing Keys:** Missing external credentials will **never crash the system**. The application validates configuration on startup, gracefully disables unconfigured external features, provides local deterministic fallbacks, and surfaces clear integration status in the dashboard.
* **Separation of API Credentials from Content Permissions:** Having an API key does *not* grant rights to monetize or process a creator's stream. Streamer permissions are tracked independently via an explicit permission verification system in the database.

---

## 2. Integrated External APIs

```
+-----------------------------------------------------------------------------------+
|                           GTA 6 AI Clip Factory Engine                            |
+-------------------------+-------------------------------+-------------------------+
                          |                               |
       [ YouTube Monitoring Layer ]             [ Multimodal AI Layer ]
                          |                               |
        +-----------------+-----------------+             +-------------------+
        |                                   |             |                   |
        v                                   v             v                   v
[ YouTube Data API v3 ]            [ YouTube OAuth 2.0 ] [ Google Gemini ] [ OpenAI API ]
- Channel ID discovery             - Streamer account    - Context scoring - Title generation
- Live stream status detection       authorization       - Game chaos eval - Summary & tags
- View counts & chat velocity      - Granular read scopes- Local heuristic - Fallback logic
                                                           fallback
```

---

## 3. Detailed API Breakdown

### 1. YouTube Data API v3
* **Purpose:** Monitor registered GTA 6 streamers, detect when they broadcast live, and fetch stream metadata (title, category, startedAt, viewer count).
* **Features Enabled:**
  * Automated live detection without manual link pasting.
  * Real-time metadata tracking.
  * Detection of stream category (verifying Grand Theft Auto VI gameplay).
* **Official Portal:** [Google Cloud Console - YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
* **Pricing & Free Limits:**
  * Free quota: **10,000 units/day**.
  * Search endpoint (`search.list`): 100 units per call (expensive).
  * Videos endpoint (`videos.list` with channel live broadcast filter): 1 unit per call (ultra-efficient).
  * Cost: Free within quota.
* **Environment Variables:**
  ```env
  YOUTUBE_API_KEY="AIzaSy..."
  YOUTUBE_POLL_INTERVAL_SECONDS=120
  ```
* **Local / Zero-Cost Fallback:**
  * Users can manually provide authorized local video files or direct stream URLs for ingestion. Live polling simply pauses if no key is configured.

---

### 2. YouTube OAuth 2.0 (Optional)
* **Purpose:** Allows registered streamers to authenticate directly and authorize the Clip Factory to access their stream broadcast data with verified consent.
* **Features Enabled:**
  * Cryptographic streamer permission linking.
  * Zero quota collision with generic public keys.
* **Official Portal:** [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials)
* **Pricing & Free Limits:**
  * Free standard tier.
* **Environment Variables:**
  ```env
  YOUTUBE_CLIENT_ID="...apps.googleusercontent.com"
  YOUTUBE_CLIENT_SECRET="..."
  YOUTUBE_REDIRECT_URI="http://localhost:8000/api/v1/auth/youtube/callback"
  ```
* **Fallback:** Manual permission management via the Permissions dashboard (admin enters streamer consent records manually).

---

### 3. Google Gemini API (Recommended VLM Provider)
* **Purpose:** Advanced multimodal context analysis, streamer reaction evaluation, viral hook generation, and click-worthy title synthesis.
* **Features Enabled:**
  * Scene comprehension (detecting police chases, comedic fails, high-speed stunts, gunfights).
  * Streamer facecam reaction alignment (matching laughter/shock with gameplay events).
  * Generation of 3 distinct title styles: *Viral Clickbait*, *Clean Descriptive*, and *Meme/Reaction*.
* **Official Portal:** [Google AI Studio](https://aistudio.google.com/)
* **Pricing & Free Limits:**
  * Generous free tier (up to 15 RPM on Gemini 1.5/2.0 Flash at no monetary charge).
* **Environment Variables:**
  ```env
  GEMINI_API_KEY="AIzaSy..."
  VLM_MODEL_NAME="gemini-1.5-flash"
  ```
* **Local Fallback:**
  * Deterministic rule-based template engine: constructs high-engagement titles using detected gameplay keywords (e.g., `"INSANE 6-STAR CHASE IN VICE CITY!"`) and audio excitement scores.

---

### 4. OpenAI API (Alternative VLM Provider)
* **Purpose:** Alternative cloud intelligence engine for users who prefer GPT-4o / GPT-4o-mini for event description and title generation.
* **Features Enabled:** Parity with Gemini for scene summary and title generation.
* **Official Portal:** [OpenAI Platform](https://platform.openai.com/api-keys)
* **Pricing:** Pay-as-you-go ($0.15 / 1M input tokens on `gpt-4o-mini`).
* **Environment Variables:**
  ```env
  OPENAI_API_KEY="sk-..."
  OPENAI_MODEL_NAME="gpt-4o-mini"
  ```

---

### 5. Cloud Transcription APIs (Optional Cloud Alternative)
* **Purpose:** Cloud offload for speech-to-text if local GPU transcription is constrained.
* **Options:** Groq Whisper (ultra-fast, free beta tier) or Deepgram.
* **Local Primary:** `faster-whisper` running locally on the RTX 3050 (or CPU fallback) using int8/float16.

---

### 6. Cloud Storage APIs (Optional)
* **Purpose:** Offsite backup or CDN delivery for rendered vertical clips.
* **Supported Protocols:** S3-compatible (Cloudflare R2, AWS S3, Google Cloud Storage).
* **Local Primary:** All MP4 clips, thumbnails, and subtitle files are saved locally on the filesystem under `data/clips/` and served directly by the backend.

---

## 4. Security & Credential Hygiene Rules

1. **Strict Environment Segregation:** Secrets reside **only** in the local `.env` file.
2. **Never Committed to Git:** `.gitignore` explicitly excludes `.env`, `*.key`, `*.pem`, and `credentials.json`.
3. **No Secret Leaks in Responses:** API endpoints that report integration status (e.g., `GET /api/v1/integrations/status`) return booleans and masked identifiers only (e.g. `{"gemini_connected": true, "key_hint": "...aB4x"}`).
4. **Credential Validation at Boot:** During application startup, a non-blocking diagnostic routine verifies key formats and network reachability.

