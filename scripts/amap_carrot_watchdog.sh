#!/usr/bin/env bash
set -u

DIR="${1:-/data/openpilot}"
PY_BIN="${2:-$(command -v python3 || command -v python || true)}"
PID_FILE="${AMAP_CARROT_PID_FILE:-/tmp/amap_carrot_watchdog.pid}"
LOCK_FILE="${AMAP_CARROT_LOCK_FILE:-/tmp/amap_carrot_watchdog.lock}"
RESTART_DELAY="${AMAP_CARROT_RESTART_DELAY:-2}"

if [ -z "$PY_BIN" ]; then
  echo "[amap_carrot] python not found"
  exit 1
fi

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "[amap_carrot] another watchdog already holds ${LOCK_FILE}; exiting"
    exit 0
  fi
fi

existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -n "$existing_pid" ] && [ "$existing_pid" != "$$" ] && kill -0 "$existing_pid" >/dev/null 2>&1; then
  echo "[amap_carrot] watchdog pid ${existing_pid} is already running; exiting"
  exit 0
fi

cleanup() {
  current_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ "$current_pid" = "$$" ]; then
    rm -f "$PID_FILE"
  fi
}

printf '%s\n' "$$" > "$PID_FILE"
trap cleanup EXIT
trap 'exit 0' INT TERM

while true; do
  if ! cd -P -- "$DIR"; then
    echo "[amap_carrot] checkout unavailable at ${DIR}; retrying in ${RESTART_DELAY}s"
    sleep "$RESTART_DELAY"
    continue
  fi
  echo "[amap_carrot] starting navi bridge on 7000/7713"
  "$PY_BIN" -m openpilot.starpilot.navigation.amap_carrot_bridge
  rc=$?
  echo "[amap_carrot] bridge exited rc=${rc}; restarting in ${RESTART_DELAY}s"
  sleep "$RESTART_DELAY"
done
