# GTA 6 AI Clip Factory

AI-assisted highlight detection and vertical clip creation for authorized GTA 6 gameplay recordings.

The project combines a **FastAPI** processing backend with a **Next.js 15** dashboard. It analyses audio and video signals, identifies candidate highlight moments, scores them, and renders vertical clips with subtitles and thumbnails.

> **Important:** This project monitors public YouTube livestream metadata through the official YouTube Data API. It does not download or capture YouTube streams. Media processing accepts authorized local recordings or other explicitly authorized media sources. Creator permission is checked separately from API credentials. Automatic social publishing is disabled.

## Features

- **Streamer management:** Register channels and keep creator records.
- **Permission controls:** Track consent status and block ingestion when permission is not active.
- **Authorized media ingestion:** Upload or provide approved local recordings.
- **Audio analysis:** Detect loudness and reaction spikes; transcribe speech with faster-whisper.
- **Visual analysis:** Detect scene changes and motion patterns; optionally track facecam placement.
- **Highlight candidates:** Generate time windows, rank moments using audio, visual and contextual signals, and remove overlapping duplicates.
- **Vertical rendering:** Produce 9:16 clips with subtitle overlays and thumbnails using the rendering pipeline.
- **Dashboard:** Manage streamers, permissions, clips, the processing queue, storage and analytics.
- **YouTube live monitoring:** Use YouTube Data API v3 for public live-stream metadata only.
- **Local-first operation:** AI/video processing and generated media are designed to run locally, with optional external AI providers.

## Architecture

```text
Next.js Dashboard (port 3000)
          |
          | REST API
          v
FastAPI Backend (port 8000)
          |
          +-- Streamer and permission management
          +-- Authorized media ingestion
          +-- Audio / speech analysis
          +-- Visual / facecam analysis
          +-- Highlight generation and scoring
          +-- Vertical video rendering
          +-- YouTube metadata monitor
          |
          v
Local media storage + SQL database
```

## Technology stack

| Area | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| Database | SQLAlchemy, PostgreSQL with local SQLite fallback where configured |
| Migrations | Alembic |
| Audio / transcription | faster-whisper, PyAV |
| Video / vision | OpenCV, MediaPipe |
| Rendering | PyAV and optional FFmpeg |
| YouTube integration | YouTube Data API v3 |
| Optional AI providers | Google Gemini and OpenAI |
| Workflow | GSD-style project specifications and progress tracking |

## Requirements

- Windows 10/11 (the included launchers target Windows)
- Python 3.10 or newer
- Node.js 20 or newer recommended
- Git
- NVIDIA GPU with CUDA is recommended for faster processing; CPU fallback is supported by the configuration.
- FFmpeg/FFprobe are optional when the embedded PyAV rendering path is available. Install them for the CLI/hardware-encoding path.

Video analysis and rendering are resource-intensive. A serverless frontend host is not suitable for the full processing worker and local media storage.

## Quick start (Windows)

### 1. Clone the repository

```powershell
git clone https://github.com/CMS105/YOUTUBE-AUTOMATION.git
cd YOUTUBE-AUTOMATION
```

### 2. Configure environment

```powershell
Copy-Item .env.example .env
```

Open `.env` and set the database connection and any API credentials you plan to use. Keep real credentials private; do not commit `.env`.

### 3. Install backend dependencies

Create and activate a virtual environment:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Install dependencies from the backend dependency manifest if present in your checkout. If the manifest is missing, inspect the imports and project setup before installing packages individually; do not assume a dependency list.

Return to the repository root:

```powershell
cd ..
```

### 4. Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

### 5. Start the application

The repository includes Windows launch scripts:

```powershell
.\run_factory.bat
```

Or use:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_factory.ps1
```

When startup succeeds:

- Dashboard: http://localhost:3000
- Backend root: http://127.0.0.1:8000
- API documentation: http://127.0.0.1:8000/api/v1/docs

If the launcher reports missing Python packages, install the dependencies required by the backend and retry. Configure PostgreSQL if using it; otherwise confirm that the application's SQLite fallback is enabled in the current configuration.

## API credentials

All credentials are optional unless the feature you are using requires them. The application has local processing/fallback paths for several AI features.

| Variable | Purpose | Setup |
|---|---|---|
| `YOUTUBE_API_KEY` | Public live-stream and channel metadata | [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) |
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | Optional OAuth client configuration | [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials) |
| `GEMINI_API_KEY` | Optional contextual AI analysis and title generation | [Google AI Studio](https://aistudio.google.com/) |
| `OPENAI_API_KEY` | Optional alternative AI provider | [OpenAI API keys](https://platform.openai.com/api-keys) |

Copy values into your local `.env`. Never paste secrets into source code, issues, screenshots, or commits. Restrict API keys to the required API and rotate them if exposed.

**YouTube API limitations:** The Data API provides metadata such as channel and live-broadcast information. It does not grant permission to ingest or record a stream. Use only media files or feeds you have rights and explicit authorization to process.

See [docs/API_INTEGRATIONS.md](docs/API_INTEGRATIONS.md) for the integration details.

## Typical workflow

1. Start the dashboard and backend.
2. Add a creator/channel in **Streamers**.
3. Record the creator's explicit consent in **Permissions** and ensure the status is active.
4. Upload an authorized gameplay recording.
5. Run the analysis pipeline to extract audio/video features.
6. Review and rank generated highlight candidates.
7. Render a vertical clip using the available preset.
8. Preview the output and download the MP4 and thumbnail.

## Safety and content rights

- Do not ingest or process media without the creator's permission and the necessary rights.
- Do not use this project to bypass DRM, access controls, or platform restrictions.
- YouTube live monitoring is metadata monitoring only; media ingestion is a separate authorized workflow.
- Generated clips are saved for manual review and download. Automatic social publishing is disabled by default.
- Follow YouTube API Services Terms and the applicable copyright and privacy requirements.

## Repository layout

```text
.
├── .agent/                 # Agent workflow rules
├── .gsd/                   # Project, requirements and roadmap
├── backend/
│   ├── alembic/            # Database migrations
│   ├── app/
│   │   ├── core/            # Settings and logging
│   │   ├── routers/         # FastAPI endpoints
│   │   └── services/        # Analysis, scoring and rendering services
│   ├── data/                # Models and local development data
│   └── tests/               # Backend and pipeline tests
├── data/                    # Local runtime media directories
├── docs/                    # User manual, API guide and reuse audit
├── frontend/
│   └── src/
│       ├── app/             # Dashboard pages
│       ├── components/      # Shared UI components
│       └── services/        # API client
├── .env.example
├── progress.txt
├── ralph-loop.ps1
├── run_factory.bat
└── run_factory.ps1
```

## Documentation

- [User operations manual](docs/USER_MANUAL.md)
- [External API integrations](docs/API_INTEGRATIONS.md)
- [Repository reuse audit](docs/REPOSITORY_REUSE_AUDIT.md)
- [GSD project definition](.gsd/PROJECT.md)
- [Requirements](.gsd/REQUIREMENTS.md)
- [Roadmap](.gsd/ROADMAP.md)

## Testing

Run the backend tests from the backend environment:

```powershell
cd backend
python -m pytest -q
```

The repository contains phase-specific test modules under `backend/tests/`. Some tests may require optional models, environment variables, GPU libraries, a database, or local media fixtures. Review test prerequisites and report the actual result; do not treat a test as passing if it was skipped, cancelled, or failed.

Build the dashboard:

```powershell
cd frontend
npm run build
```

## Hosting and deployment

This is a **hybrid local-processing application**, not a static website.

- **Frontend:** The Next.js dashboard can be deployed separately to Vercel or another Node-compatible host.
- **Backend:** Deploy FastAPI to a persistent Python host/container that supports long-running tasks and the required system dependencies.
- **Processing worker and media:** Keep these on a persistent machine or GPU-capable server with adequate disk space. Serverless functions and ephemeral filesystems are not appropriate for long video processing.
- **Database:** Use a managed PostgreSQL service for a remote deployment.
- **Secrets:** Configure environment variables in the host's secret manager; never commit `.env`.

The current repository configuration defaults to local service URLs and local media folders. Before a public deployment, configure production CORS origins, database, storage, worker execution, authentication/access controls, upload limits, and secret variables. Do not expose a public instance with unrestricted upload or processing endpoints.

## Current deployment status

The repository source is hosted on GitHub. A live production application is **not claimed by this README**. Deployment must be completed and verified separately for the frontend, backend API, and persistent processing/storage services.

## License

No license file was present when this README was prepared. Unless a license is added, the repository's code is not automatically granted an open-source license. Add a `LICENSE` file before inviting reuse or redistribution.

---

Built for authorized GTA 6 creator workflows. Keep the creator in control of their content.
