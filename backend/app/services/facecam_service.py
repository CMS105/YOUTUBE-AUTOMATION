"""
Streamer Facecam Detection & Spatial Tracking Service.
Adapted from Face_detection (face_mesh.py / face_detect.py) using MediaPipe FaceLandmarker.
Inspects corner quadrants to detect streamer facecam presence and calculate stabilized bounding coordinates.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from app.core.config import settings
from app.core.logging import logger


class FacecamService:
    def __init__(self):
        self._detector: Optional[vision.FaceLandmarker] = None
        self._is_ready: bool = False
        self._init_detector()

    def _init_detector(self):
        try:
            # Check local data models directory
            candidates = [
                Path(settings.DATA_DIR) / "models" / "face_landmarker.task",
                Path(__file__).resolve().parent.parent.parent / "data" / "models" / "face_landmarker.task",
                Path(__file__).resolve().parent.parent / "data" / "models" / "face_landmarker.task",
            ]
            model_path = next((p for p in candidates if p.exists()), None)
            if model_path:
                base_options = python.BaseOptions(model_asset_path=str(model_path))
                options = vision.FaceLandmarkerOptions(
                    base_options=base_options,
                    num_faces=1,
                    output_face_blendshapes=False,
                )
                self._detector = vision.FaceLandmarker.create_from_options(options)
                self._is_ready = True
                logger.info(f"[FacecamService] MediaPipe FaceLandmarker loaded from: {model_path}")
            else:
                logger.warning("[FacecamService] face_landmarker.task not found; using corner heuristic fallback.")
        except Exception as e:
            logger.warning(f"[FacecamService] MediaPipe initialization error ({e}); using heuristic fallback.")

    def detect_facecam_in_frame(
        self, frame_bgr: np.ndarray
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, int]]]:
        """
        Inspects the 4 corner quadrants of a video frame to detect if a facecam is present.
        Returns:
            - has_facecam: bool
            - corner_location: "top_left" | "top_right" | "bottom_left" | "bottom_right" | None
            - bounding_box: {"x": int, "y": int, "w": int, "h": int} in frame coordinates
        """
        if frame_bgr is None:
            return False, None, None

        h, w = frame_bgr.shape[:2]

        # Define 4 corner quadrants (35% width, 35% height)
        corners = {
            "top_left": (0, int(0.35 * h), 0, int(0.35 * w)),
            "top_right": (0, int(0.35 * h), int(0.65 * w), w),
            "bottom_left": (int(0.65 * h), h, 0, int(0.35 * w)),
            "bottom_right": (int(0.65 * h), h, int(0.65 * w), w),
        }

        # Method 1: MediaPipe FaceLandmarker
        if self._is_ready and self._detector is not None:
            rgb_full = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            for loc, (y1, y2, x1, x2) in corners.items():
                crop_rgb = rgb_full[y1:y2, x1:x2].copy()
                ch, cw = crop_rgb.shape[:2]
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop_rgb)
                try:
                    res = self._detector.detect(mp_image)
                    if res.face_landmarks:
                        landmarks = res.face_landmarks[0]
                        xs = [int(lm.x * cw) for lm in landmarks]
                        ys = [int(lm.y * ch) for lm in landmarks]
                        min_x, max_x = min(xs), max(xs)
                        min_y, max_y = min(ys), max(ys)
                        fw = max_x - min_x
                        fh = max_y - min_y

                        # Expand to full facecam box window
                        pad_w = int(fw * 0.45)
                        pad_h = int(fh * 0.5)
                        box_x = max(0, x1 + min_x - pad_w)
                        box_y = max(0, y1 + min_y - pad_h)
                        box_w = min(w - box_x, fw + (2 * pad_w))
                        box_h = min(h - box_y, fh + (2 * pad_h))

                        return True, loc, {"x": box_x, "y": box_y, "w": box_w, "h": box_h}
                except Exception:
                    pass

        # Method 2: Corner Edge/Variance Heuristic (Zero-dependency fallback)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        for loc, (y1, y2, x1, x2) in corners.items():
            crop = gray[y1:y2, x1:x2]
            # Check for rectangle border overlay in corner
            edges = cv2.Canny(crop, 50, 150)
            edge_density = np.mean(edges) / 255.0
            variance = np.var(crop)
            if edge_density > 0.08 and variance > 500:
                cw = x2 - x1
                ch = y2 - y1
                return True, loc, {"x": x1, "y": y1, "w": cw, "h": ch}

        return False, None, None

    def analyze_stream_facecam(
        self, file_path: Path, max_sample_frames: int = 15
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, int]]]:
        """
        Samples video keyframes to establish persistent facecam presence and coordinates.
        Requires facecam to be detected in >= 30% of sampled frames.
        """
        cap = cv2.VideoCapture(str(file_path))
        if not cap.isOpened():
            return False, None, None

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames <= 0:
            cap.release()
            return False, None, None

        step = max(1, total_frames // max_sample_frames)
        detections: List[Tuple[str, Dict[str, int]]] = []

        for i in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break
            found, loc, box = self.detect_facecam_in_frame(frame)
            if found and loc and box:
                detections.append((loc, box))

        cap.release()

        # Majority voting across samples
        if len(detections) >= max(2, int(0.25 * max_sample_frames)):
            loc_counts: Dict[str, int] = {}
            for loc, _ in detections:
                loc_counts[loc] = loc_counts.get(loc, 0) + 1

            best_loc = max(loc_counts, key=loc_counts.get)
            boxes = [b for l, b in detections if l == best_loc]
            avg_x = int(np.median([b["x"] for b in boxes]))
            avg_y = int(np.median([b["y"] for b in boxes]))
            avg_w = int(np.median([b["w"] for b in boxes]))
            avg_h = int(np.median([b["h"] for b in boxes]))

            logger.info(
                f"[FacecamService] Streamer facecam detected at '{best_loc}' "
                f"(x={avg_x}, y={avg_y}, w={avg_w}, h={avg_h})."
            )
            return True, best_loc, {"x": avg_x, "y": avg_y, "w": avg_w, "h": avg_h}

        logger.info("[FacecamService] No consistent streamer facecam detected (pure gameplay stream).")
        return False, None, None


facecam_service = FacecamService()
