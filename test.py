# tuya_valve_clean.py
# pip install requests
import time, json, uuid, hmac, hashlib, base64, requests
from typing import Dict, Any, Optional
import secret

# --- EDIT THESE ---
BASE          = "https://openapi.tuyaus.com"        # your Tuya data center
CLIENT_ID     = secret.ID              # Access ID
CLIENT_SECRET = secret.KEY   # Access Secret
DEVICE_ID     = secret.DEVICE_ID           # Backyard Water Valve

# model property codes we use
PROP_MAIN_SWITCH     = "main_switch"            # rw, raw (expects {"totalswitch": ...})
PROP_GET_STATE_TOTAL = "get_valve_state_total"  # wr, bool
PROP_STATE_LIST      = "valve_state_list"       # ro, raw (Base64(JSON))

# ----- helpers -----
def _now_ms() -> str:
    return str(int(time.time() * 1000))

def _sha256_hex(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

def _hmac_hex(key: str, msg: str) -> str:
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest().upper()

def _b64_obj(o: Dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(o, separators=(",", ":")).encode()).decode()

# ----- single-style (v2 canonical) signing -----
_token_cache: Dict[str, Any] = {"access_token": None, "ts": 0.0, "ttl": 0}

def _req_v2(method: str, path_with_query: str, body_obj: Optional[Dict[str, Any]]=None, need_token: bool=True) -> Dict[str, Any]:
    body = "" if body_obj is None else json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
    t = _now_ms()
    nonce = uuid.uuid4().hex
    bodyhash = _sha256_hex(body)
    string_to_sign = f"{method}\n{bodyhash}\n\n{path_with_query}"

    headers = {
        "client_id": CLIENT_ID,
        "t": t,
        "nonce": nonce,
        "sign_headers": "",
        "sign_method": "HMAC-SHA256",
        "Content-Type": "application/json",
    }

    # include access_token when required (all non-token calls)
    if need_token:
        at = _access_token()
        headers["access_token"] = at
        sign_str = CLIENT_ID + at + t + nonce + string_to_sign
    else:
        sign_str = CLIENT_ID + t + nonce + string_to_sign

    headers["sign"] = _hmac_hex(CLIENT_SECRET, sign_str)

    r = requests.request(method, f"{BASE}{path_with_query}", headers=headers, data=body, timeout=20)
    try:
        return r.json()
    except Exception:
        return {"http_status": r.status_code, "text": r.text}

def _token_v2() -> Dict[str, Any]:
    return _req_v2("GET", "/v1.0/token?grant_type=1", None, need_token=False)

def _access_token() -> str:
    now = time.time()
    if _token_cache["access_token"] and (now - _token_cache["ts"] < max(1, _token_cache["ttl"] - 60)):
        return _token_cache["access_token"]
    j = _token_v2()
    if not j.get("success"):
        raise RuntimeError(f"Token error: {j}")
    res = j["result"]
    _token_cache.update(access_token=res["access_token"], ts=now, ttl=res.get("expire_time", 3600))
    return res["access_token"]

# ----- Tuya Things (only what we need) -----
def _props_issue(props: Dict[str, Any]) -> Dict[str, Any]:
    body = {"properties": json.dumps(props, ensure_ascii=False, separators=(",", ":"))}
    return _req_v2("POST", f"/v2.0/cloud/thing/{DEVICE_ID}/shadow/properties/issue", body, need_token=True)

def _props_query(codes) -> Dict[str, Any]:
    return _req_v2("GET", f"/v2.0/cloud/thing/{DEVICE_ID}/shadow/properties?codes={','.join(codes)}", None, need_token=True)

def _read_state_bool() -> Optional[bool]:
    # ask device to publish total state; then read
    _props_issue({PROP_GET_STATE_TOTAL: True})
    time.sleep(0.8)
    j = _props_query([PROP_STATE_LIST])
    try:
        prop = (j.get("result") or {}).get("properties", [])[0]
        decoded = json.loads(base64.b64decode(prop["value"]).decode())
        return bool(decoded["valve_state_list"]["valvestatelist"][0])
    except Exception:
        return None

# ----- public API -----
def valve_on() -> bool:
    # exact payload the device reports: {"totalswitch": true} (Base64) under "main_switch"
    _props_issue({PROP_MAIN_SWITCH: _b64_obj({"totalswitch": True})})
    time.sleep(1.0)
    return _read_state_bool() is True

def valve_off() -> bool:
    _props_issue({PROP_MAIN_SWITCH: _b64_obj({"totalswitch": False})})
    time.sleep(1.0)
    return _read_state_bool() is False

def valve_state() -> Optional[bool]:
    return _read_state_bool()

# ----- tiny CLI -----
if __name__ == "__main__":
    print(valve_off())