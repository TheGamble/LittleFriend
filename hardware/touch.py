# hardware/touch.py
import glob
import threading
import time
from evdev import InputDevice, ecodes
import config


class TouchController:

    def __init__(self, on_gesture):
        self.on_gesture = on_gesture
        self.running = False
        self.device = self._find_touch_device()

    def _find_touch_device(self):
        """Finds the Waveshare Goodix capacitive touch event device."""
        if not config.IS_PI:
            return None

        devices = glob.glob("/dev/input/event*")
        for path in sorted(devices):
            try:
                dev = InputDevice(path)
                name_lower = dev.name.lower()
                # Match Goodix or generic touch devices directly
                if "goodix" in name_lower or "touch" in name_lower:
                    print(
                        f"[Touch] Successfully bound to: {dev.name} ({path})"
                    )
                    return dev
            except Exception as e:
                print(f"[Touch Debug] Error inspecting {path}: {e}")

        print("[Touch Warning] No capacitive touch device found.")
        return None

    def start(self):
        if not self.device:
            return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        dev = self.device
        if not dev:
            return

        start_x, start_y = None, None
        current_x, current_y = 0, 0
        touch_start_time = 0
        touching = False
        num_fingers = 1

        for event in dev.read_loop():
            if not self.running:
                break

            # Multi-touch tracking ID
            if (
                event.type == ecodes.EV_ABS
                and event.code == ecodes.ABS_MT_TRACKING_ID
            ):
                if event.value != -1:  # Finger Down
                    touching = True
                    touch_start_time = time.time()
                    start_x, start_y = None, None
                else:  # Finger Up
                    if touching and start_x is not None and start_y is not None:
                        touching = False
                        self._process_gesture(
                            start_x,
                            start_y,
                            current_x,
                            current_y,
                            time.time() - touch_start_time,
                            num_fingers,
                        )
                    touching = False
                    start_x, start_y = None, None
                    num_fingers = 1

            # Multi-touch slot (count fingers)
            elif (
                event.type == ecodes.EV_ABS and event.code == ecodes.ABS_MT_SLOT
            ):
                num_fingers = max(num_fingers, event.value + 1)

            # Coordinate updates
            elif event.type == ecodes.EV_ABS:
                if event.code in (ecodes.ABS_MT_POSITION_X, ecodes.ABS_X):
                    current_x = event.value
                    if start_x is None:
                        start_x = current_x
                elif event.code in (ecodes.ABS_MT_POSITION_Y, ecodes.ABS_Y):
                    current_y = event.value
                    if start_y is None:
                        start_y = current_y

    def _process_gesture(self, x1, y1, x2, y2, duration, fingers):
        dx = x2 - x1
        dy = y2 - y1
        dist_sq = dx * dx + dy * dy

        print(
            f"[Touch Debug] Raw dx={dx}, dy={dy}, dist={int(dist_sq**0.5)}, dur={duration:.2f}s, fingers={fingers}"
        )

        # 1. Swipes (Distance > 50px under 0.45s)
        # Note: Because the screen was rotated 90 degrees in X11,
        # moving horizontally on the landscape TV corresponds to dy in the Goodix hardware!
        if dist_sq > 2500 and duration < 0.45:
            if abs(dy) > abs(dx):
                # Horizontal swipe across the 640px landscape dimension
                if fingers > 1:
                    self.on_gesture("season_next" if dy < 0 else "season_prev")
                else:
                    self.on_gesture(
                        "episode_next" if dy < 0 else "episode_prev"
                    )
            else:
                # Vertical swipe across the 480px landscape dimension (Channel Surf)
                if fingers > 1:
                    self.on_gesture("season_next" if dx < 0 else "season_prev")
                else:
                    self.on_gesture(
                        "channel_next" if dx < 0 else "channel_prev"
                    )
            return

        # 2. Taps (Quick release under 0.35s with minimal travel)
        if duration < 0.35 and dist_sq < 1600:
            # Tap zones mapped to landscape (dy represents horizontal position)
            # Center tap toggles pause
            if y2 < 120:
                self.on_gesture("seek_backward")
            elif y2 > 520:
                self.on_gesture("seek_forward")
            else:
                self.on_gesture("toggle_pause")