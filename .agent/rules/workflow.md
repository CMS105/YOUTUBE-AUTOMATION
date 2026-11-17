# Agent Autonomous Workflow & Quality Standards

## 1. Memory-First Protocol & GSD Alignment
Before starting any new engineering task or file modification:
1. **Align with `.gsd/REQUIREMENTS.md`**: Verify that the proposed code satisfies an explicit requirement (PERM, YT, INGEST, AUD, VIS, SCORE, EDIT, DASH, DATA, API, or HW).
2. **Inspect `progress.txt`**: Confirm the active phase and ensure no duplicate or conflicting work.
3. **Hardware Guardrails**: Always check VRAM consumption and ensure sequential stage execution on the NVIDIA RTX 3050 6GB GPU.

## 2. Code Quality & Windows Engineering Standards
- **Strict Type Hints**: Every Python function in `backend/` must include explicit type annotations and pass Pydantic / mypy validation without `Any` shortcuts.
- **Robust Windows Path Handling**: Always use `Path` from `pathlib` or `os.path.join`. Never hardcode Unix forward slashes for filesystem paths.
- **Fail-Safe Video & Audio Processing**:
  - Always clean up temporary audio and frame files in `finally` blocks.
  - Subprocess calls to FFmpeg must specify timeouts and capture stderr for diagnostic inspection.
  - PyAV audio calls must use the `_safe_av_open` patch to prevent `metadata_errors` crashes on PyAV >= 14.
- **Clean Diff Hygiene**: No orphaned print statements, dead code, or leftover scratch files. Use structured logging (`logger.info`, `logger.error`).

## 3. External API & Security Standards
- **Never Hardcode Secrets**: All API keys, tokens, and credentials must be read from environment variables via `backend/app/core/config.py`.
- **Zero Hallucination**: Never fabricate mock live statuses, statistics, or generated clips when real processing is requested.
- **Deterministic Offline Fallbacks**: Every cloud API call (Gemini, OpenAI, YouTube) must have a verified local fallback path so the system never breaks when keys are omitted.

## 4. Post-Task Protocol
Upon completing an implementation milestone:
1. **Record Architectural Decisions**: Document any new schema or threshold adjustments in `.gsd/PROJECT.md`.
2. **Update `progress.txt`**: Move the completed step to `[COMPLETED TASKS]` with a timestamp.
3. **Commit Incrementally**: Ensure atomic, descriptive git commit messages (`feat:`, `fix:`, `test:`, `docs:`).

