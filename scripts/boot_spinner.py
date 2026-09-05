#!/usr/bin/env python3
"""Keep the comma splash spinning before SCons starts.

launch_chffrplus.sh writes /tmp/boot_status_line. This process feeds that text
to the existing UI spinner and exits when /tmp/boot_spinner.stop appears.
A fifo is not used: a dead UI must not block the launch script.
"""
import os
import time

from openpilot.common.spinner import Spinner

STATUS_PATH = "/tmp/boot_status_line"
STOP_PATH = "/tmp/boot_spinner.stop"


def main() -> None:
  spinner = Spinner()
  last = ""
  spinner.update("Starting openpilot. Keep power on.")
  while not os.path.exists(STOP_PATH):
    try:
      with open(STATUS_PATH, encoding="utf-8") as f:
        msg = f.read().strip()
    except OSError:
      msg = ""
    if msg and msg != last:
      spinner.update(msg)
      last = msg
    time.sleep(0.3)
  spinner.close()


if __name__ == "__main__":
  main()
