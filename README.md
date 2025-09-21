# Tuya Valve (Cloud Minimal) — Home Assistant Custom Integration

Control a Tuya-based **remote water valve** from Home Assistant using the Tuya Cloud v2 API.  
This integration creates a single `valve` entity able to **open/close** and **poll ON/OFF state** for devices that expose Tuya “raw” properties for the main switch and a Base64-encoded state list.

> ⚠️ This is a *minimal, device-specific* cloud integration. It was written for valves that report `main_switch` (raw) and `valve_state_list` (raw) with a `get_valve_state_total` trigger. If your valve reports different codes, this integration will not work without changes.

> ✅ Developed and tested against the Tuya valve model **YS_SM_WV** (previously sold on [Amazon](https://www.amazon.com/dp/B0D2D25854?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_12), now unavailable). It may work with other Tuya-based valves that expose the same property codes.

---

## Features

- UI config-flow (no YAML): enter **Base URL**, **Access ID**, **Access Secret**, and **Device ID**.
- Creates one Home Assistant **Valve** entity with device class **Water** (open/close only).
- Polls only the ON/OFF state on a schedule (default: 30s).  
- Populates the Device page with static metadata (name, model, MAC, SN) fetched once from Tuya Cloud.
- Exposes handy static attributes on the entity for quick reference (device id, product id, etc.).

How it maps Tuya → HA:

- **Open/Close**: sends `main_switch` with a Base64-encoded JSON `{"totalswitch": true|false}`.
- **State**: triggers `get_valve_state_total: true`, then reads `valve_state_list` (Base64 JSON) and parses `valvestatelist[0]` (`true`=open flow).

---

## Requirements

- Home Assistant 2024.12+ (Valve platform).
- A Tuya **Cloud Project** (IoT Console) with:
  - **Access ID** / **Access Secret**,
  - Correct **Data Center** (Base URL),
  - Your **Tuya App Account linked** to the cloud project,
  - The target **device bound** to that app account.
- Internet connectivity from your HA host.

---

## Installation

### Option A: Manual (custom_components)

1. Copy the folder `custom_components/tuya_valve/` into your HA config directory:
   ```text
   <config>/
     custom_components/
       tuya_valve/
         __init__.py
         client.py
         config_flow.py
         const.py
         manifest.json
         valve.py
         translations/en.json
   ```
2. Restart Home Assistant.

### Option B: HACS (Custom repo)

1. In HACS → Integrations → ⋯ → **Custom repositories**, add your GitHub repo URL and category **Integration**.
2. Install **Tuya Valve (Cloud Minimal)** and restart Home Assistant.

---

## Configuration

1. In Home Assistant: **Settings → Devices & Services → + Add Integration → Tuya Valve (Cloud Minimal)**.
2. Fill the fields:
   - **Base URL**: e.g. `https://openapi.tuyaus.com` (US), EU/IN endpoints as appropriate.
   - **Access ID** (a.k.a. Client ID)
   - **Access Secret**
   - **Device ID**: the Tuya device ID of your valve
3. Submit. The flow validates credentials and fetches the device name for the entity title.
4. (Optional) In **Options** set a different **Polling interval** (seconds).

**Where to find Device ID / Credentials?**  
In the Tuya IoT Console: **Cloud → Projects → (your project)**: Credentials on the project overview.  
Link your mobile app account under **Cloud → Projects → Link Tuya App Account**, then check **Devices** to copy the device ID.

---

## Entity Behavior

- Entity type: **Valve** with device class **Water**.
- Supported features: **OPEN** and **CLOSE** (no position reporting).
- Device page shows Manufacturer, Model, MAC, and Serial if Tuya provides them.
- Entity attributes include Tuya IDs and product metadata for quick copy/paste.

---

## How it Works (under the hood)

- Auth: Tuya Cloud **v2 HMAC-SHA256** canonical signing. Tokens are cached and refreshed automatically.
- Endpoints used:
  - `GET /v1.0/token?grant_type=1` — fetch access token
  - `GET /v1.0/iot-03/devices/{device_id}` — one-shot device metadata
  - `POST /v2.0/cloud/thing/{device_id}/shadow/properties/issue` — send properties
  - `GET /v2.0/cloud/thing/{device_id}/shadow/properties?codes=...` — query properties
- Property codes used by default:
  - `main_switch` (raw) — send Base64 JSON `{"totalswitch": true|false}` to open/close
  - `get_valve_state_total` (bool) — trigger device to publish its state
  - `valve_state_list` (raw) — read Base64 JSON and parse `valvestatelist[0]`

---

## Troubleshooting

**“token invalid” (`code: 1010`)**  
- Wrong **Base URL** (Data Center). Use the one that matches your project’s region.  
- App account not linked to this cloud project. Link it and verify the device appears under project **Devices**.  
- Access ID/Secret typo.

**“sign invalid” (`code: 1004`)**  
- System clock skew. Sync the HA host time.  
- Copy/paste errors in Access ID/Secret.  
- Extra spaces or wrong Base URL.

**“param is illegal” (`code: 1109`)**  
- Your device doesn’t use these property codes or formats. Inspect the device **model** (things model) in Tuya Cloud and adapt `client.py` accordingly.

**Entity never changes state**  
- Some valves take ~0.5–1.0s to publish state. This integration triggers state and then polls; try increasing polling interval slightly if you see flapping.

---

## Security

- **Never commit** your Access Secret / Device ID. Use HA **secrets.yaml** or the UI config flow.  
- If you accidentally published secrets, **rotate them** in the Tuya IoT Console and clean your Git history (e.g., with `git filter-repo`).

---

## Limitations

- Cloud-only; latency and rate limits apply. If you need LAN/local control, use a local integration or device that exposes local DP codes.
- Tested with specific Tuya water valves that report the raw properties listed above; other models may require code tweaks.
- Icons/logo: HA shows vendor icons only when the integration is listed in the official Brands repo.

---

## Development

- Code style: ruff + HA conventions (docstrings, imports, etc.).
- Key files:
  - `manifest.json` — domain, requirements, and metadata
  - `const.py` — property codes and defaults
  - `client.py` — REST client + signing + valve logic
  - `valve.py` — entity, device info, attributes, coordinator
  - `config_flow.py` — UI setup + options

PRs and issues welcome!


