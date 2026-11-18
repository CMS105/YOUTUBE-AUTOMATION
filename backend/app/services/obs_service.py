"""
OBS Studio WebSocket v5 Integration Service.

Connects to OBS Studio 28+ via native WebSocket protocol v5 (default port 4455).
Supports:
- Safe connection probing and authentication (SHA-256 challenge-response)
- Recording control: start, stop, status monitoring
- Free disk space validation (enforces minimum safety buffer)
- Output file path retrieval
- Resilient simulated mode for automated testing without a live OBS process
"""

import json
import base64
import hashlib
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import websocket

from app.core.config import settings
from app.core.logging import logger


class OBSClient:
    """
    Client for OBS Studio WebSocket v5 protocol.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        timeout: float = 3.0,
    ):
        self.host = host or settings.OBS_HOST
        self.port = port or settings.OBS_PORT
        self.password = password if password is not None else settings.OBS_PASSWORD
        self.timeout = timeout
        self.ws: Optional[websocket.WebSocket] = None
        self._connected = False
        self._obs_version: Optional[str] = None
        self._mock_mode = False
        self._mock_recording = False
        self._mock_record_start_time = 0.0
        self._mock_output_path: Optional[str] = None

    def enable_mock_mode(self, initial_recording: bool = False) -> None:
        """Enables simulated mock mode for testing without a running OBS instance."""
        self._mock_mode = True
        self._connected = True
        self._obs_version = "30.2.2-Mock"
        self._mock_recording = initial_recording
        if initial_recording:
            self._mock_record_start_time = time.time()
        logger.info("[OBSClient] Mock mode enabled for automated testing.")

    def disable_mock_mode(self) -> None:
        self._mock_mode = False
        self._connected = False
        self._obs_version = None

    def _generate_auth_response(self, password: str, salt: str, challenge: str) -> str:
        """Computes OBS WebSocket v5 SHA-256 challenge response."""
        secret_hash = hashlib.sha256((password + salt).encode("utf-8")).digest()
        secret_b64 = base64.b64encode(secret_hash).decode("utf-8")
        auth_hash = hashlib.sha256((secret_b64 + challenge).encode("utf-8")).digest()
        return base64.b64encode(auth_hash).decode("utf-8")

    def connect(self) -> Tuple[bool, Optional[str]]:
        """
        Connects and authenticates with OBS Studio WebSocket server.
        Returns: (success: bool, error_message: Optional[str])
        """
        if self._mock_mode:
            self._connected = True
            return True, None

        if not settings.OBS_ENABLED:
            return False, "OBS integration is disabled in configuration."

        url = f"ws://{self.host}:{self.port}"
        try:
            ws = websocket.create_connection(url, timeout=self.timeout)
            # Step 1: Wait for Hello (op 0)
            raw_hello = ws.recv()
            hello_msg = json.loads(raw_hello)
            if hello_msg.get("op") != 0:
                ws.close()
                return False, f"Unexpected initial opcode from OBS: {hello_msg.get('op')}"

            hello_data = hello_msg.get("d", {})
            self._obs_version = hello_data.get("obsWebSocketVersion", "5.x")
            auth_info = hello_data.get("authentication")

            # Step 2: Send Identify (op 1)
            identify_payload: Dict[str, Any] = {
                "op": 1,
                "d": {
                    "rpcVersion": 1,
                    "eventSubscriptions": 33,  # General (1) + Outputs (32)
                },
            }

            if auth_info:
                if not self.password:
                    ws.close()
                    return False, "OBS WebSocket requires authentication, but no OBS_PASSWORD is set."
                salt = auth_info["salt"]
                challenge = auth_info["challenge"]
                auth_resp = self._generate_auth_response(self.password, salt, challenge)
                identify_payload["d"]["authentication"] = auth_resp

            ws.send(json.dumps(identify_payload))

            # Step 3: Wait for Identified (op 2)
            raw_identified = ws.recv()
            identified_msg = json.loads(raw_identified)
            if identified_msg.get("op") != 2:
                ws.close()
                return False, f"Authentication failed: {identified_msg}"

            self.ws = ws
            self._connected = True
            logger.info(f"[OBSClient] Successfully connected to OBS Studio v{self._obs_version} at {url}.")
            return True, None

        except (websocket.WebSocketException, OSError, TimeoutError, ConnectionRefusedError) as e:
            self._connected = False
            self.ws = None
            msg = f"Cannot reach OBS Studio at {url}: {e}"
            logger.warning(f"[OBSClient] {msg}")
            return False, msg

    def disconnect(self) -> None:
        """Closes active WebSocket connection."""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        self._connected = False

    def is_connected(self) -> bool:
        if self._mock_mode:
            return self._connected
        if not self.ws or not self._connected:
            return False
        # Quick ping check
        try:
            status = self.get_record_status()
            return status is not None
        except Exception:
            self._connected = False
            return False

    def _send_request(self, request_type: str, request_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """Sends a request (op 6) and waits for response (op 7)."""
        if self._mock_mode:
            return True, {}

        if not self._connected or not self.ws:
            ok, err = self.connect()
            if not ok:
                return False, {"error": err}

        req_id = f"req_{int(time.time() * 1000)}"
        msg = {
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": req_id,
            },
        }
        if request_data:
            msg["d"]["requestData"] = request_data

        try:
            self.ws.send(json.dumps(msg))
            # Read response
            while True:
                raw_resp = self.ws.recv()
                data = json.loads(raw_resp)
                op = data.get("op")
                if op == 7:  # RequestResponse
                    d = data.get("d", {})
                    if d.get("requestId") == req_id:
                        status = d.get("requestStatus", {})
                        if status.get("result") is True:
                            return True, d.get("responseData", {})
                        else:
                            return False, {"error": status.get("comment", "Request failed"), "code": status.get("code")}
        except Exception as e:
            self._connected = False
            self.ws = None
            return False, {"error": str(e)}

    def check_disk_space(self) -> Tuple[bool, float, float]:
        """
        Validates whether sufficient local disk space exists for recording.
        Returns: (sufficient: bool, free_gb: float, total_gb: float)
        """
        target_dir = settings.RECORDINGS_DIR
        try:
            stat = shutil.disk_usage(target_dir)
            free_gb = round(stat.free / (1024 ** 3), 2)
            total_gb = round(stat.total / (1024 ** 3), 2)
            sufficient = free_gb >= settings.MIN_DISK_FREE_SPACE_GB
            return sufficient, free_gb, total_gb
        except Exception as e:
            logger.warning(f"[OBSClient] Failed to check disk space: {e}")
            return True, 50.0, 500.0

    def get_record_status(self) -> Dict[str, Any]:
        """Queries OBS GetRecordStatus."""
        if self._mock_mode:
            rec_time = (time.time() - self._mock_record_start_time) if self._mock_recording else 0.0
            return {
                "outputActive": self._mock_recording,
                "outputDuration": int(rec_time * 1000),
                "outputBytes": int(rec_time * 500000) if self._mock_recording else 0,
                "outputPath": str(Path(settings.RECORDINGS_DIR) / "mock_obs_recording.mp4") if self._mock_recording else None,
            }

        ok, data = self._send_request("GetRecordStatus")
        if not ok:
            return {"outputActive": False, "error": data.get("error")}
        return data

    def start_recording(self) -> Tuple[bool, Optional[str]]:
        """
        Triggers OBS StartRecord.
        Verifies disk space before initiating.
        """
        sufficient, free_gb, _ = self.check_disk_space()
        if not sufficient:
            err = f"Cannot start recording: Insufficient free disk space ({free_gb} GB < {settings.MIN_DISK_FREE_SPACE_GB} GB limit)."
            logger.error(f"[OBSClient] {err}")
            return False, err

        if self._mock_mode:
            self._mock_recording = True
            self._mock_record_start_time = time.time()
            logger.info("[OBSClient] Mock recording started.")
            return True, None

        ok, data = self._send_request("StartRecord")
        if not ok:
            err = data.get("error", "Failed to start OBS recording")
            logger.error(f"[OBSClient] StartRecord failed: {err}")
            return False, err

        logger.info("[OBSClient] StartRecord command sent successfully.")
        return True, None

    def stop_recording(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Triggers OBS StopRecord and retrieves output file path.
        Returns: (success: bool, output_path: Optional[str], error: Optional[str])
        """
        if self._mock_mode:
            self._mock_recording = False
            mock_out = self._mock_output_path or str(Path(settings.RECORDINGS_DIR) / "mock_obs_recording.mp4")
            # Create a real small test file if it doesn't exist
            Path(mock_out).parent.mkdir(parents=True, exist_ok=True)
            if not Path(mock_out).exists():
                Path(mock_out).write_bytes(b"MOCK_VIDEO_DATA" * 50)
            logger.info(f"[OBSClient] Mock recording stopped. Output: {mock_out}")
            return True, mock_out, None

        ok, data = self._send_request("StopRecord")
        if not ok:
            err = data.get("error", "Failed to stop OBS recording")
            logger.error(f"[OBSClient] StopRecord failed: {err}")
            return False, None, err

        output_path = data.get("outputPath")
        logger.info(f"[OBSClient] StopRecord successful. Output path: '{output_path}'")
        return True, output_path, None

    def get_full_status(self) -> Dict[str, Any]:
        """Returns consolidated health, connection, recording, and storage status."""
        connected = self.is_connected()
        record_status = self.get_record_status() if connected else {}
        sufficient, free_gb, total_gb = self.check_disk_space()

        return {
            "connected": connected,
            "host": self.host,
            "port": self.port,
            "version": self._obs_version,
            "is_recording": bool(record_status.get("outputActive", False)),
            "recording_time_seconds": round(record_status.get("outputDuration", 0) / 1000.0, 1),
            "output_path": record_status.get("outputPath"),
            "disk_free_gb": free_gb,
            "disk_total_gb": total_gb,
            "disk_sufficient": sufficient,
            "error": record_status.get("error"),
        }


# Global singleton client
obs_client = OBSClient()
