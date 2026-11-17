"""
Audio Analysis Service:
Extracts RMS loudness curves, detects vocal excitement bursts (screams, laughter),
and identifies peak audio moments for candidate clip generation.
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np
import av

from app.core.logging import logger


class AudioEvent:
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


class AudioAnalysisService:
    @staticmethod
    def extract_audio_samples(file_path: Path, target_sample_rate: int = 16000) -> Tuple[np.ndarray, int]:
        """
        Decodes audio stream from MP4/MKV video into a mono 16kHz float32 numpy array using PyAV.
        """
        samples_list = []
        try:
            with av.open(str(file_path)) as container:
                audio_streams = [s for s in container.streams if s.type == "audio"]
                if not audio_streams:
                    logger.warning(f"No audio stream found in {file_path.name}")
                    return np.zeros(0, dtype=np.float32), target_sample_rate

                resampler = av.AudioResampler(
                    format="fltp",
                    layout="mono",
                    rate=target_sample_rate,
                )

                for frame in container.decode(audio_streams[0]):
                    resampled_frames = resampler.resample(frame)
                    for r_frame in resampled_frames:
                        # Extract mono channel as float32 array
                        plane = r_frame.planes[0]
                        arr = np.frombuffer(plane, dtype=np.float32)
                        samples_list.append(arr)

            if samples_list:
                full_audio = np.concatenate(samples_list)
                return full_audio, target_sample_rate
            return np.zeros(0, dtype=np.float32), target_sample_rate
        except Exception as e:
            logger.warning(f"[AudioAnalysis] PyAV decode failed ({e}), returning zero audio.")
            return np.zeros(0, dtype=np.float32), target_sample_rate

    @classmethod
    def compute_rms_energy_curve(
        cls, audio: np.ndarray, sample_rate: int, window_ms: int = 500
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes the Root-Mean-Square (RMS) energy curve across the audio signal in discrete windows.
        Returns: (timestamps_seconds, rms_values)
        """
        if len(audio) == 0:
            return np.zeros(0), np.zeros(0)

        window_size = int((window_ms / 1000.0) * sample_rate)
        if window_size <= 0:
            window_size = 1024

        num_windows = len(audio) // window_size
        if num_windows == 0:
            return np.array([0.0]), np.array([np.sqrt(np.mean(audio ** 2))])

        # Reshape into chunks and compute RMS per window
        truncated_audio = audio[: num_windows * window_size]
        chunks = truncated_audio.reshape(num_windows, window_size)
        rms = np.sqrt(np.mean(chunks ** 2, axis=1))

        # Normalize RMS into [0.0, 100.0]
        max_rms = np.max(rms) if np.max(rms) > 0 else 1.0
        rms_norm = (rms / max_rms) * 100.0

        timestamps = (np.arange(num_windows) * window_size) / float(sample_rate)
        return timestamps, rms_norm

    @classmethod
    def detect_excitement_events(
        cls, timestamps: np.ndarray, rms_norm: np.ndarray, threshold_sigma: float = 2.0
    ) -> List[AudioEvent]:
        """
        Detects significant vocal reaction spikes (screams, laughter, shock) where
        loudness exceeds threshold_sigma standard deviations above baseline median.
        """
        if len(rms_norm) == 0:
            return []

        baseline_median = float(np.median(rms_norm))
        baseline_std = float(np.std(rms_norm))
        trigger_threshold = baseline_median + (threshold_sigma * baseline_std)
        trigger_threshold = max(25.0, trigger_threshold)  # Minimum threshold floor

        events: List[AudioEvent] = []
        in_event = False
        start_idx = 0

        for i, val in enumerate(rms_norm):
            if val >= trigger_threshold and not in_event:
                in_event = True
                start_idx = i
            elif val < trigger_threshold and in_event:
                in_event = False
                end_idx = i
                # Event duration in seconds
                duration = timestamps[end_idx] - timestamps[start_idx]
                if duration >= 1.0:  # Minimum 1 second spike
                    chunk_vals = rms_norm[start_idx:end_idx]
                    peak_idx = start_idx + int(np.argmax(chunk_vals))
                    events.append(
                        AudioEvent(
                            event_type="vocal_spike",
                            start_time=float(timestamps[start_idx]),
                            end_time=float(timestamps[end_idx]),
                            intensity=float(np.max(chunk_vals)),
                            peak_time=float(timestamps[peak_idx]),
                        )
                    )

        # Handle event open at the end
        if in_event and (len(timestamps) - 1 - start_idx) > 2:
            chunk_vals = rms_norm[start_idx:]
            events.append(
                AudioEvent(
                    event_type="vocal_spike",
                    start_time=float(timestamps[start_idx]),
                    end_time=float(timestamps[-1]),
                    intensity=float(np.max(chunk_vals)),
                    peak_time=float(timestamps[start_idx + int(np.argmax(chunk_vals))]),
                )
            )

        logger.info(f"[AudioAnalysis] Detected {len(events)} vocal excitement events.")
        return events


audio_analysis_service = AudioAnalysisService()
