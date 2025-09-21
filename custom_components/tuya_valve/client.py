"""Tuya Cloud client for the Remote Water Valve (v2 canonical signing).

This module implements just enough of Tuya's Cloud API to:
- obtain/refresh a project token
- issue/read "thing shadow" properties for the valve
- read device metadata (name, mac, sn, model, etc.)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
import uuid

import requests

from .const import PROP_GET_STATE_TOTAL, PROP_MAIN_SWITCH, PROP_STATE_LIST


class TuyaValveClient:
    """Minimal Tuya cloud client for this valve (v2 canonical signing only)."""

    def __init__(self, base: str, client_id: str, client_secret: str, device_id: str) -> None:
        """Initialize the client with endpoint, credentials, and target device id."""
        self.base = base.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.device_id = device_id
        self._token_cache: dict[str, Any] = {"access_token": None, "ts": 0.0, "ttl": 0}

    # ----- signing helpers -----
    def _now_ms(self) -> str:
        """Return the current timestamp in milliseconds as a string."""
        return str(int(time.time() * 1000))

    def _sha256_hex(self, s: str) -> str:
        """Return the SHA256 hex digest of a string (empty-string safe)."""
        return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

    def _hmac_hex(self, key: str, msg: str) -> str:
        """Return the uppercased HMAC-SHA256 hex digest for (key, msg)."""
        return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest().upper()

    # ----- v2 canonical request -----
    def _req_v2(
        self,
        method: str,
        path_with_query: str,
        body_obj: dict[str, Any] | None = None,
        need_token: bool = True,
    ) -> dict[str, Any]:
        """Perform a signed Tuya v2 request and return JSON (or a small error dict)."""
        body = "" if body_obj is None else json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
        t = self._now_ms()
        nonce = uuid.uuid4().hex
        bodyhash = self._sha256_hex(body)
        sts = f"{method}\n{bodyhash}\n\n{path_with_query}"

        headers = {
            "client_id": self.client_id,
            "t": t,
            "nonce": nonce,
            "sign_headers": "",
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json",
        }

        if need_token:
            at = self._access_token()
            headers["access_token"] = at
            sign_str = self.client_id + at + t + nonce + sts
        else:
            sign_str = self.client_id + t + nonce + sts

        headers["sign"] = self._hmac_hex(self.client_secret, sign_str)

        try:
            resp = requests.request(
                method,
                f"{self.base}{path_with_query}",
                headers=headers,
                data=body,
                timeout=20,
            )
        except requests.RequestException as exc:
            # Network/transport error
            return {"success": False, "error": "request_exception", "message": str(exc)}

        try:
            return resp.json()
        except ValueError:
            # Non-JSON body; return minimal context for debugging
            return {"success": False, "http_status": resp.status_code, "text": resp.text}

    def _token_v2(self) -> dict[str, Any]:
        """Request a new project token (no access_token in the signature)."""
        return self._req_v2("GET", "/v1.0/token?grant_type=1", None, need_token=False)

    def _access_token(self) -> str:
        """Return a cached access token, refreshing when near expiry."""
        now = time.time()
        if self._token_cache["access_token"] and (now - self._token_cache["ts"] < max(1, self._token_cache["ttl"] - 60)):
            return self._token_cache["access_token"]
        j = self._token_v2()
        if not j.get("success"):
            raise RuntimeError(f"Tuya token error: {j}")
        res = j["result"]
        self._token_cache.update(access_token=res["access_token"], ts=now, ttl=res.get("expire_time", 3600))
        return res["access_token"]

    # ----- Things endpoints we actually use -----
    def _props_issue(self, props: dict[str, Any]) -> dict[str, Any]:
        """Issue thing-shadow properties to the device."""
        body = {"properties": json.dumps(props, ensure_ascii=False, separators=(",", ":"))}
        return self._req_v2(
            "POST",
            f"/v2.0/cloud/thing/{self.device_id}/shadow/properties/issue",
            body,
            need_token=True,
        )

    def _props_query(self, codes: list[str]) -> dict[str, Any]:
        """Query thing-shadow properties by code list."""
        return self._req_v2(
            "GET",
            f"/v2.0/cloud/thing/{self.device_id}/shadow/properties?codes={','.join(codes)}",
            None,
            need_token=True,
        )

    # ----- Device metadata (one-shot) -----
    def device_meta(self) -> dict[str, Any] | None:
        """Return Tuya device metadata (name, mac, sn, product info...), or None."""
        j = self._req_v2("GET", f"/v1.0/iot-03/devices/{self.device_id}")
        if isinstance(j, dict) and j.get("success") and isinstance(j.get("result"), dict):
            return j["result"]
        return None

    def device_name(self) -> str | None:
        """Convenience accessor for the device display name."""
        meta = self.device_meta()
        return meta.get("name") if meta else None

    # ----- Valve ops -----
    def _b64_obj(self, o: dict[str, Any]) -> str:
        """Encode a JSON-serializable object as Base64(JSON)."""
        return base64.b64encode(json.dumps(o, separators=(",", ":")).encode()).decode()

    def state(self) -> bool | None:
        """Return True=flow open, False=closed, or None if unknown."""
        self._props_issue({PROP_GET_STATE_TOTAL: True})
        time.sleep(0.8)
        j = self._props_query([PROP_STATE_LIST])
        try:
            prop = (j.get("result") or {}).get("properties", [])[0]
            decoded = json.loads(base64.b64decode(prop["value"]).decode())
            return bool(decoded["valve_state_list"]["valvestatelist"][0])
        except (IndexError, KeyError, ValueError, TypeError):
            return None

    def turn_on(self) -> bool:
        """Open the valve; return True on success (confirmed by readback)."""
        self._props_issue({PROP_MAIN_SWITCH: self._b64_obj({"totalswitch": True})})
        time.sleep(0.8)
        return self.state() is True

    def turn_off(self) -> bool:
        """Close the valve; return True on success (confirmed by readback)."""
        self._props_issue({PROP_MAIN_SWITCH: self._b64_obj({"totalswitch": False})})
        time.sleep(0.8)
        return self.state() is False

    def validate(self) -> bool:
        """Lightweight credential/device check used by the config flow."""
        try:
            self._access_token()
            self.state()
        except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
            return False
        else:
            return True
