"""
Candidate Generation & Highlight Scoring Service.

Synthesizes audio bursts, visual motion, and scene boundaries into optimal
15-60s highlight clip windows, applies multimodal composite scoring,
runs Temporal Non-Maximum Suppression (NMS), and persists candidates.
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.core.logging import logger
from app.models import Recording, DetectedEvent, ClipCandidate
from app.services.context_service import context_service


def compute_temporal_iou(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    """Computes temporal Intersection over Union (IoU) between two 1D time windows."""
    intersection = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    union = max(end_a, end_b) - min(start_a, start_b)
    if union <= 0.0:
        return 0.0
    return intersection / union


class CandidateService:
    """
    Synthesizes detected feature events into ranked, deduplicated
    short-form vertical clip candidates.
    """

    def __init__(
        self,
        min_duration: float = float(settings.MIN_CLIP_DURATION_SECONDS),
        max_duration: float = float(settings.MAX_CLIP_DURATION_SECONDS),
        iou_threshold: float = 0.30,
        audio_weight: float = 0.35,
        visual_weight: float = 0.35,
        context_weight: float = 0.30,
    ):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.iou_threshold = iou_threshold
        self.w_audio = audio_weight
        self.w_visual = visual_weight
        self.w_context = context_weight

    def generate_candidates_for_recording(
        self,
        db: Session,
        recording_id: int,
        target_count: int = 10,
    ) -> List[ClipCandidate]:
        """
        Main pipeline: Reads events for recording, builds windows, scores them,
        applies Temporal NMS, and saves ClipCandidate records to the database.
        """
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            raise ValueError(f"Recording #{recording_id} not found")

        total_duration = recording.duration_seconds or 60.0

        # Load all detected events for this recording
        events = (
            db.query(DetectedEvent)
            .filter(DetectedEvent.recording_id == recording_id)
            .order_by(DetectedEvent.start_time.asc())
            .all()
        )

        audio_events = [e for e in events if e.category == "audio" or "audio" in e.event_type]
        visual_events = [e for e in events if e.category == "visual" or "action" in e.event_type]
        scene_cuts = [e for e in events if e.event_type == "scene_cut"]

        # Facecam info from recording metadata or events
        rec_meta = recording.metadata_json or {}
        facecam_info = rec_meta.get("facecam", {})
        has_facecam = facecam_info.get("has_facecam", False)
        facecam_region = facecam_info.get("box") if has_facecam else None

        # Transcripts from recording metadata
        transcripts = rec_meta.get("transcripts", [])

        # 1. Synthesize candidate time windows
        raw_windows = self._synthesize_windows(
            audio_events=audio_events,
            visual_events=visual_events,
            scene_cuts=scene_cuts,
            transcripts=transcripts,
            total_duration=total_duration,
        )

        if not raw_windows:
            # Fallback: if no anchor events fired, generate evenly spaced windows
            logger.info(f"[CandidateService] No peak events detected. Generating baseline windows for Recording #{recording_id}.")
            raw_windows = self._generate_baseline_windows(total_duration)

        logger.info(f"[CandidateService] Synthesized {len(raw_windows)} candidate windows.")

        # 2. Score candidate windows
        scored_candidates: List[Dict[str, Any]] = []
        for w_start, w_end in raw_windows:
            w_duration = round(w_end - w_start, 2)
            if w_duration < self.min_duration or w_duration > self.max_duration:
                continue

            # Audio score in window
            score_audio, peak_audio = self._calculate_event_score(audio_events, w_start, w_end)

            # Visual score in window
            score_visual, peak_visual = self._calculate_event_score(visual_events, w_start, w_end)

            # Extract window transcript
            w_transcript = self._extract_window_transcript(transcripts, w_start, w_end)

            # Context evaluation via ContextService
            context_eval = context_service.evaluate_context(
                transcript=w_transcript,
                start_time=w_start,
                end_time=w_end,
                peak_audio_intensity=peak_audio,
                peak_visual_intensity=peak_visual,
                has_facecam=has_facecam,
            )

            score_context = context_eval["context_score"]

            # Multimodal composite score
            composite = (
                self.w_audio * score_audio +
                self.w_visual * score_visual +
                self.w_context * score_context
            )

            # Bonus for facecam engagement
            if has_facecam:
                composite += 0.05

            composite = round(min(1.0, max(0.1, composite)), 3)

            scored_candidates.append({
                "recording_id": recording_id,
                "start_time": w_start,
                "end_time": w_end,
                "duration": w_duration,
                "score_audio": round(score_audio, 3),
                "score_visual": round(score_visual, 3),
                "score_context": round(score_context, 3),
                "score_composite": composite,
                "event_category": context_eval.get("event_category", "General Chaos"),
                "has_facecam": has_facecam,
                "facecam_region": facecam_region,
                "transcript_text": w_transcript or None,
                "suggested_titles": context_eval.get("suggested_titles", []),
                "metadata_json": {
                    "summary": context_eval.get("summary", ""),
                    "provider_used": context_eval.get("provider_used", "local"),
                },
            })

        # 3. Temporal Non-Maximum Suppression (NMS)
        deduplicated = self._apply_temporal_nms(scored_candidates, self.iou_threshold)
        logger.info(f"[CandidateService] NMS reduced candidates from {len(scored_candidates)} to {len(deduplicated)}.")

        # Limit to target_count
        top_candidates = deduplicated[:target_count]

        # 4. Save to database
        db_candidates: List[ClipCandidate] = []
        for rank, cand_data in enumerate(top_candidates, start=1):
            cand = ClipCandidate(
                recording_id=cand_data["recording_id"],
                start_time=cand_data["start_time"],
                end_time=cand_data["end_time"],
                duration=cand_data["duration"],
                score_audio=cand_data["score_audio"],
                score_visual=cand_data["score_visual"],
                score_context=cand_data["score_context"],
                score_composite=cand_data["score_composite"],
                rank=rank,
                event_category=cand_data["event_category"],
                status="pending",
                has_facecam=cand_data["has_facecam"],
                facecam_region=cand_data["facecam_region"],
                transcript_text=cand_data["transcript_text"],
                suggested_titles=cand_data["suggested_titles"],
                metadata_json=cand_data["metadata_json"],
            )
            db.add(cand)
            db_candidates.append(cand)

        db.commit()
        for cand in db_candidates:
            db.refresh(cand)

        logger.info(f"[CandidateService] Successfully persisted {len(db_candidates)} ranked clip candidates for Recording #{recording_id}.")
        return db_candidates

    def _synthesize_windows(
        self,
        audio_events: List[DetectedEvent],
        visual_events: List[DetectedEvent],
        scene_cuts: List[DetectedEvent],
        transcripts: List[Dict[str, Any]],
        total_duration: float,
    ) -> List[Tuple[float, float]]:
        """
        Generates candidate time windows anchored on high-energy events
        with boundary snapping to natural speech pauses and scene cuts.
        """
        windows: List[Tuple[float, float]] = []
        anchors: List[Tuple[float, float]] = []  # (peak_time, intensity)

        # Collect peak anchors from audio
        for ae in audio_events:
            mid = (ae.start_time + ae.end_time) / 2.0
            anchors.append((mid, ae.intensity))

        # Collect peak anchors from visual
        for ve in visual_events:
            mid = (ve.start_time + ve.end_time) / 2.0
            anchors.append((mid, ve.intensity))

        if not anchors:
            return []

        # Sort anchors chronologically
        anchors.sort(key=lambda x: x[0])

        cut_times = [c.start_time for c in scene_cuts]

        for peak_time, _ in anchors:
            # Ideal window size ~30 seconds (8s lead-in, 22s resolution)
            w_start = max(0.0, peak_time - 8.0)
            w_end = min(total_duration, peak_time + 22.0)

            # Snap to scene cuts if nearby (within 2.0 seconds)
            w_start = self._snap_to_nearest_cut(w_start, cut_times, max_delta=2.0)
            w_end = self._snap_to_nearest_cut(w_end, cut_times, max_delta=2.0)

            # Snap to transcript boundary if available
            w_start, w_end = self._snap_to_transcript_bounds(w_start, w_end, transcripts)

            # Ensure minimum duration
            if (w_end - w_start) < self.min_duration:
                w_end = min(total_duration, w_start + self.min_duration)
                if (w_end - w_start) < self.min_duration:
                    w_start = max(0.0, w_end - self.min_duration)

            # Ensure maximum duration
            if (w_end - w_start) > self.max_duration:
                w_end = w_start + self.max_duration

            windows.append((round(w_start, 2), round(w_end, 2)))

        return windows

    def _generate_baseline_windows(self, total_duration: float) -> List[Tuple[float, float]]:
        """Generates evenly distributed sliding windows when no spike events occur."""
        windows = []
        step = 25.0
        window_size = 30.0

        current = 0.0
        while (current + self.min_duration) <= total_duration:
            end = min(total_duration, current + window_size)
            windows.append((round(current, 2), round(end, 2)))
            current += step
            if end >= total_duration:
                break
        return windows

    def _snap_to_nearest_cut(self, time_sec: float, cut_times: List[float], max_delta: float = 2.0) -> float:
        """Snaps time to the closest scene cut within max_delta seconds."""
        if not cut_times:
            return time_sec
        closest_cut = min(cut_times, key=lambda c: abs(c - time_sec))
        if abs(closest_cut - time_sec) <= max_delta:
            return closest_cut
        return time_sec

    def _snap_to_transcript_bounds(
        self,
        start_sec: float,
        end_sec: float,
        transcripts: List[Dict[str, Any]],
    ) -> Tuple[float, float]:
        """Snaps start and end times to avoid cutting sentences in half."""
        if not transcripts:
            return start_sec, end_sec

        new_start = start_sec
        new_end = end_sec

        # Try to snap start to beginning of a segment
        for seg in transcripts:
            s_start = seg.get("start", 0.0)
            if abs(s_start - start_sec) <= 3.0:
                new_start = s_start
                break

        # Try to snap end to end of a segment
        for seg in reversed(transcripts):
            s_end = seg.get("end", 0.0)
            if abs(s_end - end_sec) <= 3.0:
                new_end = s_end
                break

        return new_start, new_end

    def _calculate_event_score(
        self,
        events: List[DetectedEvent],
        w_start: float,
        w_end: float,
    ) -> Tuple[float, float]:
        """Calculates normalized average and peak event intensity in time window."""
        overlapping = [
            e for e in events
            if max(e.start_time, w_start) < min(e.end_time, w_end)
        ]
        if not overlapping:
            return 0.35, 0.0  # Baseline ambient score

        intensities = [e.intensity for e in overlapping]
        avg_intensity = sum(intensities) / len(intensities)
        peak_intensity = max(intensities)

        # Normalized score between 0.35 and 0.95
        score = 0.35 + (0.60 * min(1.0, (avg_intensity * 0.6 + peak_intensity * 0.4)))
        return min(1.0, score), peak_intensity

    def _extract_window_transcript(
        self,
        transcripts: List[Dict[str, Any]],
        w_start: float,
        w_end: float,
    ) -> str:
        """Extracts text spoken within the given window."""
        matched_texts = []
        for seg in transcripts:
            s_start = seg.get("start", 0.0)
            s_end = seg.get("end", 0.0)
            if max(s_start, w_start) < min(s_end, w_end):
                matched_texts.append(seg.get("text", "").strip())
        return " ".join(matched_texts).strip()

    def _apply_temporal_nms(
        self,
        candidates: List[Dict[str, Any]],
        iou_threshold: float,
    ) -> List[Dict[str, Any]]:
        """
        Greedy 1D Temporal Non-Maximum Suppression (NMS).
        Deduplicates candidate windows covering the same moment.
        """
        if not candidates:
            return []

        # Sort descending by composite score
        sorted_cands = sorted(candidates, key=lambda c: c["score_composite"], reverse=True)
        keep: List[Dict[str, Any]] = []

        while sorted_cands:
            best = sorted_cands.pop(0)
            keep.append(best)

            remaining = []
            for other in sorted_cands:
                iou = compute_temporal_iou(
                    best["start_time"], best["end_time"],
                    other["start_time"], other["end_time"],
                )
                if iou < iou_threshold:
                    remaining.append(other)

            sorted_cands = remaining

        return keep


# Global singleton instance
candidate_service = CandidateService()
