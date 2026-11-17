"""
Official YouTube Data API v3 Monitoring Service.

Discovers channels, checks live broadcast status, retrieves stream metadata,
manages API quotas, and updates stream records in the database.

STRICT POLICY COMPLIANCE:
- Official YouTube Data API v3 endpoints only.
- ZERO video stream scraping, extraction, or DRM bypass.
- Live status detection is strictly decoupled from media ingestion.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models import Streamer, Stream, AuditLog

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeQuotaTracker:
    """Tracks daily YouTube Data API quota consumption (default 10,000 units/day)."""

    def __init__(self, daily_limit: int = 10000):
        self.daily_limit = daily_limit
        self.used_units = 0
        self.last_reset = datetime.now(timezone.utc).date()

    def _check_day_rollover(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self.last_reset:
            self.used_units = 0
            self.last_reset = today

    def consume(self, units: int) -> bool:
        self._check_day_rollover()
        if self.used_units + units > self.daily_limit:
            logger.warning(
                f"[YouTubeQuota] Quota limit reached ({self.used_units}/{self.daily_limit}). "
                f"Suppression active until midnight UTC."
            )
            return False
        self.used_units += units
        return True

    def get_status(self) -> Dict[str, Any]:
        self._check_day_rollover()
        return {
            "used_units": self.used_units,
            "daily_limit": self.daily_limit,
            "remaining_units": max(0, self.daily_limit - self.used_units),
            "percentage_used": round((self.used_units / self.daily_limit) * 100, 2),
            "last_reset": str(self.last_reset),
        }


class YouTubeMonitorService:
    """
    Monitors registered GTA 6 streamers via official YouTube Data API v3.
    """

    def __init__(self):
        self.quota_tracker = YouTubeQuotaTracker()

    @property
    def api_key(self) -> Optional[str]:
        return settings.YOUTUBE_API_KEY if settings.has_youtube_api else None

    def verify_api_key(self, key_to_test: Optional[str] = None) -> Dict[str, Any]:
        """
        Tests an API key against YouTube Data API v3 using a lightweight 1-quota request.
        """
        test_key = key_to_test or self.api_key
        if not test_key:
            return {
                "valid": False,
                "error": "No YouTube API key provided or configured.",
                "status": "missing_credentials",
            }

        try:
            # Test key by querying a known public channel (Google Developers)
            with httpx.Client(timeout=6.0) as client:
                resp = client.get(
                    f"{YOUTUBE_API_BASE}/channels",
                    params={
                        "part": "id",
                        "id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
                        "key": test_key,
                    },
                )
                if resp.status_code == 200:
                    self.quota_tracker.consume(1)
                    return {
                        "valid": True,
                        "error": None,
                        "status": "connected",
                        "quota_cost": 1,
                    }
                else:
                    err_json = resp.json().get("error", {})
                    message = err_json.get("message", f"HTTP {resp.status_code}")
                    return {
                        "valid": False,
                        "error": message,
                        "status": "invalid_credentials",
                    }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Connection error: {str(e)}",
                "status": "network_error",
            }

    def fetch_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves official channel metadata (avatar, title, sub count).
        Costs 1 quota unit.
        """
        if not self.api_key:
            logger.info("[YouTubeMonitor] YouTube API key not configured. Cannot query channel info.")
            return None

        if not self.quota_tracker.consume(1):
            return None

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{YOUTUBE_API_BASE}/channels",
                    params={
                        "part": "snippet,statistics",
                        "id": channel_id,
                        "key": self.api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    return None

                item = items[0]
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})

                return {
                    "channel_id": channel_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "avatar_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                    "subscriber_count": int(stats.get("subscriberCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                }
        except Exception as e:
            logger.warning(f"[YouTubeMonitor] Failed to fetch channel info for '{channel_id}': {e}")
            return None

    def check_channel_live_status(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Queries official YouTube search.list API for active live broadcasts.
        Costs 100 quota units.
        """
        if not self.api_key:
            return None

        if not self.quota_tracker.consume(100):
            return None

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{YOUTUBE_API_BASE}/search",
                    params={
                        "part": "snippet",
                        "channelId": channel_id,
                        "eventType": "live",
                        "type": "video",
                        "key": self.api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    return None

                live_item = items[0]
                video_id = live_item.get("id", {}).get("videoId")
                snippet = live_item.get("snippet", {})

                return {
                    "platform_video_id": video_id,
                    "title": snippet.get("title", "GTA 6 Live Stream"),
                    "published_at": snippet.get("publishedAt"),
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "status": "live",
                }
        except Exception as e:
            logger.warning(f"[YouTubeMonitor] Live check failed for channel '{channel_id}': {e}")
            return None

    def poll_streamers(self, db: Session) -> Dict[str, Any]:
        """
        Polls active registered streamers in database to detect new live streams.
        Updates 'streams' table and logs audit events.
        """
        streamers = (
            db.query(Streamer)
            .filter(Streamer.is_active == True, Streamer.channel_id.isnot(None))
            .all()
        )

        checked_count = 0
        live_detected = 0

        for st in streamers:
            checked_count += 1
            live_data = self.check_channel_live_status(st.channel_id)

            if live_data:
                video_id = live_data["platform_video_id"]
                # Check if this stream is already recorded
                existing_stream = (
                    db.query(Stream)
                    .filter(Stream.streamer_id == st.id, Stream.platform_video_id == video_id)
                    .first()
                )

                if not existing_stream:
                    # New live stream detected
                    new_stream = Stream(
                        streamer_id=st.id,
                        platform_video_id=video_id,
                        title=live_data["title"],
                        status="live",
                        started_at=datetime.now(timezone.utc),
                        thumbnail_url=live_data["thumbnail_url"],
                        category="Grand Theft Auto VI",
                    )
                    db.add(new_stream)
                    db.add(
                        AuditLog(
                            entity_type="stream",
                            entity_id=None,
                            action="live_detected",
                            details=f"Streamer '{st.display_name}' went LIVE on YouTube: '{live_data['title']}'.",
                        )
                    )
                    db.commit()
                    live_detected += 1
                    logger.info(f"[YouTubeMonitor] Streamer '{st.display_name}' is LIVE: {live_data['title']}")
                else:
                    if existing_stream.status != "live":
                        existing_stream.status = "live"
                        db.commit()

        return {
            "streamers_checked": checked_count,
            "live_streams_detected": live_detected,
            "quota_status": self.quota_tracker.get_status(),
        }


# Global singleton instance
youtube_monitor_service = YouTubeMonitorService()
