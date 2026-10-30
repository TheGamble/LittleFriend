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
        """Finds the Waveshare capacitive touch event device."""
        if not config.IS_PI:
            return None
        devices = glob.glob("/dev/input/event*")
        if not devices:
            print("[Touch Warning] No /dev/input/event* nodes exist.")
            return None

        for path in sorted(devices):
            try:
                dev = InputDevice(path)
                caps = dev.capabilities()
                # Check for absolute coordinate touch capabilities
                if ecodes.EV_ABS in caps:
                    abs_caps = caps[ecodes.EV_ABS]
                    if (
                        ecodes.ABS_X in abs_caps
                        or ecodes.ABS_MT_POSITION_X in abs_caps
                    ):
                        print(
                            f"[Touch] Bound to touch device: {dev.name} ({path})"
                        )
                        return dev
                print(
                    f"[Touch Debug] Skipped {path} ({dev.name}): Not a touch device"
                )
            except PermissionError:
                print(
                    f"[Touch Permission Error] User 'pi' cannot read {path}. Needs group 'input'."
                )
            except Exception as e:
                print(f"[Touch Debug] {path}: {e}")

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

        start_x, start_y = 0, 0
        current_x, current_y = 0, 0
        touch_start_time = 0
        touching = False
        num_fingers = 1

        for event in dev.read_loop():
            if not self.running:
                break

            # Multi-touch slot / tracking
            if (
                event.type == ecodes.EV_ABS
                and event.code == ecodes.ABS_MT_TRACKING_ID
            ):
                if event.value != -1:  # Touch Down
                    touching = True
                    touch_start_time = time.time()
                    start_x, start_y = current_x, current_y
                else:  # Touch Up
                    if touching:
                        touching = False
                        self._process_gesture(
                            start_x,
                            start_y,
                            current_x,
                            current_y,
                            time.time() - touch_start_time,
                            num_fingers,
                        )
                    num_fingers = 1

            elif (
                event.type == ecodes.EV_ABS and event.code == ecodes.ABS_MT_SLOT
            ):
                num_fingers = max(num_fingers, event.value + 1)

            # Coordinate updates
            elif event.type == ecodes.EV_ABS:
                if event.code in (ecodes.ABS_MT_POSITION_X, ecodes.ABS_X):
                    current_x = event.value
                elif event.code in (ecodes.ABS_MT_POSITION_Y, ecodes.ABS_Y):
                    current_y = event.value

    def _process_gesture(self, x1, y1, x2, y2, duration, fingers):
        dx = x2 - x1
        dy = y2 - y1
        dist_sq = dx * dx + dy * dy

        # 1. Swipes (Distance > 40px in under 0.4s)
        if dist_sq > 1600 and duration < 0.4:
            if abs(dx) > abs(dy):
                # Horizontal Swipe
                if fingers > 1:
                    self.on_gesture("season_next" if dx < 0 else "season_prev")
                else:
                    self.on_gesture("episode_next" if dx < 0 else "episode_prev")
            else:
                # Vertical Swipe (Channel Surf)
                if fingers > 1:
                    self.on_gesture("season_next" if dy < 0 else "season_prev")
                else:
                    self.on_gesture("channel_next" if dy < 0 else "channel_prev")
            return

        # 2. Taps (Quick release, minimal movement)
        if duration < 0.35 and dist_sq < 900:
            # Check edge zones for quick seek
            # Assuming normalized 640 width
            if x2 < 140:
                self.on_gesture("seek_backward")
            elif x2 > 500:
                self.on_gesture("seek_forward")
            else:
                self.on_gesture("toggle_pause")