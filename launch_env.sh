#!/usr/bin/env bash

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1

# models get lower priority than ui
# - ui is ~5ms
# - modeld is 20ms
# - DM is 10ms
# in order to run ui at 60fps (16.67ms), we need to allow
# it to preempt the model workloads. we have enough
# headroom for this until ui is moved to the CPU.
export QCOM_PRIORITY=12

# Do not force AGNOS 19.6.3 on first boot. The GitHub installer hangs on the
# comma logo while agnos.py downloads from commadist.azureedge.net, which is
# unreachable for many C3 installs (VPN / China network). Boot on the AGNOS
# already on the device; eigen/libjpeg wheels cover the AGNOS 19 ABI gap.
if [ -z "$AGNOS_VERSION" ]; then
  if [ -f /VERSION ]; then
    export AGNOS_VERSION="$(tr -d '\000\r\n' < /VERSION)"
  else
    export AGNOS_VERSION="19.6.3-carrot"
  fi
fi

export STAGING_ROOT="/data/safe_staging"
