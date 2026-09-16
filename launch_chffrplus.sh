#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

source "$DIR/launch_env.sh"

# Hardcode Volkswagen Jetta MK7 so car selection cannot drift.
export FINGERPRINT="${FINGERPRINT:-VOLKSWAGEN_JETTA_MK7}"
export SKIP_FW_QUERY="${SKIP_FW_QUERY:-1}"

export SP_BOOT_TIMING_LOG="${SP_BOOT_TIMING_LOG:-/tmp/starpilot_boot_timing.log}"
: > "$SP_BOOT_TIMING_LOG" 2>/dev/null || true
SP_LAUNCH_LAST_SECONDS=$SECONDS

function sp_boot_timing_line {
  echo "$1"
  printf '%s\n' "$1" >> "$SP_BOOT_TIMING_LOG" 2>/dev/null || true
}

function sp_launch_timing {
  local now=$SECONDS
  local delta=$((now - SP_LAUNCH_LAST_SECONDS))
  sp_boot_timing_line "SP_BOOT_TIMING launch $1 +${delta}s total=${now}s"
  SP_LAUNCH_LAST_SECONDS=$now
}

function agnos_init {
  sp_launch_timing "agnos_init_start"

  # TODO: move this to agnos
  sudo rm -f /data/etc/NetworkManager/system-connections/*.nmmeta

  # set success flag for current boot slot
  sudo abctl --set_success

  # Restore SSH access after a user-triggered reset if keys were backed up to /cache.
  SSH_BACKUP_DIR="/cache/reset_backup"
  if [ -d "$SSH_BACKUP_DIR" ]; then
    sudo mkdir -p /data/params/d
    for key in GithubSshKeys SshEnabled; do
      if [ -f "$SSH_BACKUP_DIR/$key" ]; then
        sudo cp "$SSH_BACKUP_DIR/$key" "/data/params/d/$key"
      fi
    done
    sudo chown comma:comma /data/params/d/GithubSshKeys /data/params/d/SshEnabled 2>/dev/null || true
    sudo chmod 600 /data/params/d/GithubSshKeys /data/params/d/SshEnabled 2>/dev/null || true
    sudo rm -rf "$SSH_BACKUP_DIR"
  fi

  # Seed SSH as GitHub user dakexiaoxu so a reset cannot wipe authorized_keys.
  SSH_KEYS_SRC="$DIR/tools/scripts/dakexiaoxu.keys"
  if [ -f "$SSH_KEYS_SRC" ]; then
    sudo mkdir -p /data/params/d
    printf '%s' 'dakexiaoxu' | sudo tee /data/params/d/GithubUsername >/dev/null
    sudo cp "$SSH_KEYS_SRC" /data/params/d/GithubSshKeys
    printf '1' | sudo tee /data/params/d/SshEnabled >/dev/null
    sudo chown comma:comma /data/params/d/GithubSshKeys /data/params/d/GithubUsername /data/params/d/SshEnabled 2>/dev/null || true
    sudo chmod 600 /data/params/d/GithubSshKeys /data/params/d/SshEnabled 2>/dev/null || true
  fi

  # Full-time lane keep + resume-cruise-after-brake + MK7 fingerprint must survive reboot/reset.
  sudo mkdir -p /data/params/d
  printf '1' | sudo tee /data/params/d/AlwaysOnLateral >/dev/null
  printf '1' | sudo tee /data/params/d/AlwaysOnLateralLKAS >/dev/null
  printf '1' | sudo tee /data/params/d/ActivateCruiseAfterBrake >/dev/null
  printf '1' | sudo tee /data/params/d/ForceFingerprint >/dev/null
  printf '1' | sudo tee /data/params/d/LaneChanges >/dev/null
  printf '1' | sudo tee /data/params/d/NudgelessLaneChange >/dev/null
  printf '0' | sudo tee /data/params/d/PauseAOLOnBrake >/dev/null
  printf '%s' 'VOLKSWAGEN_JETTA_MK7' | sudo tee /data/params/d/CarModel >/dev/null
  # Chinese UI + metric units must survive reboot. Do not leave these files missing.
  printf '%s' 'main_zh-CHS' | sudo tee /data/params/d/LanguageSetting >/dev/null
  printf '1' | sudo tee /data/params/d/IsMetric >/dev/null
  # Jetta MK7 has a dedicated NNFF torque model; RDF V4 is the current StarPilot driving model.
  printf '1' | sudo tee /data/params/d/NNFF >/dev/null
  printf '0' | sudo tee /data/params/d/NNFFLite >/dev/null
  printf '1' | sudo tee /data/params/d/LateralTune >/dev/null
  # Jetta J533 splice: never enable OP long. Alpha Long TX of ACC faults TSK
  # (Cruise Fault). Stock ACC + GRA resume-after-brake still work.
  printf '0' | sudo tee /data/params/d/AlphaLongitudinalEnabled >/dev/null
  printf '1' | sudo tee /data/params/d/DisableOpenpilotLongitudinal >/dev/null
  if [ ! -s /data/params/d/DrivingModel ]; then
    printf '%s' 'rdf43' | sudo tee /data/params/d/DrivingModel >/dev/null
    printf '%s' 'rdf43' | sudo tee /data/params/d/Model >/dev/null
    printf '%s' 'Regret Driven Framework V4' | sudo tee /data/params/d/DrivingModelName >/dev/null
    printf '%s' 'v15' | sudo tee /data/params/d/DrivingModelVersion >/dev/null
    printf '%s' 'v15' | sudo tee /data/params/d/ModelVersion >/dev/null
  fi
  sudo chown comma:comma \
    /data/params/d/AlwaysOnLateral \
    /data/params/d/AlwaysOnLateralLKAS \
    /data/params/d/ActivateCruiseAfterBrake \
    /data/params/d/ForceFingerprint \
    /data/params/d/LaneChanges \
    /data/params/d/NudgelessLaneChange \
    /data/params/d/PauseAOLOnBrake \
    /data/params/d/CarModel \
    /data/params/d/LanguageSetting \
    /data/params/d/IsMetric \
    /data/params/d/NNFF \
    /data/params/d/NNFFLite \
    /data/params/d/LateralTune \
    /data/params/d/AlphaLongitudinalEnabled \
    /data/params/d/DisableOpenpilotLongitudinal \
    /data/params/d/DrivingModel \
    /data/params/d/Model \
    /data/params/d/DrivingModelName \
    /data/params/d/DrivingModelVersion \
    /data/params/d/ModelVersion 2>/dev/null || true

  # TODO: do this without udev in AGNOS
  # udev does this, but sometimes we startup faster
  sudo chgrp gpu /dev/adsprpc-smd /dev/ion /dev/kgsl-3d0
  sudo chmod 660 /dev/adsprpc-smd /dev/ion /dev/kgsl-3d0

  # StarPilot variables
  sudo chmod 0777 /cache

  # Never flash AGNOS from this tree. Carrot 19.6.3 hanging on updater looks like a frozen comma logo.
  AGNOS_CURRENT_VERSION="$(< /VERSION)"
  AGNOS_UPDATE_REQUIRED=0
  sp_boot_timing_line "skip_agnos_update current=${AGNOS_CURRENT_VERSION}"

  sp_launch_timing "agnos_init_done"
}

function launch {
  sp_launch_timing "launch_start"

  # Remove orphaned git lock if it exists on boot
  [ -f "$DIR/.git/index.lock" ] && rm -f $DIR/.git/index.lock

  # Check to see if there's a valid overlay-based update available. Conditions
  # are as follows:
  #
  # 1. The DIR init file has to exist, with a newer modtime than anything in
  #    the DIR Git repo. This checks for local development work or the user
  #    switching branches/forks, which should not be overwritten.
  # 2. The FINALIZED consistent file has to exist, indicating there's an update
  #    that completed successfully and synced to disk.

  if [ -f "${DIR}/.overlay_init" ]; then
    find ${DIR}/.git -newer ${DIR}/.overlay_init | grep -q '.' 2> /dev/null
    if [ $? -eq 0 ]; then
      echo "${DIR} has been modified, skipping overlay update installation"
    else
      if [ -f "${STAGING_ROOT}/finalized/.overlay_consistent" ]; then
        if [ ! -d /data/safe_staging/old_openpilot ]; then
          echo "Valid overlay update found, installing"
          LAUNCHER_LOCATION="${BASH_SOURCE[0]}"

          mv $DIR /data/safe_staging/old_openpilot
          mv "${STAGING_ROOT}/finalized" $DIR
          cd $DIR

          echo "Restarting launch script ${LAUNCHER_LOCATION}"
          unset AGNOS_VERSION
          exec "${LAUNCHER_LOCATION}"
        else
          echo "openpilot backup found, not updating"
          # TODO: restore backup? This means the updater didn't start after swapping
        fi
      fi
    fi
  fi
  sp_launch_timing "overlay_check_done"

  # handle pythonpath
  ln -sfn $(pwd) /data/pythonpath
  export BASEDIR="$DIR"
  export PYTHONPATH="$DIR/starpilot/third_party:$PWD"
  sp_launch_timing "pythonpath_done"

  function start_amap_carrot_bridge {
    local watchdog_script="$DIR/scripts/amap_carrot_watchdog.sh"
    local pid_file="${AMAP_CARROT_PID_FILE:-/tmp/amap_carrot_watchdog.pid}"
    local py_bin
    [ -f "$watchdog_script" ] || return
    if command -v pgrep >/dev/null 2>&1 && pgrep -f '[a]map_carrot_watchdog[.]sh' >/dev/null 2>&1; then
      return
    fi
    if [ -f "$pid_file" ]; then
      local old_pid
      old_pid="$(cat "$pid_file" 2>/dev/null || true)"
      if [ -n "$old_pid" ] && kill -0 "$old_pid" >/dev/null 2>&1; then
        return
      fi
    fi
    py_bin="$(command -v python3 || command -v python || true)"
    [ -n "$py_bin" ] || return
    echo "Starting Amap/Carrot navi bridge on 7000 and 7713."
    if command -v setsid >/dev/null 2>&1; then
      setsid bash "$watchdog_script" "$DIR" "$py_bin" >> /tmp/amap_carrot_bridge.log 2>&1 &
    else
      bash "$watchdog_script" "$DIR" "$py_bin" >> /tmp/amap_carrot_bridge.log 2>&1 &
    fi
  }
  start_amap_carrot_bridge
  if command -v iptables >/dev/null 2>&1; then
    sudo iptables -C INPUT -p tcp --dport 8082 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT -p tcp --dport 8082 -j ACCEPT
    sudo iptables -C INPUT -p tcp --dport 7000 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT -p tcp --dport 7000 -j ACCEPT
    sudo iptables -C INPUT -p tcp --dport 7713 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT -p tcp --dport 7713 -j ACCEPT
    sudo iptables -C INPUT -p udp --dport 7706 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT -p udp --dport 7706 -j ACCEPT
    sudo iptables -C INPUT -p udp --dport 7705 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT -p udp --dport 7705 -j ACCEPT
  fi

  # hardware specific init
  if [ -f /AGNOS ]; then
    agnos_init
  fi
  sp_launch_timing "hardware_init_done"

  # write tmux scrollback to a file
  tmux capture-pane -pq -S-1000 > /tmp/launch_log
  sp_launch_timing "capture_launch_log_done"

  # start manager
  cd system/manager

  sp_launch_timing "launch_param_migrations_start"
  if ! python3 ./launch_param_migrations.py; then
    echo "Launch param migrations failed; continuing boot."
  fi
  sp_launch_timing "launch_param_migrations_done"

  # Bootstrap runtime (e.g. /usr/comma after reset/uninstall) must go straight
  # to manager/setup flow. Do not run StarPilot prebuilt checks/builds here.
  if [ "$DIR" = "/usr/comma" ] || [ ! -d "$DIR/.git" ]; then
    sp_launch_timing "bootstrap_manager_start"
    ./manager.py
    while true; do sleep 1; done
  fi

  sp_launch_timing "prebuilt_decision_done"
  # Published trees carry this marker and must never compile on-device.
  # Developers can remove it explicitly when working from a source tree.
  if [ ! -f "$DIR/prebuilt" ]; then
    sp_launch_timing "build_start"
    ./build.py
    sp_launch_timing "build_done"
  fi
  sp_launch_timing "manager_start"
  ./manager.py

  # if broken, keep on screen error
  while true; do sleep 1; done
}

launch
