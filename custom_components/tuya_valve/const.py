"""Constants for the Tuya Valve custom integration."""

DOMAIN = "tuya_valve"

CONF_BASE_URL = "base_url"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_DEVICE_ID = "device_id"
CONF_NAME = "name"

DEFAULT_NAME = "Tuya Valve"
DEFAULT_BASE_URL = "https://openapi.tuyaus.com"
DEFAULT_SCAN_SEC = 30

PROP_MAIN_SWITCH = "main_switch"               # rw, raw (expects {"totalswitch": ...})
PROP_GET_STATE_TOTAL = "get_valve_state_total" # wr, bool
PROP_STATE_LIST = "valve_state_list"           # ro, raw (Base64(JSON))

PLATFORMS = ["valve"]
