#!/usr/bin/env python3
"""Apply Jetta MK7 fingerprint, MQB CAN parsers, and persistent ActivateCruiseAfterBrake=1."""
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

def must_read(rel):
  p = ROOT / rel
  if not p.exists():
    raise SystemExit(f"missing {p}")
  return p, p.read_text(encoding="utf-8")

# --- launch fingerprint ---
p, t = must_read("launch_chffrplus.sh")
needle = 'source "$DIR/launch_env.sh"\n'
insert = needle + (
  "\n# Hardcode Volkswagen Jetta MK7 so car selection cannot drift.\n"
  'export FINGERPRINT="${FINGERPRINT:-VOLKSWAGEN_JETTA_MK7}"\n'
  'export SKIP_FW_QUERY="${SKIP_FW_QUERY:-1}"\n'
)
if "VOLKSWAGEN_JETTA_MK7" not in t:
  if needle not in t:
    raise SystemExit("launch_chffrplus.sh: source line not found")
  t = t.replace(needle, insert, 1)
  p.write_text(t, encoding="utf-8")
  print("patched launch_chffrplus.sh")
else:
  print("launch_chffrplus.sh already has MK7 fingerprint")

# --- skip AGNOS flash (carrot 19.6.3 hangs on updater / comma logo) ---
p, t = must_read("launch_chffrplus.sh")
old_agnos = '''  # Check if AGNOS update is required
  AGNOS_CURRENT_VERSION="$(< /VERSION)"
  AGNOS_UPDATE_REQUIRED=1
  for accepted_version in $AGNOS_ACCEPTED_VERSIONS; do
    if [ "$AGNOS_CURRENT_VERSION" = "$accepted_version" ]; then
      AGNOS_UPDATE_REQUIRED=0
      break
    fi
  done

  if [ "$AGNOS_UPDATE_REQUIRED" = "1" ]; then
    AGNOS_PY="$DIR/system/hardware/tici/agnos.py"
    MANIFEST="$DIR/system/hardware/tici/agnos.json"
    if $AGNOS_PY --verify $MANIFEST; then
      sudo reboot
    fi
    $DIR/system/hardware/tici/updater $AGNOS_PY $MANIFEST
  fi
'''
new_agnos = '''  # Never flash AGNOS from this tree. Carrot 19.6.3 hanging on updater looks like a frozen comma logo.
  AGNOS_CURRENT_VERSION="$(< /VERSION)"
  AGNOS_UPDATE_REQUIRED=0
  sp_boot_timing_line "skip_agnos_update current=${AGNOS_CURRENT_VERSION}"
'''
if "skip_agnos_update" not in t:
  if old_agnos not in t:
    raise SystemExit("launch_chffrplus.sh: AGNOS updater block not found")
  t = t.replace(old_agnos, new_agnos, 1)
  p.write_text(t, encoding="utf-8")
  print("patched launch_chffrplus.sh AGNOS skip")

p, t = must_read("launch_env.sh")
if "19.6.3-carrot" not in t:
  t = t.replace(
    'export AGNOS_ACCEPTED_VERSIONS="$AGNOS_VERSION"',
    'export AGNOS_ACCEPTED_VERSIONS="$AGNOS_VERSION 19.6.3-carrot"',
    1,
  )
  p.write_text(t, encoding="utf-8")
  print("patched launch_env.sh accepted AGNOS")

# --- params ---
p, t = must_read("common/params_keys.h")
t = t.replace(
  '{"ForceFingerprint", {PERSISTENT, BOOL, "0", "0", 2, SETTINGS_SIMPLE}},',
  '{"ForceFingerprint", {PERSISTENT, BOOL, "1", "1", 2, SETTINGS_SIMPLE}},',
  1,
)
if "ActivateCruiseAfterBrake" not in t:
  t = t.replace(
    '{"ForceFingerprint", {PERSISTENT, BOOL, "1", "1", 2, SETTINGS_SIMPLE}},',
    '{"ForceFingerprint", {PERSISTENT, BOOL, "1", "1", 2, SETTINGS_SIMPLE}},\n'
    '    {"ActivateCruiseAfterBrake", {PERSISTENT, INT, "1", "1", 2, SETTINGS_SIMPLE}},',
    1,
  )
p.write_text(t, encoding="utf-8")
print("patched params_keys.h")

# --- controlsd ACB ---
p, t = must_read("selfdrive/controls/controlsd.py")
if "_acb_need_resume" not in t:
  t = t.replace(
    "    self.params = Params()\n",
    "    self.params = Params()\n    self._acb_need_resume = False\n",
    1,
  )
  old = """    CC.cruiseControl.resume = CC.enabled and CS.cruiseState.standstill and (
      not self.sm['longitudinalPlan'].shouldStop or legacy_resume_hack
    )
"""
  new = old + """
    try:
      acb_on = int(self.params.get("ActivateCruiseAfterBrake") or 0) == 1
    except Exception:
      acb_on = False
    if acb_on:
      if CS.brakePressed and (CC.enabled or CS.cruiseState.enabled):
        self._acb_need_resume = True
      if self._acb_need_resume and not CS.brakePressed and CS.cruiseState.available:
        CC.cruiseControl.resume = True
        if CS.cruiseState.enabled:
          self._acb_need_resume = False
"""
  if old not in t:
    raise SystemExit("controlsd.py: resume block not found")
  t = t.replace(old, new, 1)
  p.write_text(t, encoding="utf-8")
  print("patched controlsd.py")
else:
  print("controlsd.py already has ACB")

# --- carstate CAN parsers ---
p, t = must_read("opendbc_repo/opendbc/car/volkswagen/carstate.py")
if "import math" not in t:
  t = "import math\n" + t
old_kombi = '        self.upscale_lead_car_signal = bool(pt_cp.vl["Kombi_03"]["KBI_Variante"])  # Analog vs digital instrument cluster'
new_kombi = '''        try:
          self.upscale_lead_car_signal = bool(pt_cp.vl["Kombi_03"]["KBI_Variante"])  # Analog vs digital instrument cluster
        except Exception:
          self.upscale_lead_car_signal = False'''
if old_kombi in t:
  t = t.replace(old_kombi, new_kombi, 1)

old_parsers = '''    # manually configure some optional and variable-rate/edge-triggered messages
    pt_messages, cam_messages = [], []

    if not CP.flags & VolkswagenFlags.MLB:
      pt_messages += [
        ("Blinkmodi_02", 1)  # From J519 BCM (sent at 1Hz when no lights active, 50Hz when active)
      ]
    if CP.flags & VolkswagenFlags.STOCK_HCA_PRESENT:
      cam_messages += [
        ("HCA_01", 1),  # From R242 Driver assistance camera, 50Hz if steering/1Hz if not
      ]

    return {
      Bus.pt: CANParser(DBC[CP.carFingerprint][Bus.pt], pt_messages, CanBus(CP).pt),
      Bus.cam: CANParser(DBC[CP.carFingerprint][Bus.pt], cam_messages, CanBus(CP).cam),
    }
'''
new_parsers = '''    if CP.flags & VolkswagenFlags.MLB:
      pt_messages, cam_messages = [], []
      if CP.flags & VolkswagenFlags.STOCK_HCA_PRESENT:
        cam_messages += [
          ("HCA_01", 1),  # From R242 Driver assistance camera, 50Hz if steering/1Hz if not
        ]
      return {
        Bus.pt: CANParser(DBC[CP.carFingerprint][Bus.pt], pt_messages, CanBus(CP).pt),
        Bus.cam: CANParser(DBC[CP.carFingerprint][Bus.pt], cam_messages, CanBus(CP).cam),
      }

    # MQB (Jetta MK7): explicit lists. This fork's CANParser lazy-adds via vl[] and then
    # times out missing optional frames (Kombi_03, radar on the other bus) -> canError.
    # Kombi_03 nan => ignore_alive (freq 0 is NOT optional here).
    pt_messages = [
      ("LWI_01", 100),
      ("LH_EPS_03", 100),
      ("ESP_19", 100),
      ("ESP_05", 50),
      ("ESP_21", 50),
      ("Motor_20", 50),
      ("TSK_06", 50),
      ("ESP_02", 50),
      ("GRA_ACC_01", 33),
      ("Gateway_73", 20),
      ("Gateway_72", 10),
      ("Motor_14", 10),
      ("Airbag_02", 5),
      ("Kombi_01", 2),
      ("Blinkmodi_02", 1),
      ("Kombi_03", math.nan),
    ]
    if CP.transmissionType == TransmissionType.direct:
      pt_messages.append(("Motor_EV_01", 10))
    if CP.networkLocation == NetworkLocation.fwdCamera:
      pt_messages += MqbExtraSignals.fwd_radar_messages
      if CP.enableBsm:
        pt_messages += MqbExtraSignals.bsm_radar_messages

    cam_messages = []
    if CP.flags & VolkswagenFlags.STOCK_HCA_PRESENT:
      cam_messages += [
        ("HCA_01", 1),  # From R242 Driver assistance camera, 50Hz if steering/1Hz if not
      ]
    if CP.networkLocation == NetworkLocation.fwdCamera:
      cam_messages += [("LDW_02", 10)]
    else:
      cam_messages += MqbExtraSignals.fwd_radar_messages
      if CP.enableBsm:
        cam_messages += MqbExtraSignals.bsm_radar_messages

    return {
      Bus.pt: CANParser(DBC[CP.carFingerprint][Bus.pt], pt_messages, CanBus(CP).pt),
      Bus.cam: CANParser(DBC[CP.carFingerprint][Bus.pt], cam_messages, CanBus(CP).cam),
    }
'''
if '("ESP_19", 100)' not in t:
  if old_parsers not in t:
    raise SystemExit("carstate.py: original get_can_parsers block not found")
  t = t.replace(old_parsers, new_parsers, 1)
if "class MqbExtraSignals" not in t:
  t = t.rstrip() + """

class MqbExtraSignals:
  fwd_radar_messages = [("ACC_06", 50), ("ACC_10", 50), ("ACC_02", 17)]
  bsm_radar_messages = [("SWA_01", 20)]
"""
p.write_text(t, encoding="utf-8")
print("patched carstate.py")
print("DONE")
