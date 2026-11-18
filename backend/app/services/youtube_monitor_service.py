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
import random
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models import (
    Streamer, Stream, AuditLog,
    LiveDiscovery, CreatorAuthorization, Permission
)

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

    def get_creator_auth_status(self, db: Session, channel_id: str) -> str:
        """
        Determines if a creator has granted recording permission.
        Checks both CreatorAuthorization and Streamer/Permission models.
        Returns: 'AUTHORIZED', 'REVOKED', or 'AWAITING_AUTHORIZATION'
        """
        # 1. Check CreatorAuthorization
        auth = (
            db.query(CreatorAuthorization)
            .filter(CreatorAuthorization.channel_id == channel_id)
            .first()
        )
        if auth:
            if auth.status == "ACTIVE":
                return "AUTHORIZED"
            if auth.status == "REVOKED":
                return "REVOKED"

        # 2. Check registered Streamers + Permissions
        streamer = db.query(Streamer).filter(Streamer.channel_id == channel_id).first()
        if streamer:
            active_perm = (
                db.query(Permission)
                .filter(Permission.streamer_id == streamer.id, Permission.status == "ACTIVE")
                .first()
            )
            if active_perm:
                return "AUTHORIZED"
            revoked_perm = (
                db.query(Permission)
                .filter(Permission.streamer_id == streamer.id, Permission.status == "REVOKED")
                .first()
            )
            if revoked_perm:
                return "REVOKED"

        return "AWAITING_AUTHORIZATION"

    def discover_gta6_livestreams(
        self,
        db: Session,
        query: Optional[str] = None,
        max_results: int = 15,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Searches public YouTube broadcasts for active GTA 6 livestreams.
        Strictly compliant with official YouTube Data API v3 (search.list).
        Stores or updates LiveDiscovery records and syncs authorization states.
        Costs 100 quota units.
        """
        search_query = query or random.choice(settings.discovery_keywords_list or ["GTA 6 live"])

        if not self.api_key:
            logger.info("[YouTubeMonitor] YouTube API key not configured. Discovery unavailable.")
            return {
                "success": False,
                "error": "YouTube API key not configured.",
                "items_discovered": 0,
                "new_discoveries": 0,
                "query_used": search_query,
                "quota_status": self.quota_tracker.get_status(),
            }

        if not self.quota_tracker.consume(100):
            return {
                "success": False,
                "error": "Daily YouTube API quota limit reached.",
                "items_discovered": 0,
                "new_discoveries": 0,
                "query_used": search_query,
                "quota_status": self.quota_tracker.get_status(),
            }

        try:
            params = {
                "part": "snippet",
                "q": search_query,
                "eventType": "live",
                "type": "video",
                "maxResults": min(max(max_results, 1), 50),
                "key": self.api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{YOUTUBE_API_BASE}/search", params=params)
                resp.raise_for_status()
                data = resp.json()

            items = data.get("items", [])
            next_page = data.get("nextPageToken")
            new_count = 0
            updated_count = 0

            for item in items:
                video_id = item.get("id", {}).get("videoId")
                if not video_id:
                    continue

                snippet = item.get("snippet", {})
                channel_id = snippet.get("channelId", "")
                channel_title = snippet.get("channelTitle", "Unknown Creator")
                title = snippet.get("title", "GTA 6 Gameplay")
                thumbs = snippet.get("thumbnails", {})
                thumb_url = (
                    thumbs.get("high", {}).get("url")
                    or thumbs.get("medium", {}).get("url")
                    or thumbs.get("default", {}).get("url")
                )
                stream_url = f"https://www.youtube.com/watch?v={video_id}"

                auth_status = self.get_creator_auth_status(db, channel_id)

                existing = (
                    db.query(LiveDiscovery)
                    .filter(LiveDiscovery.video_id == video_id)
                    .first()
                )

                if existing:
                    existing.title = title
                    existing.thumbnail_url = thumb_url
                    existing.live_status = "live"
                    existing.authorization_status = auth_status
                    existing.updated_at = datetime.now(timezone.utc)
                    updated_count += 1
                else:
                    new_discovery = LiveDiscovery(
                        video_id=video_id,
                        channel_id=channel_id,
                        channel_title=channel_title,
                        title=title,
                        thumbnail_url=thumb_url,
                        stream_url=stream_url,
                        live_status="live",
                        authorization_status=auth_status,
                        recording_status="IDLE",
                        metadata_json={
                            "query": search_query,
                            "published_at": snippet.get("publishedAt"),
                        },
                    )
                    db.add(new_discovery)
                    new_count += 1

            if new_count > 0:
                db.add(
                    AuditLog(
                        entity_type="live_discovery",
                        entity_id=None,
                        action="global_discovery",
                        details=f"Discovered {new_count} new GTA 6 livestreams with query '{search_query}'.",
                    )
                )

            db.commit()
            logger.info(
                f"[YouTubeMonitor] Discovery query '{search_query}' completed: "
                f"{len(items)} items returned, {new_count} new, {updated_count} updated."
            )

            return {
                "success": True,
                "error": None,
                "query_used": search_query,
                "items_discovered": len(items),
                "new_discoveries": new_count,
                "updated_discoveries": updated_count,
                "next_page_token": next_page,
                "quota_status": self.quota_tracker.get_status(),
            }

        except Exception as e:
            logger.warning(f"[YouTubeMonitor] Discovery search failed for '{search_query}': {e}")
            return {
                "success": False,
                "error": str(e),
                "query_used": search_query,
                "items_discovered": 0,
                "new_discoveries": 0,
                "quota_status": self.quota_tracker.get_status(),
            }

    def verify_active_discoveries_status(self, db: Session) -> Dict[str, Any]:
        """
        Polls active LiveDiscovery items to verify if they are still streaming live.
        Uses YouTube Data API 'videos.list' (which costs only 1 quota unit for 50 IDs).
        Updates stream status to 'ended' when broadcast ends.
        """
        if not self.api_key:
            return {"checked": 0, "ended": 0}

        active_streams = (
            db.query(LiveDiscovery)
            .filter(LiveDiscovery.live_status == "live")
            .limit(50)
            .all()
        )

        if not active_streams:
            return {"checked": 0, "ended": 0}

        if not self.quota_tracker.consume(1):
            return {"checked": 0, "ended": 0, "error": "Quota limit reached"}

        video_ids = [s.video_id for s in active_streams]
        id_str = ",".join(video_ids)

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{YOUTUBE_API_BASE}/videos",
                    params={
                        "part": "snippet,liveStreamingDetails",
                        "id": id_str,
                        "key": self.api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            returned_items = {item["id"]: item for item in data.get("items", [])}
            ended_count = 0

            for stream in active_streams:
                if stream.video_id not in returned_items:
                    # Video is deleted, privated, or ended
                    stream.live_status = "ended"
                    ended_count += 1
                else:
                    snippet = returned_items[stream.video_id].get("snippet", {})
                    live_content = snippet.get("liveBroadcastContent", "none")
                    if live_content == "none":
                        stream.live_status = "ended"
                        ended_count += 1

            if ended_count > 0:
                db.commit()
                logger.info(f"[YouTubeMonitor] Live stream verification: {ended_count} streams marked as ENDED.")

            return {
                "checked": len(active_streams),
                "ended": ended_count,
                "quota_status": self.quota_tracker.get_status(),
            }

        except Exception as e:
            logger.warning(f"[YouTubeMonitor] Failed to verify active discoveries: {e}")
            return {"checked": len(active_streams), "ended": 0, "error": str(e)}


# Global singleton instance
youtube_monitor_service = YouTubeMonitorService()
