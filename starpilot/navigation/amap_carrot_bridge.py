#!/usr/bin/env python3
"""Receive Amap / Carrot navi packets the same way Carrot/Lane/egpu/onnx do.

Carrot Web listens on 7000. 高德车机版 / TMAP patched apps POST rgdata to
7713 /api/navi/<version>. Discovery beacons go out on UDP 7705 so the phone
app can find this C3.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

STALE_SECONDS = 8.0
WEB_PORT = int(os.environ.get("CARROT_WEB_PORT", "7000"))
NAVI_HTTP_PORT = int(os.environ.get("CARROT_NAVI_HTTP_PORT", "7713"))
DISCOVERY_PORT = int(os.environ.get("CARROT_NAVI_DISCOVERY_PORT", "7705"))
DISCOVERY_INTERVAL_S = 1.0

# Same TBT ids as CarrotServ._update_tbt on Lane/Carrot.
TURN_TYPE_MAPPING = {
  12: ("turn", "left"),
  16: ("turn", "sharp left"),
  13: ("turn", "right"),
  19: ("turn", "sharp right"),
  102: ("off ramp", "slight left"),
  105: ("off ramp", "slight left"),
  112: ("off ramp", "slight left"),
  115: ("off ramp", "slight left"),
  101: ("off ramp", "slight right"),
  104: ("off ramp", "slight right"),
  111: ("off ramp", "slight right"),
  114: ("off ramp", "slight right"),
  7: ("fork", "left"),
  44: ("fork", "left"),
  17: ("fork", "left"),
  75: ("fork", "left"),
  76: ("fork", "left"),
  118: ("fork", "left"),
  6: ("fork", "right"),
  43: ("fork", "right"),
  73: ("fork", "right"),
  74: ("fork", "right"),
  123: ("fork", "right"),
  124: ("fork", "right"),
  117: ("fork", "right"),
  131: ("rotary", "slight right"),
  132: ("rotary", "slight right"),
  140: ("rotary", "slight left"),
  141: ("rotary", "slight left"),
  133: ("rotary", "right"),
  134: ("rotary", "sharp right"),
  135: ("rotary", "sharp right"),
  136: ("rotary", "sharp left"),
  137: ("rotary", "sharp left"),
  138: ("rotary", "sharp left"),
  139: ("rotary", "left"),
  142: ("rotary", "straight"),
  14: ("turn", "uturn"),
  201: ("arrive", "straight"),
}

_state_lock = threading.Lock()
_last_navi: dict[str, Any] = {}
_last_navi_at = 0.0
_last_error = ""


def _i(value: Any, default: int = 0) -> int:
  try:
    return int(float(value))
  except (TypeError, ValueError):
    return default


def _s(value: Any) -> str:
  if value is None:
    return ""
  text = str(value).strip()
  return "" if text.lower() in ("null", "none") else text


def _f(value: Any, default: float = 0.0) -> float:
  try:
    return float(value)
  except (TypeError, ValueError):
    return default


def detect_advertise_ip() -> str:
  probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  try:
    probe.connect(("8.8.8.8", 80))
    return str(probe.getsockname()[0])
  except OSError:
    return "127.0.0.1"
  finally:
    probe.close()


def _decode_road_limit(raw: int) -> int:
  if raw <= 0:
    return 30
  if raw > 200:
    return int((raw - 20) / 10)
  if raw == 120:
    return 115
  return raw


def _extract_rgdata(payload: Any) -> dict[str, Any]:
  if not isinstance(payload, dict):
    return {}
  rgdata = payload.get("rgdata")
  if isinstance(rgdata, dict):
    merged = dict(rgdata)
    for group in ("guidance", "sdi", "lane"):
      nested = payload.get(group)
      if isinstance(nested, dict):
        for key, value in nested.items():
          merged.setdefault(key, value)
    return merged
  return payload


def _maneuver(turn_type: int, dist: int, text: str) -> tuple[str, str, float, str]:
  mapped = TURN_TYPE_MAPPING.get(turn_type, ("turn", "straight"))
  nav_type, modifier = mapped
  if not nav_type:
    nav_type, modifier = "turn", "straight"
  modifier = modifier.replace(" ", "")
  if modifier == "sharpleft":
    modifier = "sharpLeft"
  elif modifier == "sharpright":
    modifier = "sharpRight"
  elif modifier == "slightleft":
    modifier = "slightLeft"
  elif modifier == "slightright":
    modifier = "slightRight"
  return nav_type, modifier, float(max(dist, 0)), text


def publish_navi(rgdata: dict[str, Any]) -> dict[str, Any]:
  global _last_navi, _last_navi_at, _last_error
  if "nRoadLimitSpeed" not in rgdata and "nTBTTurnType" not in rgdata:
    raise ValueError("missing navi fields")

  road_limit = _decode_road_limit(_i(rgdata.get("nRoadLimitSpeed"), 0))
  tbt_type = _i(rgdata.get("nTBTTurnType"), -1)
  tbt_dist = _i(rgdata.get("nTBTDist"), 0)
  tbt_text = _s(rgdata.get("szTBTMainText") or rgdata.get("szPosRoadName"))
  next_type = _i(rgdata.get("nTBTTurnTypeNext"), -1)
  next_dist = _i(rgdata.get("nTBTDistNext"), 0) + tbt_dist
  next_text = _s(rgdata.get("szTBTMainTextNext"))
  dest_name = _s(rgdata.get("szGoalName") or "高德导航")
  lat = _f(rgdata.get("goalPosY") or rgdata.get("vpPosPointLat"))
  lon = _f(rgdata.get("goalPosX") or rgdata.get("vpPosPointLon"))

  nav_type, modifier, distance, primary = _maneuver(tbt_type, tbt_dist, tbt_text)
  next_nav_type, next_modifier, next_distance, _ = _maneuver(next_type, next_dist, next_text)
  valid = tbt_type >= 0 or road_limit > 0

  state = {
    "valid": valid,
    "source": "amap_carrot",
    "speedLimit": road_limit / 3.6 if road_limit > 0 else 0.0,
    "maneuverType": nav_type,
    "maneuverModifier": modifier,
    "maneuverDistance": distance,
    "maneuverPrimaryText": primary or dest_name,
    "maneuverSecondaryText": _s(rgdata.get("szNearDirName") or rgdata.get("szFarDirName")),
    "nextManeuverType": next_nav_type if next_type >= 0 else "",
    "nextManeuverModifier": next_modifier if next_type >= 0 else "",
    "nextManeuverDistance": next_distance if next_type >= 0 else 0.0,
    "nSdiType": _i(rgdata.get("nSdiType"), -1),
    "nSdiSpeedLimit": _i(rgdata.get("nSdiSpeedLimit"), 0),
    "nSdiDist": _i(rgdata.get("nSdiDist"), -1),
  }

  try:
    from openpilot.common.params import Params
    params = Params()
    memory = Params(memory=True)
    memory.put_nonblocking("NavInstructionState", state)
    if dest_name and lat and lon:
      params.put("NavDestination", json.dumps({
        "name": dest_name,
        "place_name": dest_name,
        "latitude": lat,
        "longitude": lon,
      }))
  except Exception as exc:
    _last_error = str(exc)

  with _state_lock:
    _last_navi = state
    _last_navi_at = time.monotonic()
  return state


def _stale_watch() -> None:
  global _last_error
  while True:
    time.sleep(1.0)
    with _state_lock:
      age = time.monotonic() - _last_navi_at if _last_navi_at else 1e9
      active = dict(_last_navi) if _last_navi else {}
    if age <= STALE_SECONDS or not active:
      continue
    active["valid"] = False
    try:
      from openpilot.common.params import Params
      Params(memory=True).put_nonblocking("NavInstructionState", active)
    except Exception as exc:
      _last_error = str(exc)
    with _state_lock:
      _last_navi = active


def _discovery_loop() -> None:
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
  payload = json.dumps({"ip": detect_advertise_ip(), "navi_debug": 0}).encode()
  while True:
    try:
      payload = json.dumps({"ip": detect_advertise_ip(), "navi_debug": 0}).encode()
      sock.sendto(payload, ("255.255.255.255", DISCOVERY_PORT))
    except OSError:
      pass
    time.sleep(DISCOVERY_INTERVAL_S)


class NaviHandler(BaseHTTPRequestHandler):
  protocol_version = "HTTP/1.1"

  def log_message(self, fmt: str, *args: Any) -> None:
    print(f"[amap_carrot_bridge] {self.address_string()} {fmt % args}", flush=True)

  def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
    self.send_response(code)
    self.send_header("Content-Type", content_type)
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    self.wfile.write(body)

  def do_OPTIONS(self) -> None:  # noqa: N802
    self.send_response(204)
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "*")
    self.end_headers()

  def do_GET(self) -> None:  # noqa: N802
    path = urlparse(self.path).path.rstrip("/") or "/"
    with _state_lock:
      status = {
        "ok": True,
        "feature": "amapCarrotNavi",
        "webPort": WEB_PORT,
        "naviHttpPort": NAVI_HTTP_PORT,
        "discoveryPort": DISCOVERY_PORT,
        "advertiseIp": detect_advertise_ip(),
        "lastNaviAt": _last_navi_at,
        "navi": _last_navi,
        "error": _last_error,
      }
    if path in ("/", "/index.html"):
      html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>StarPilot 高德联动</title></head>
<body>
<h1>StarPilot 高德 / Carrot Navi</h1>
<p>网页端口 <b>{WEB_PORT}</b>，导航接收 <b>{NAVI_HTTP_PORT}</b>，发现广播 UDP <b>{DISCOVERY_PORT}</b>。</p>
<p>高德车机版把 C3 地址填成 <code>{detect_advertise_ip()}</code> 即可，协议与胡萝卜 Lane/Carrot/egpu/onnx 相同。</p>
<pre>{json.dumps(status, ensure_ascii=False, indent=2)}</pre>
</body></html>"""
      self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
      return
    if path in ("/api/status", "/api/carrot_navi/status", "/params"):
      self._send(200, json.dumps(status, ensure_ascii=False).encode("utf-8"))
      return
    self._send(404, b'{"ok":false,"error":"not found"}')

  def do_POST(self) -> None:  # noqa: N802
    path = urlparse(self.path).path
    if not (path.startswith("/api/navi") or path in ("/navi", "/carrot", "/rgdata")):
      self._send(404, b'{"ok":false,"error":"not found"}')
      return
    length = int(self.headers.get("Content-Length", "0") or 0)
    raw = self.rfile.read(max(length, 0)) if length else b"{}"
    try:
      payload = json.loads(raw.decode("utf-8", errors="replace") or "{}")
      state = publish_navi(_extract_rgdata(payload))
      self._send(200, json.dumps({"ok": True, "navi": state}, ensure_ascii=False).encode("utf-8"))
    except Exception as exc:
      self._send(400, json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))


def _serve(port: int) -> None:
  httpd = ThreadingHTTPServer(("0.0.0.0", port), NaviHandler)
  print(f"[amap_carrot_bridge] listening 0.0.0.0:{port}", flush=True)
  httpd.serve_forever()


def main() -> None:
  threading.Thread(target=_stale_watch, daemon=True).start()
  threading.Thread(target=_discovery_loop, daemon=True).start()
  threading.Thread(target=_serve, args=(NAVI_HTTP_PORT,), daemon=True).start()
  _serve(WEB_PORT)


if __name__ == "__main__":
  main()
