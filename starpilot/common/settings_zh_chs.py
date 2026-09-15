#!/usr/bin/env python3
"""Chinese (Simplified) strings for Galaxy settings catalog and C3 UI."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

_MAP_PATH = Path(__file__).resolve().parent / "assets" / "settings_zh-CHS.json"

_STRING_KEYS = (
  "name",
  "label",
  "description",
  "picker_description",
  "disabled_reason",
  "action_label",
  "confirm_message",
  "picker_label",
  "placeholder",
  "hint",
  "title",
  "subtitle",
  "message",
  "disabled_label",
  "unit",
)

_POINT_SPEED = re.compile(r"^Vehicle speed in mph for curve point (\d+)\.?$")
_POINT_ACCEL = re.compile(r"^Maximum acceleration in m/s² at curve point (\d+)\.?$")
_POINT_LABEL_SPEED = re.compile(r"^Point (\d+) Speed$")
_POINT_LABEL_ACCEL = re.compile(r"^Point (\d+) Max Accel$")
_OFFSET_MPH = re.compile(r"^Speed Offset \((\d+)[–-](\d+) mph\)$")
_OFFSET_KMH = re.compile(r"^Speed Offset \((\d+)[–-](\d+) km/h\)$")
_OFFSET_DESC_MPH = re.compile(r"^How much to offset posted speed[- ]limits between ([0-9]+[–-][0-9]+) mph\.$")
_OFFSET_DESC_KMH = re.compile(r"^How much to offset posted speed[- ]limits between ([0-9]+[–-][0-9]+) km/h\.$")
_WEATHER_FOLLOW = re.compile(r"^Increase Following Distance by:$")
_BUTTON_PRESS = re.compile(
  r'^Action performed when the (?:remapped )?"([^"]+)" button is pressed'
  r"(?: for more than ([0-9.]+) seconds)?\.?(?: Hyundai CAN-FD only\.)?$"
)
_CC_MAIN = re.compile(r"^Action performed when the cruise control main button is pressed\.$")


def _load_map() -> dict[str, str]:
  try:
    data = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError, TypeError):
    return {}
  if not isinstance(data, dict):
    return {}
  return {str(k): str(v) for k, v in data.items() if k and v}


def reload_map() -> dict[str, str]:
  global ZH_CHS
  ZH_CHS = _load_map()
  return ZH_CHS


ZH_CHS = _load_map()


def section_slug(name: str) -> str:
  return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")


def attach_section_slugs(layout: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
  if not isinstance(layout, list):
    return layout
  for section in layout:
    if isinstance(section, dict) and not section.get("slug"):
      section["slug"] = section_slug(section.get("name") or "")
  return layout


def _pattern_translate(text: str) -> str | None:
  try:
    return _pattern_translate_inner(text)
  except Exception:
    return None


def _pattern_translate_inner(text: str) -> str | None:
  m = _POINT_LABEL_SPEED.match(text)
  if m:
    return f"第 {m.group(1)} 点车速"
  m = _POINT_LABEL_ACCEL.match(text)
  if m:
    return f"第 {m.group(1)} 点最大加速度"
  m = _POINT_SPEED.match(text)
  if m:
    return f"自定义加速曲线第 {m.group(1)} 点的车速（英里/小时）。后一点必须高于前一点。"
  m = _POINT_ACCEL.match(text)
  if m:
    return f"自定义加速曲线第 {m.group(1)} 点的最大加速度（米/秒²）。"
  m = _OFFSET_MPH.match(text)
  if m:
    return f"限速偏移（{m.group(1)}–{m.group(2)} 英里/小时）"
  m = _OFFSET_KMH.match(text)
  if m:
    return f"限速偏移（{m.group(1)}–{m.group(2)} 公里/小时）"
  m = _OFFSET_DESC_MPH.match(text)
  if m:
    return f"对 {m.group(1)} 英里/小时区间的限速偏移量。"
  m = _OFFSET_DESC_KMH.match(text)
  if m:
    return f"对 {m.group(1)} 公里/小时区间的限速偏移量。"
  m = _BUTTON_PRESS.match(text)
  if m:
    name = translate_text(m.group(1))
    hold = m.group(2)
    if hold == "0.5":
      return f"长按（超过 0.5 秒）“{name}”键时执行的动作。"
    if hold == "2.5":
      return f"超长按（超过 2.5 秒）“{name}”键时执行的动作。"
    return f"按下“{name}”键时执行的动作。"
  if _CC_MAIN.match(text):
    return "按下巡航主开关时执行的动作。"
  return None


def translate_text(value: Any) -> Any:
  if not isinstance(value, str) or not value.strip():
    return value
  candidates = (value, value.replace('\\"', '"'), value.replace('\\\\', '\\'))
  for candidate in candidates:
    found = ZH_CHS.get(candidate)
    if found:
      return found
  patterned = _pattern_translate(value)
  if patterned:
    return patterned
  return value


def translate_catalog(layout: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
  if not layout:
    return layout
  data = copy.deepcopy(layout)

  def walk(obj: Any) -> None:
    if isinstance(obj, dict):
      for key, child in obj.items():
        if key in _STRING_KEYS and isinstance(child, str):
          obj[key] = translate_text(child)
        elif key == "description_steps" and isinstance(child, list):
          for step in child:
            if isinstance(step, dict) and isinstance(step.get("description"), str):
              step["description"] = translate_text(step["description"])
        elif key == "labels" and isinstance(child, list):
          obj[key] = [translate_text(item) if isinstance(item, str) else item for item in child]
        elif key == "options" and isinstance(child, list):
          for opt in child:
            if isinstance(opt, dict):
              for field in ("label", "description"):
                if isinstance(opt.get(field), str):
                  opt[field] = translate_text(opt[field])
        else:
          walk(child)
    elif isinstance(obj, list):
      for item in obj:
        walk(item)

  walk(data)
  return data


def _lang_text(value: Any) -> str:
  if isinstance(value, (bytes, bytearray)):
    value = value.decode("utf-8", "ignore")
  text = str(value or "").strip()
  if len(text) >= 3 and text.startswith("b'") and text.endswith("'"):
    text = text[2:-1]
  return text.replace("main_", "").replace("MAIN_", "")


def language_wants_chinese(value: Any) -> bool:
  text = _lang_text(value).lower()
  if not text or text in ("none", "null"):
    return True
  if text in ("en", "english"):
    return False
  return text.startswith("zh")
