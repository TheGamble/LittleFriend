# hardware/button.py
from typing import Any
import config


class PowerButton:

    def __init__(self, on_sleep, on_shutdown):
        self.on_sleep = on_sleep
        self.on_shutdown = on_shutdown
        self.btn: Any = None

        if config.IS_PI:
            try:
                from gpiozero import Button

                self.btn = Button(
                    config.PIN_POWER_BUTTON,
                    pull_up=True,
                    bounce_time=0.2,
                    hold_time=3,
                )
                self.btn.when_activated = self.on_sleep
                self.btn.when_held = self.on_shutdown
                print(f"[Button] Active on GPIO {config.PIN_POWER_BUTTON}")
            except Exception as e:
                print(f"[Button Warning] Could not initialize GPIO button: {e}")