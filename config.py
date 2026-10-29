# config.py
import os
import sys

# Platform detection
IS_PI = sys.platform.startswith("linux") and (
    os.path.exists("/proc/device-tree/model")
    or "arm" in os.uname().machine
    or "aarch64" in os.uname().machine
)

# Display settings
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
FPS = 30

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = "/video" if IS_PI else os.path.join(BASE_DIR, "test_media")

# Store state on the journaled ext4 home partition (power-cut safe)
STATE_FILE = os.path.expanduser("~/.littlefriend_state.json")

# Hardware Pins
PIN_POWER_BUTTON = 26

# Behavior settings
SEEK_FORWARD_SECS = 30
SEEK_BACKWARD_SECS = 15
INTRO_SKIP_SECS = 45
AUTO_SAVE_INTERVAL_SECS = 5
CREDITS_CUTOFF_SECS = 20

# Web UI
WEB_PORT = 80 if IS_PI else 8080