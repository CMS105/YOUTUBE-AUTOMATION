"""
Context Evaluation Service.

Evaluates narrative context, gameplay intensity, and viral potential of candidate
clip windows using AI vision-language models (Google Gemini 1.5/2.0 Flash, OpenAI GPT-4o-mini)
with a deterministic local heuristic fallback.

Adapted from visionmate-ai vlm_service.py with GTA 6 gaming domain rules.
"""

import json
import re
from typing import Optional, List, Dict, Any
import httpx

from app.core.config import settings
from app.core.logging import logger

# GTA 6 Domain Category Keywords
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "Police Chase": [
        "cop", "cops", "police", "escape", "pursuit", "helicopter", "heli", "stars",
        "siren", "wanted", "drive", "drift", "speed", "swerve", "cruiser", "roadblock",
        "spike strip", "getaway", "chase", "evade", "patrol"
    ],
    "High Stakes Gunfight": [
        "shoot", "shot", "gun", "sniper", "rpg", "explosive", "grenade", "tank",
        "bullet", "reload", "kill", "fire", "blast", "aim", "headshot", "rifle",
        "cover", "suppress", "heavy", "clutch", "ambush"
    ],
    "Funny Fail / Rage": [
        "no way", "bro", "bruh", "oh my god", "omg", "what", "are you kidding",
        "stop", "dead", "wasted", "fell", "crash", "flying", "rip", "lmao", "lol",
        "crying", "unbelievable", "why", "ridiculous", "glitch", "bug", "ragdoll"
    ],
    "Heist / Mission": [
        "money", "vault", "cash", "bank", "mission", "target", "loot", "bag",
        "score", "plan", "hack", "drill", "alarm", "security", "guard", "take"
    ],
    "Crazy Stunt": [
        "jump", "flip", "landed", "roof", "insane", "physics", "stunt", "ramp",
        "boat", "plane", "jet", "parachute", "cliff", "skyscraper", "trick"
    ],
}

# Catchy title templates by category
TITLE_TEMPLATES: Dict[str, List[str]] = {
    "Police Chase": [
        "BRO OUTSMARTED THE ENTIRE GTA 6 POLICE FORCE 💀",
        "THE MOST INSANE 5-STAR GETAWAY IN GTA 6! 🚨",
        "HE REALLY THOUGHT HE COULD ESCAPE IN GTA 6... 🚓",
        "IMPOSSIBLE POLICE EVASION IN GTA 6! 💨",
    ],
    "High Stakes Gunfight": [
        "HE CLUTCHED THIS IMPOSSIBLE GTA 6 GUNFIGHT! 🔥",
        "1V5 CLUTCH IN GTA 6 GONE COMPLETELY WRONG! 💀",
        "THE MOST CHAOTIC SHOOTOUT IN GTA 6 HISTORY! 💥",
        "BRO TURNED INTO JOHN WICK IN GTA 6 🎯",
    ],
    "Funny Fail / Rage": [
        "BRO DID NOT EXPECT THIS IN GTA 6 💀😭",
        "WORST TIMING IN GTA 6 EVER! 🤣",
        "HE INSTANTLY REGRETTED THIS MOVE IN GTA 6... 😭",
        "THE FUNNIEST INSTANT KARMA IN GTA 6! 💀",
    ],
    "Heist / Mission": [
        "THIS GTA 6 HEIST ESCAPE WAS LEGENDARY! 💰",
        "1000 IQ HEIST GETAWAY IN GTA 6 🧠",
        "THE CLEANEST BANK ROBBERY IN GTA 6 🔥",
        "WHEN THE HEIST PLAN GOES TERRIBLY WRONG IN GTA 6 🚨",
    ],
    "Crazy Stunt": [
        "PHYSICS ENGINE BROKE IN GTA 6! 🤯",
        "IMPOSSIBLE STUNT IN GTA 6! 😱",
        "HOW DID HE SURVIVE THIS IN GTA 6?! 🚁",
        "BRO DEFIED GRAVITY IN GTA 6 🚀",
    ],
    "General Chaos": [
        "UNEXPECTED CHAOS IN GTA 6! 🔥",
        "BRO PULLED OFF THE IMPOSSIBLE IN GTA 6 💀",
        "YOU WON'T BELIEVE WHAT HAPPENED IN GTA 6! 🤯",
        "GTA 6 IS ALREADY PEAK GAMING MOMENT 💀🔥",
    ],
}


class ContextService:
    """
    Evaluates gameplay context and generates viral metadata.
    Supports multi-provider VLM execution with graceful degradation.
    """

    def __init__(self):
        self.provider = settings.active_vlm_provider

    def evaluate_context(
        self,
        transcript: str = "",
        start_time: float = 0.0,
        end_time: float = 0.0,
        peak_audio_intensity: float = 0.0,
        peak_visual_intensity: float = 0.0,
        has_facecam: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluate context, determine event category, compute context score,
        and generate catchy short-form titles.
        """
        # Try active cloud provider if configured
        if self.provider == "gemini" and settings.has_gemini:
            try:
                return self._evaluate_with_gemini(
                    transcript, start_time, end_time,
                    peak_audio_intensity, peak_visual_intensity, has_facecam
                )
            except Exception as e:
                logger.warning(f"[ContextService] Gemini evaluation failed: {e}. Falling back to local heuristic.")

        elif self.provider == "openai" and settings.has_openai:
            try:
                return self._evaluate_with_openai(
                    transcript, start_time, end_time,
                    peak_audio_intensity, peak_visual_intensity, has_facecam
                )
            except Exception as e:
                logger.warning(f"[ContextService] OpenAI evaluation failed: {e}. Falling back to local heuristic.")

        # Local deterministic heuristic engine (offline, fast, zero-cost)
        return self._evaluate_local_heuristic(
            transcript, start_time, end_time,
            peak_audio_intensity, peak_visual_intensity, has_facecam
        )

    def _evaluate_local_heuristic(
        self,
        transcript: str,
        start_time: float,
        end_time: float,
        peak_audio_intensity: float,
        peak_visual_intensity: float,
        has_facecam: bool,
    ) -> Dict[str, Any]:
        """Deterministic local heuristic context analyzer."""
        transcript_clean = transcript.lower() if transcript else ""
        category_scores: Dict[str, float] = {}

        # Keyword matching across categories
        for category, keywords in CATEGORY_KEYWORDS.items():
            matches = sum(1 for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", transcript_clean))
            category_scores[category] = matches

        # Pick best category
        best_category = "General Chaos"
        max_matches = 0
        for category, score in category_scores.items():
            if score > max_matches:
                max_matches = score
                best_category = category

        # Compute heuristic context score [0.30 - 0.95]
        base_score = 0.40
        keyword_bonus = min(0.30, max_matches * 0.08)
        audio_boost = min(0.15, peak_audio_intensity * 0.15)
        visual_boost = min(0.10, peak_visual_intensity * 0.10)
        facecam_bonus = 0.05 if has_facecam else 0.0

        context_score = round(min(0.98, max(0.25, base_score + keyword_bonus + audio_boost + visual_boost + facecam_bonus)), 3)

        # Select titles
        titles = TITLE_TEMPLATES.get(best_category, TITLE_TEMPLATES["General Chaos"])

        # Summary
        summary = (
            f"GTA 6 {best_category.lower()} clip featuring peak gameplay action "
            f"from {start_time:.1f}s to {end_time:.1f}s."
        )
        if transcript_clean:
            snippet = transcript[:80].strip()
            summary += f' Streamer quote: "{snippet}..."'

        return {
            "context_score": context_score,
            "event_category": best_category,
            "suggested_titles": titles[:4],
            "summary": summary,
            "provider_used": "local_heuristic",
        }

    def _evaluate_with_gemini(
        self,
        transcript: str,
        start_time: float,
        end_time: float,
        peak_audio_intensity: float,
        peak_visual_intensity: float,
        has_facecam: bool,
    ) -> Dict[str, Any]:
        """Evaluate context using Google Gemini 1.5/2.0 Flash."""
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = self._build_prompt(
            transcript, start_time, end_time,
            peak_audio_intensity, peak_visual_intensity, has_facecam
        )

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )

        return self._parse_ai_json_response(response.text, "gemini")

    def _evaluate_with_openai(
        self,
        transcript: str,
        start_time: float,
        end_time: float,
        peak_audio_intensity: float,
        peak_visual_intensity: float,
        has_facecam: bool,
    ) -> Dict[str, Any]:
        """Evaluate context using OpenAI GPT-4o-mini REST API."""
        prompt = self._build_prompt(
            transcript, start_time, end_time,
            peak_audio_intensity, peak_visual_intensity, has_facecam
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional social media video editor specializing in viral GTA 6 YouTube Shorts and TikTok gaming clips.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=8.0) as client:
            resp = client.post(
                f"{settings.OPENAI_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_ai_json_response(content, "openai")

    def _build_prompt(
        self,
        transcript: str,
        start_time: float,
        end_time: float,
        peak_audio_intensity: float,
        peak_visual_intensity: float,
        has_facecam: bool,
    ) -> str:
        """Constructs structured JSON evaluation prompt for LLM/VLM."""
        return f"""
Analyze this candidate GTA 6 highlight clip:
- Duration: {start_time:.1f}s to {end_time:.1f}s (Total: {end_time - start_time:.1f}s)
- Audio Peak Intensity: {peak_audio_intensity:.2f} (0.0 to 1.0)
- Visual Motion Intensity: {peak_visual_intensity:.2f} (0.0 to 1.0)
- Streamer Facecam Active: {has_facecam}
- Speech Transcript: "{transcript or 'No dialogue detected'}"

Return a strict JSON object with these exact keys:
{{
    "context_score": <float between 0.0 and 1.0 representing viral entertainment potential>,
    "event_category": <one of: "Police Chase", "High Stakes Gunfight", "Funny Fail / Rage", "Heist / Mission", "Crazy Stunt", "General Chaos">,
    "suggested_titles": [<array of 4 ultra-catchy viral YouTube Shorts / TikTok titles with emojis and caps>],
    "summary": <concise 1-2 sentence description of the highlight>
}}
"""

    def _parse_ai_json_response(self, text: str, provider: str) -> Dict[str, Any]:
        """Safely extracts JSON from model text response."""
        # Find json content
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON block found in {provider} response")

        data = json.loads(match.group(0))
        score = float(data.get("context_score", 0.70))
        score = max(0.1, min(1.0, score))

        category = str(data.get("event_category", "General Chaos"))
        titles = list(data.get("suggested_titles", []))
        if not titles:
            titles = TITLE_TEMPLATES.get(category, TITLE_TEMPLATES["General Chaos"])

        summary = str(data.get("summary", "GTA 6 highlight clip."))

        return {
            "context_score": round(score, 3),
            "event_category": category,
            "suggested_titles": titles[:4],
            "summary": summary,
            "provider_used": provider,
        }


# Global singleton instance
context_service = ContextService()
