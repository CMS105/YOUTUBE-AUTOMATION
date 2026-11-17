"""
Subtitle Generation & Text Rendering Service.

Generates Advanced SubStation Alpha (ASS) and SubRip (SRT) subtitle files
with word-by-word karaoke highlighting for TikTok / YouTube Shorts.
Also provides a frame-level subtitle renderer using PIL.
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.core.logging import logger


class SubtitleService:
    """
    Handles subtitle generation, word-level timing synchronization,
    ASS script creation, and direct frame burn-in.
    """

    def __init__(self):
        # Default font fallbacks on Windows
        self.font_candidates = [
            "C:\\Windows\\Fonts\\impact.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\segoeui.ttf",
        ]
        self._font_path = self._resolve_font()

    def _resolve_font(self) -> Optional[str]:
        for fp in self.font_candidates:
            if Path(fp).exists():
                return fp
        return None

    def get_font(self, size: int = 56) -> ImageFont.ImageFont:
        if self._font_path:
            try:
                return ImageFont.truetype(self._font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def format_ass_time(self, seconds: float) -> str:
        """Converts seconds float to ASS time format: H:MM:SS.cc"""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centis = int(round((seconds - int(seconds)) * 100))
        if centis >= 100:
            centis = 99
        return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"

    def format_srt_time(self, seconds: float) -> str:
        """Converts seconds float to SRT time format: HH:MM:SS,mmm"""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis >= 1000:
            millis = 999
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    def group_words_into_lines(
        self,
        words: List[Dict[str, Any]],
        max_words_per_line: int = 4,
        max_chars_per_line: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Groups word tokens into short, punchy 3-5 word lines optimal for vertical video.
        Each line dict contains: {'text': str, 'start': float, 'end': float, 'words': [...]}
        """
        if not words:
            return []

        lines: List[Dict[str, Any]] = []
        current_words: List[Dict[str, Any]] = []
        current_chars = 0

        for w in words:
            text = w.get("word", "").strip()
            if not text:
                continue

            word_len = len(text)
            if (
                len(current_words) >= max_words_per_line
                or (current_chars + word_len + 1) > max_chars_per_line
            ):
                if current_words:
                    line_start = current_words[0]["start"]
                    line_end = current_words[-1]["end"]
                    lines.append({
                        "text": " ".join(cw["word"].strip() for cw in current_words),
                        "start": line_start,
                        "end": max(line_start + 0.5, line_end),
                        "words": list(current_words),
                    })
                current_words = [w]
                current_chars = word_len
            else:
                current_words.append(w)
                current_chars += word_len + 1

        if current_words:
            line_start = current_words[0]["start"]
            line_end = current_words[-1]["end"]
            lines.append({
                "text": " ".join(cw["word"].strip() for cw in current_words),
                "start": line_start,
                "end": max(line_start + 0.5, line_end),
                "words": list(current_words),
            })

        return lines

    def generate_ass_script(
        self,
        words: List[Dict[str, Any]],
        clip_start: float = 0.0,
        clip_end: float = 60.0,
        output_path: Optional[str] = None,
        font_size: int = 48,
        active_color: str = "&H00FFFF&",    # Yellow in BGR &H00BBGGRR&
        inactive_color: str = "&HFFFFFF&",  # White
        outline_color: str = "&H000000&",   # Black
    ) -> str:
        """
        Generates dynamic ASS subtitle content with karaoke word highlighting.
        Times are shifted relative to clip_start.
        """
        # Filter words within clip boundaries
        clip_words = []
        for w in words:
            w_start = w.get("start", 0.0)
            w_end = w.get("end", 0.0)
            if w_end > clip_start and w_start < clip_end:
                shifted_word = dict(w)
                shifted_word["start"] = max(0.0, w_start - clip_start)
                shifted_word["end"] = max(0.0, min(clip_end - clip_start, w_end - clip_start))
                clip_words.append(shifted_word)

        lines = self.group_words_into_lines(clip_words)

        ass_header = f"""[Script Info]
Title: GTA 6 AI Clip Factory Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,{font_size},{inactive_color},&H000000FF&,{outline_color},&H80000000&,-1,0,0,0,100,100,1,0,1,5,2,2,40,40,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for line in lines:
            line_start = self.format_ass_time(line["start"])
            line_end = self.format_ass_time(line["end"])

            # Build karaoke style word tokens
            karaoke_text = ""
            for w in line["words"]:
                duration_centis = int(round((w["end"] - w["start"]) * 100))
                duration_centis = max(10, duration_centis)
                word_clean = w["word"].strip().upper()
                karaoke_text += f"{{\\k{duration_centis}}}{word_clean} "

            events.append(f"Dialogue: 0,{line_start},{line_end},Default,,0,0,0,,{karaoke_text.strip()}")

        content = ass_header + "\n".join(events) + "\n"

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

        return content

    def render_subtitles_on_frame(
        self,
        pil_image: Image.Image,
        timestamp_sec: float,
        lines: List[Dict[str, Any]],
        y_position: int = 1520,
        font_size: int = 54,
    ) -> Image.Image:
        """
        Renders dynamic highlighted subtitle line directly onto a PIL frame.
        Used for native Python video composition.
        """
        # Find active line at this timestamp
        active_line = None
        for line in lines:
            if line["start"] <= timestamp_sec <= line["end"]:
                active_line = line
                break

        if not active_line:
            return pil_image

        draw = ImageDraw.Draw(pil_image)
        font = self.get_font(font_size)

        words = active_line.get("words", [])
        if not words:
            # Fallback to plain line text
            text = active_line.get("text", "").upper()
            draw.text(
                (540, y_position), text,
                font=font, fill=(255, 255, 255),
                stroke_fill=(0, 0, 0), stroke_width=5,
                anchor="mm"
            )
            return pil_image

        # Measure widths of words to compute total line width
        word_items = []
        total_width = 0
        space_width = draw.textlength(" ", font=font)

        for w in words:
            w_text = w.get("word", "").strip().upper()
            w_width = draw.textlength(w_text, font=font)
            is_active = w.get("start", 0.0) <= timestamp_sec <= w.get("end", 0.0)
            word_items.append((w_text, w_width, is_active))
            total_width += w_width + space_width

        if word_items:
            total_width -= space_width

        # Start x centered at 540
        start_x = 540 - (total_width / 2.0)
        curr_x = start_x

        for w_text, w_width, is_active in word_items:
            # Active word: bright vibrant yellow (255, 235, 59), inactive: crisp white (255, 255, 255)
            color = (255, 235, 59) if is_active else (255, 255, 255)
            stroke_width = 6 if is_active else 4

            draw.text(
                (curr_x, y_position),
                w_text,
                font=font,
                fill=color,
                stroke_fill=(0, 0, 0),
                stroke_width=stroke_width,
            )
            curr_x += w_width + space_width

        return pil_image


# Global singleton instance
subtitle_service = SubtitleService()
