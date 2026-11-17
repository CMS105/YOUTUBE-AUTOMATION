"""
Visual Analysis Service:
Extracts scene cuts, computes gameplay motion energy curves,
and detects high-action gameplay events (car chases, crashes, combat).
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple
import cv2
import numpy as np

from app.core.logging import logger


class VisualEvent:
    def __init__(self, event_type: str, start_time: float, end_time: float, intensity: float, peak_time: float):
        self.event_type = event_type
        self.start_time = start_time
        self.end_time = end_time
        self.intensity = intensity  # 0.0 to 100.0
        self.peak_time = peak_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "start_time": round(self.start_time, 2),
            "end_time": round(self.end_time, 2),
            "intensity": round(self.intensity, 2),
            "peak_time": round(self.peak_time, 2),
        }


class VisualAnalysisService:
    @staticmethod
    def analyze_video_motion_and_cuts(
        file_path: Path, sample_fps: float = 2.0
    ) -> Tuple[List[float], np.ndarray, np.ndarray, List[VisualEvent]]:
        """
        Samples video at sample_fps, calculates scene cut boundaries and gameplay motion energy.
        Returns:
            - scene_cuts: list of cut timestamps in seconds
            - sample_timestamps: numpy array of sampled times
            - motion_curve: normalized motion energy values [0.0, 100.0]
            - visual_events: high-action events (chases, explosions, crashes)
        """
        cap = cv2.VideoCapture(str(file_path))
        if not cap.isOpened():
            logger.warning(f"[VisualAnalysis] Cannot open video {file_path.name}")
            return [], np.zeros(0), np.zeros(0), []

        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frame_interval = max(1, int(round(source_fps / sample_fps)))

        prev_gray = None
        prev_hist = None

        timestamps: List[float] = []
        motion_scores: List[float] = []
        scene_cuts: List[float] = []

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                current_time = round(frame_idx / source_fps, 2)
                timestamps.append(current_time)

                # Resize to small thumbnail for fast CPU/GPU differencing (320x180)
                small = cv2.resize(frame, (320, 180))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

                # Compute color histogram for cut detection
                hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
                cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

                if prev_gray is not None and prev_hist is not None:
                    # 1. Motion energy: absolute pixel difference
                    diff = cv2.absdiff(gray, prev_gray)
                    motion = float(np.mean(diff))
                    motion_scores.append(motion)

                    # 2. Scene cut detection: histogram correlation drops
                    sim = cv2.compareHist(hist, prev_hist, cv2.HISTCMP_CORREL)
                    if sim < 0.45:  # Significant scene transition
                        scene_cuts.append(current_time)
                else:
                    motion_scores.append(0.0)

                prev_gray = gray
                prev_hist = hist

            frame_idx += 1

        cap.release()

        timestamps_arr = np.array(timestamps)
        motion_arr = np.array(motion_scores)

        # Normalize motion into [0.0, 100.0]
        max_motion = np.max(motion_arr) if len(motion_arr) > 0 and np.max(motion_arr) > 0 else 1.0
        motion_norm = (motion_arr / max_motion) * 100.0

        # Detect High-Action Events
        events: List[VisualEvent] = []
        if len(motion_norm) > 0:
            median_motion = float(np.median(motion_norm))
            std_motion = float(np.std(motion_norm))
            action_threshold = max(30.0, median_motion + (1.5 * std_motion))

            in_action = False
            start_i = 0
            for i, val in enumerate(motion_norm):
                if val >= action_threshold and not in_action:
                    in_action = True
                    start_i = i
                elif val < action_threshold and in_action:
                    in_action = False
                    end_i = i
                    if (timestamps_arr[end_i] - timestamps_arr[start_i]) >= 1.5:
                        chunk = motion_norm[start_i:end_i]
                        peak_i = start_i + int(np.argmax(chunk))
                        events.append(
                            VisualEvent(
                                event_type="gameplay_action",
                                start_time=float(timestamps_arr[start_i]),
                                end_time=float(timestamps_arr[end_i]),
                                intensity=float(np.max(chunk)),
                                peak_time=float(timestamps_arr[peak_i]),
                            )
                        )

        logger.info(
            f"[VisualAnalysis] Completed: {len(timestamps)} frames sampled, "
            f"{len(scene_cuts)} scene cuts, {len(events)} action bursts detected."
        )
        return scene_cuts, timestamps_arr, motion_norm, events


visual_analysis_service = VisualAnalysisService()
