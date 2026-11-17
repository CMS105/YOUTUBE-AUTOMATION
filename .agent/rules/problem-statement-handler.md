# Multi-Domain Analysis & Approval-Gated Execution Protocol

Whenever a new phase, feature, or major architectural pivot is initiated:

## STAGE 1: Tech Scan & Plan Proposal (NO FILE EDITS)
1. **Cross-Domain Evaluation**:
   - Evaluate the problem across all relevant fields: Video Engineering (FFmpeg, NVENC, codecs), Computer Vision (OpenCV, PySceneDetect, MediaPipe), Audio Signal Processing (SciPy, faster-whisper), Modern Backend (FastAPI, SQLAlchemy, PostgreSQL), and Production Frontend (Next.js 15, Tailwind, Recharts).
2. **Present the Architectural Plan**:
   - Detail the proposed modules, reused components from existing repositories, and hardware impact.
3. **Mandatory Approval Gate**:
   - Present the phase roadmap and stop for user review and approval before executing heavy implementation.

## STAGE 2: Execution (ONLY AFTER USER ACCEPTS)
Once approved:
1. Update `.gsd/ROADMAP.md` and `progress.txt`.
2. Execute tasks sequentially following GSD guidelines.
3. Verify with end-to-end unit and integration tests before marking tasks completed.

