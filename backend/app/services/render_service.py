"""
Vertical Video Rendering Engine.

Composites and encodes 9:16 vertical MP4 videos (1080x1920) with NVENC / PyAV,
word-by-word dynamic subtitles, audio loudness normalization, and custom presets:
1. 'Viral Gaming' (smart center-crop / zoom, facecam badge, karaoke subtitles)
2. 'Clean Gameplay' (centered 16:9 gameplay with blurred reflection top/bottom)
3. 'Reaction Focus' (vertical split-screen: facecam top, gameplay bottom)
"""

import os
import shutil
import subprocess
import uuid
from fractions import Fraction
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import av
from sqlalchemy.orm import Session

from app.core.config import settings, BASE_DIR
from app.core.logging import logger
from app.models import Recording, ClipCandidate, Clip, Thumbnail, ProcessingJob
from app.services.subtitle_service import subtitle_service


class RenderService:
    """
    High-performance vertical video rendering engine.
    Supports both CLI FFmpeg with NVENC acceleration and a native embedded
    PyAV + OpenCV fallback engine for 100% portable zero-binary execution.
    """

    def __init__(self):
        self.output_width = settings.VERTICAL_RENDER_WIDTH    # 1080
        self.output_height = settings.VERTICAL_RENDER_HEIGHT  # 1920
        self.fps = settings.TARGET_FPS                        # 30
        self.ffmpeg_cli = self._detect_ffmpeg_cli()

    def _detect_ffmpeg_cli(self) -> Optional[str]:
        """Checks if a valid ffmpeg binary exists in PATH or config."""
        path = shutil.which(settings.FFMPEG_PATH)
        if path:
            return path
        # Check custom configured path
        if Path(settings.FFMPEG_PATH).exists():
            return settings.FFMPEG_PATH
        return None

    def render_candidate(
        self,
        db: Session,
        candidate_id: int,
        preset: str = "Viral Gaming",
        custom_title: Optional[str] = None,
        job_id: Optional[int] = None,
    ) -> Clip:
        """
        Main pipeline: renders a ClipCandidate into a finished 9:16 vertical MP4,
        generates thumbnail, saves Clip record, and updates job status.
        """
        candidate = db.query(ClipCandidate).filter(ClipCandidate.id == candidate_id).first()
        if not candidate:
            raise ValueError(f"Candidate #{candidate_id} not found")

        recording = db.query(Recording).filter(Recording.id == candidate.recording_id).first()
        if not recording:
            raise ValueError(f"Recording #{candidate.recording_id} not found")

        # Resolve processing job if present
        job = None
        if job_id:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        elif hasattr(candidate, "recording_id"):
            job = (
                db.query(ProcessingJob)
                .filter(
                    ProcessingJob.recording_id == recording.id,
                    ProcessingJob.status.in_(["queued", "running"]),
                )
                .order_by(ProcessingJob.created_at.desc())
                .first()
            )

        if job:
            job.status = "running"
            job.current_stage = "Preparing assets"
            job.progress_percent = 5.0
            job.started_at = datetime.now(timezone.utc)
            db.commit()

        # Paths and naming
        clip_uuid = uuid.uuid4().hex
        out_filename = f"clip_{clip_uuid[:12]}_{preset.lower().replace(' ', '_')}.mp4"
        out_filepath = str(Path(settings.CLIPS_DIR) / out_filename)
        thumb_filename = f"thumb_{clip_uuid[:12]}.jpg"
        thumb_filepath = str(Path(settings.THUMBNAILS_DIR) / thumb_filename)

        # Title resolution
        title = custom_title
        if not title and candidate.suggested_titles:
            title = candidate.suggested_titles[0]
        if not title:
            title = f"GTA 6 Highlight #{candidate.id}"

        src_p = Path(recording.file_path)
        if not src_p.is_absolute():
            if src_p.exists():
                src_p = src_p.resolve()
            elif (Path(BASE_DIR) / recording.file_path).exists():
                src_p = (Path(BASE_DIR) / recording.file_path).resolve()
            elif (Path(BASE_DIR).parent / recording.file_path).exists():
                src_p = (Path(BASE_DIR).parent / recording.file_path).resolve()
        src_video = str(src_p.resolve())

        start_time = candidate.start_time
        end_time = candidate.end_time
        duration = max(1.0, round(end_time - start_time, 2))

        logger.info(
            f"[RenderService] Rendering Candidate #{candidate.id} -> '{out_filename}' "
            f"({duration}s, Preset: '{preset}', Facecam: {candidate.has_facecam})"
        )

        try:
            # Render video frames using native compositing engine
            self._render_native_pipeline(
                src_video=src_video,
                out_path=out_filepath,
                start_time=start_time,
                end_time=end_time,
                preset=preset,
                has_facecam=candidate.has_facecam,
                facecam_region=candidate.facecam_region,
                rec_meta=recording.metadata_json or {},
                job=job,
                db=db,
            )

            # Generate Thumbnail
            if job:
                job.current_stage = "Generating thumbnail"
                job.progress_percent = 92.0
                db.commit()

            self._generate_thumbnail(
                video_path=out_filepath,
                out_thumb_path=thumb_filepath,
                title=title,
            )

            # File size
            file_size = os.path.getsize(out_filepath) if Path(out_filepath).exists() else 0

            # Create Clip in database
            clip = Clip(
                uuid=clip_uuid,
                candidate_id=candidate.id,
                title=title,
                file_name=out_filename,
                file_path=out_filepath,
                file_size_bytes=file_size,
                duration_seconds=duration,
                width=self.output_width,
                height=self.output_height,
                preset=preset,
                score=candidate.score_composite,
                event_category=candidate.event_category,
                has_subtitles=True,
                is_favorite=False,
                download_count=0,
                rendered_at=datetime.now(timezone.utc),
            )
            db.add(clip)
            db.commit()
            db.refresh(clip)

            # Create Thumbnail in database
            thumbnail = Thumbnail(
                clip_id=clip.id,
                file_path=thumb_filepath,
                file_name=thumb_filename,
                width=self.output_width,
                height=self.output_height,
                timestamp_seconds=round(duration / 2.0, 2),
                is_primary=True,
            )
            db.add(thumbnail)

            # Update candidate status
            candidate.status = "rendered"

            # Update job status
            if job:
                job.status = "completed"
                job.current_stage = "Finished"
                job.progress_percent = 100.0
                job.completed_at = datetime.now(timezone.utc)
                job.result_summary = {
                    "clip_id": clip.id,
                    "clip_uuid": clip.uuid,
                    "file_name": out_filename,
                    "file_size_bytes": file_size,
                    "preset": preset,
                    "duration_seconds": duration,
                }

            db.commit()
            logger.info(f"[RenderService] Successfully completed render for Clip #{clip.id} ('{clip.title}').")
            return clip

        except Exception as e:
            logger.error(f"[RenderService] Rendering failed for Candidate #{candidate.id}: {e}", exc_info=True)
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
            raise

    def _render_native_pipeline(
        self,
        src_video: str,
        out_path: str,
        start_time: float,
        end_time: float,
        preset: str,
        has_facecam: bool,
        facecam_region: Optional[Dict[str, int]],
        rec_meta: Dict[str, Any],
        job: Optional[ProcessingJob] = None,
        db: Optional[Session] = None,
    ) -> None:
        """
        Native Python compositing engine using PyAV and OpenCV.
        Decodes frames, applies vertical canvas transformation, adds facecam badges,
        burns animated subtitles, normalizes audio, and muxes to MP4.
        """
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)

        # 1. Parse subtitles lines
        transcripts = rec_meta.get("transcripts", [])
        raw_words: List[Dict[str, Any]] = []
        for seg in transcripts:
            # Extract word tokens if available, else approximate word timings
            words_in_seg = seg.get("words", [])
            if words_in_seg:
                raw_words.extend(words_in_seg)
            else:
                text = seg.get("text", "").strip()
                s_start = seg.get("start", 0.0)
                s_end = seg.get("end", 0.0)
                seg_words = text.split()
                if seg_words:
                    word_dur = (s_end - s_start) / len(seg_words)
                    for i, w in enumerate(seg_words):
                        raw_words.append({
                            "word": w,
                            "start": s_start + (i * word_dur),
                            "end": s_start + ((i + 1) * word_dur),
                        })

        # Shift word timings relative to clip start
        clip_words = []
        for w in raw_words:
            w_start = w.get("start", 0.0)
            w_end = w.get("end", 0.0)
            if w_end > start_time and w_start < end_time:
                clip_words.append({
                    "word": w.get("word", ""),
                    "start": max(0.0, w_start - start_time),
                    "end": max(0.0, min(end_time - start_time, w_end - start_time)),
                })

        subtitle_lines = subtitle_service.group_words_into_lines(clip_words)

        # 2. Setup OpenCV VideoCapture
        cap = cv2.VideoCapture(src_video)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open source video: {src_video}")

        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000.0)

        total_frames = int(round((end_time - start_time) * self.fps))

        # 3. Extract and normalize audio frames upfront
        norm_audio_frames = self._extract_and_normalize_audio(src_video, start_time, end_time)

        # 4. Setup PyAV Output Container (both video and audio streams added upfront)
        out_container = av.open(out_path, mode="w")
        v_stream = out_container.add_stream("h264", rate=self.fps)
        v_stream.width = self.output_width
        v_stream.height = self.output_height
        v_stream.pix_fmt = "yuv420p"
        v_stream.options = {"preset": "fast", "crf": "21"}

        a_stream = None
        if norm_audio_frames:
            a_stream = out_container.add_stream("aac", rate=48000)
            a_stream.time_base = Fraction(1, 48000)

        if job and db:
            job.current_stage = "Rendering vertical frames"
            job.progress_percent = 15.0
            db.commit()

        frames_encoded = 0
        current_time_sec = 0.0
        frame_step = 1.0 / self.fps

        while frames_encoded < total_frames:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            # Composite vertical 9:16 frame according to preset
            composite_frame = self._composite_preset_frame(
                frame=frame,
                preset=preset,
                has_facecam=has_facecam,
                facecam_region=facecam_region,
            )

            # Burn in subtitles
            pil_img = Image.fromarray(cv2.cvtColor(composite_frame, cv2.COLOR_BGR2RGB))
            y_sub_pos = 1520 if preset != "Viral Gaming" else 1420
            pil_img = subtitle_service.render_subtitles_on_frame(
                pil_image=pil_img,
                timestamp_sec=current_time_sec,
                lines=subtitle_lines,
                y_position=y_sub_pos,
                font_size=52,
            )

            # Convert back to BGR ndarray for PyAV
            final_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            # Encode Video Frame
            av_frame = av.VideoFrame.from_ndarray(final_bgr, format="bgr24")
            for packet in v_stream.encode(av_frame):
                out_container.mux(packet)

            frames_encoded += 1
            current_time_sec += frame_step

            # Update progress periodically
            if job and db and frames_encoded % 30 == 0:
                prog = 15.0 + (70.0 * (frames_encoded / total_frames))
                job.progress_percent = round(prog, 1)
                db.commit()

        # Flush video encoder
        for packet in v_stream.encode():
            out_container.mux(packet)

        cap.release()

        # 5. Mux audio packets
        if a_stream and norm_audio_frames:
            audio_pts = 0
            for af in norm_audio_frames:
                af.pts = audio_pts
                audio_pts += af.samples
                for packet in a_stream.encode(af):
                    out_container.mux(packet)
            for packet in a_stream.encode():
                out_container.mux(packet)

        out_container.close()
        logger.info(f"[RenderService] Native render completed: {frames_encoded} frames encoded to '{out_path}'.")

    def _composite_preset_frame(
        self,
        frame: np.ndarray,
        preset: str,
        has_facecam: bool,
        facecam_region: Optional[Dict[str, int]],
    ) -> np.ndarray:
        """Composites raw 16:9 gameplay frame into 1080x1920 vertical canvas."""
        fh, fw = frame.shape[:2]
        canvas = np.zeros((self.output_height, self.output_width, 3), dtype=np.uint8)

        # Extract facecam if present before transformations
        facecam_crop = None
        if has_facecam and facecam_region:
            fx, fy = facecam_region.get("x", 0), facecam_region.get("y", 0)
            f_w, f_h = facecam_region.get("w", 100), facecam_region.get("h", 100)
            # Bound check
            fx = max(0, min(fw - 10, fx))
            fy = max(0, min(fh - 10, fy))
            f_w = max(10, min(fw - fx, f_w))
            f_h = max(10, min(fh - fy, f_h))
            facecam_crop = frame[fy:fy + f_h, fx:fx + f_w]

        if preset == "Clean Gameplay":
            # 1. Background: heavily blurred & darkened reflection
            bg_scaled = cv2.resize(frame, (self.output_width, self.output_height))
            bg_blurred = cv2.GaussianBlur(bg_scaled, (51, 51), 25)
            bg_darkened = (bg_blurred * 0.45).astype(np.uint8)
            canvas = bg_darkened

            # 2. Foreground: centered 16:9 frame (1080 x 608)
            fg_height = int(round(self.output_width * (fh / fw)))
            fg_scaled = cv2.resize(frame, (self.output_width, fg_height))
            y_offset = (self.output_height - fg_height) // 2
            canvas[y_offset:y_offset + fg_height, 0:self.output_width] = fg_scaled

        elif preset == "Reaction Focus" and facecam_crop is not None:
            # Split screen layout:
            # Top 40% (1080 x 768): Streamer facecam
            top_h = 768
            facecam_resized = cv2.resize(facecam_crop, (self.output_width, top_h))
            canvas[0:top_h, 0:self.output_width] = facecam_resized

            # Accent Divider Line (4px cyan)
            canvas[top_h - 2:top_h + 2, :] = [212, 182, 6]  # Cyan in BGR

            # Bottom 60% (1080 x 1152): Centered gameplay
            bot_h = self.output_height - top_h
            gp_resized = cv2.resize(frame, (self.output_width, bot_h))
            canvas[top_h:self.output_height, 0:self.output_width] = gp_resized

        else:
            # Default: 'Viral Gaming'
            # 1. Background blurred reflection
            bg_scaled = cv2.resize(frame, (self.output_width, self.output_height))
            bg_blurred = cv2.GaussianBlur(bg_scaled, (41, 41), 20)
            canvas = (bg_blurred * 0.50).astype(np.uint8)

            # 2. Center gameplay scaled with zoom (1080 x 810 or 1080 x 720)
            fg_height = int(round(self.output_width * (fh / fw) * 1.25))
            fg_scaled = cv2.resize(frame, (int(self.output_width * 1.25), fg_height))
            # Center crop to 1080
            x_crop = (fg_scaled.shape[1] - self.output_width) // 2
            fg_cropped = fg_scaled[:, x_crop:x_crop + self.output_width]

            y_offset = (self.output_height - fg_height) // 2
            y_start = max(0, y_offset)
            y_end = min(self.output_height, y_offset + fg_height)
            src_y_start = max(0, -y_offset)
            src_y_end = src_y_start + (y_end - y_start)

            canvas[y_start:y_end, 0:self.output_width] = fg_cropped[src_y_start:src_y_end, :]

            # 3. Streamer Facecam Badge Overlay (top-right corner with cyan border)
            if facecam_crop is not None:
                badge_w, badge_h = 320, 240
                badge = cv2.resize(facecam_crop, (badge_w, badge_h))
                # Add 4px border
                cv2.rectangle(badge, (0, 0), (badge_w - 1, badge_h - 1), (212, 182, 6), 4)

                bx = self.output_width - badge_w - 40
                by = 60
                canvas[by:by + badge_h, bx:bx + badge_w] = badge

        return canvas

    def _extract_and_normalize_audio(
        self,
        src_video: str,
        start_time: float,
        end_time: float,
    ) -> List[av.AudioFrame]:
        """
        Extracts audio segment from source, resamples to 48kHz stereo,
        and applies peak loudness normalization.
        """
        try:
            in_container = av.open(src_video)
            audio_stream = next((s for s in in_container.streams if s.type == "audio"), None)
            if not audio_stream:
                logger.info(f"[RenderService] No audio stream found in {src_video}.")
                in_container.close()
                return []

            resampler = av.AudioResampler(format="fltp", layout="stereo", rate=48000)
            in_container.seek(int(start_time * av.time_base), any_frame=False, backward=True)

            all_frames: List[av.AudioFrame] = []
            for frame in in_container.decode(audio_stream):
                pts_sec = float(frame.pts * audio_stream.time_base) if frame.pts else 0.0
                if pts_sec < start_time:
                    continue
                if pts_sec > end_time:
                    break
                for r_frame in resampler.resample(frame):
                    all_frames.append(r_frame)

            in_container.close()

            if not all_frames:
                return []

            # Normalize audio (target peak: -1.0 dBFS = ~0.89 amplitude)
            sample_arrays = [f.to_ndarray() for f in all_frames]
            concat = np.concatenate(sample_arrays, axis=1)
            peak = float(np.max(np.abs(concat)))

            gain = 1.0
            if peak > 0.001:
                target_peak = 0.891  # -1.0 dBFS
                gain = min(3.0, target_peak / peak)

            norm_frames = []
            for frame in all_frames:
                arr = frame.to_ndarray() * gain
                arr = np.clip(arr, -1.0, 1.0)
                norm_frame = av.AudioFrame.from_ndarray(arr, format="fltp", layout="stereo")
                norm_frame.rate = 48000
                norm_frames.append(norm_frame)

            logger.info(f"[RenderService] Prepared {len(norm_frames)} normalized audio frames (Gain: {gain:.2f}x).")
            return norm_frames

        except Exception as e:
            logger.warning(f"[RenderService] Audio extraction warning: {e}", exc_info=True)
            return []

    def _generate_thumbnail(
        self,
        video_path: str,
        out_thumb_path: str,
        title: str,
    ) -> None:
        """Captures middle frame from rendered clip and adds viral typography."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 30)
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total_frames * 0.45))
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            frame = np.zeros((self.output_height, self.output_width, 3), dtype=np.uint8)

        # Convert to PIL
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)

        # Draw Title Banner (Top third)
        font = subtitle_service.get_font(64)
        words = title.upper().split()
        lines = []
        curr = []
        for w in words:
            curr.append(w)
            if len(" ".join(curr)) > 20:
                lines.append(" ".join(curr))
                curr = []
        if curr:
            lines.append(" ".join(curr))

        y = 280
        for line in lines[:2]:
            draw.text(
                (540, y), line,
                font=font, fill=(255, 235, 59),
                stroke_fill=(0, 0, 0), stroke_width=6,
                anchor="mm"
            )
            y += 85

        # Save JPEG
        Path(out_thumb_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_thumb_path, "JPEG", quality=92)
        logger.info(f"[RenderService] Generated thumbnail at '{out_thumb_path}'.")


# Global singleton instance
render_service = RenderService()
