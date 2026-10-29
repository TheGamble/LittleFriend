# hardware/dial.py
import threading
import time
from typing import Any
import config

MCP3008: Any = None
if config.IS_PI:
    from gpiozero import MCP3008  # type: ignore


class VolumeDial:

    def __init__(self, on_volume_change, channel=0):
        self.on_volume_change = on_volume_change
        self.last_volume = -1
        self.running = False
        self.channel = channel
        self.pot: Any = None

        if config.IS_PI and MCP3008 is not None:
            self.pot = MCP3008(channel=self.channel)

    def start(self):
        if not config.IS_PI or self.pot is None:
            return
        self.running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _monitor_loop(self):
        while self.running:
            if self.pot is None:
                break
            raw_val = self.pot.value
            current_volume = int(round(raw_val * 100))

            if abs(current_volume - self.last_volume) >= 2:
                self.last_volume = current_volume
                self.on_volume_change(current_volume)

            time.sleep(0.05)

    def stop(self):
        self.running = False