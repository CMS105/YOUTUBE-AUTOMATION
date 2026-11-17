"""
Speech-to-Text Service:
Powered by Faster-Whisper with CUDA/CPU optimization and word-level timestamps.
Adapted from visionmate-ai stt_service.py with PyAV >= 14 patch and subtitle data models.
"""

import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import torch
import av
from faster_whisper import WhisperModel

from app.core.config import settings
from app.core.logging import logger

# Fix PyAV >= 14 / faster-whisper compatibility: remove unsupported 'metadata_errors'
_orig_av_open = av.open


def _safe_av_open(*args, **kwargs):
    kwargs.pop("metadata_errors", None)
    return _orig_av_open(*args, **kwargs)


av.open = _safe_av_open


class WordTimestamp:
    def __init__(self, word: str, start: float, end: float, probability: float):
        self.word = word.strip()
        self.start = start
        self.end = end
        self.probability = probability

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "probability": round(self.probability, 3),
        }


class TranscriptionSegment:
    def __init__(self, text: str, start: float, end: float, words: List[WordTimestamp]):
        self.text = text.strip()
        self.start = start
        self.end = end
        self.words = words

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "words": [w.to_dict() for w in self.words],
        }


class STTService:
    """Lazy-loaded Faster-Whisper service optimized for GPU float16 with CPU int8 fallback."""

    def __init__(self):
        self._model: Optional[WhisperModel] = None
        self._lock = threading.Lock()
        self._model_size = settings.WHISPER_MODEL_SIZE
        self._is_loaded = False
        self._device = "cpu"
        self._compute_type = "int8"

    def get_status(self) -> dict:
        return {
            "loaded": self._is_loaded,
            "model_size": self._model_size,
            "device": self._device,
            "compute_type": self._compute_type,
        }

    def _determine_device_and_compute(self) -> Tuple[str, str]:
        if settings.WHISPER_DEVICE.lower() == "cpu":
            return "cpu", "int8"
        if torch.cuda.is_available() and settings.has_cuda:
            return "cuda", settings.WHISPER_COMPUTE_TYPE
        return "cpu", "int8"

    def _load_model(self):
        with self._lock:
            if self._model is not None:
                return
            dev, comp = self._determine_device_and_compute()
            whisper_root = str(Path(settings.DATA_DIR) / "models" / "whisper")
            Path(whisper_root).mkdir(parents=True, exist_ok=True)
            try:
                logger.info(f"[STTService] Loading Faster-Whisper ({self._model_size}) on {dev} ({comp})...")
                self._model = WhisperModel(
                    self._model_size,
                    device=dev,
                    compute_type=comp,
                    download_root=whisper_root,
                )
                self._device = dev
                self._compute_type = comp
                self._is_loaded = True
                logger.info("[STTService] Faster-Whisper loaded on GPU.")
            except Exception as e:
                logger.warning(f"[STTService] Failed loading on {dev} ({e}). Falling back to CPU...")
                self._device = "cpu"
                self._compute_type = "int8"
                self._model = WhisperModel(
                    self._model_size,
                    device="cpu",
                    compute_type="int8",
                    download_root=whisper_root,
                )
                self._is_loaded = True
                logger.info("[STTService] Faster-Whisper loaded on CPU fallback.")

    def transcribe(
        self, audio_source: str, word_timestamps: bool = True
    ) -> Tuple[str, List[TranscriptionSegment]]:
        """
        Transcribes audio/video file and returns (full_text, segments_with_word_timestamps).
        """
        self._load_model()
        assert self._model is not None

        segments_out: List[TranscriptionSegment] = []
        full_text_parts: List[str] = []

        try:
            segments, info = self._model.transcribe(
                audio_source,
                word_timestamps=word_timestamps,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            for s in segments:
                words_list: List[WordTimestamp] = []
                if s.words:
                    for w in s.words:
                        words_list.append(
                            WordTimestamp(
                                word=w.word,
                                start=w.start,
                                end=w.end,
                                probability=w.probability,
                            )
                        )
                seg_obj = TranscriptionSegment(
                    text=s.text,
                    start=s.start,
                    end=s.end,
                    words=words_list,
                )
                segments_out.append(seg_obj)
                full_text_parts.append(s.text.strip())

            full_text = " ".join(full_text_parts)
            return full_text, segments_out
        except Exception as e:
            logger.error(f"[STTService] Transcription error: {e}")
            return "", []


stt_service = STTService()
