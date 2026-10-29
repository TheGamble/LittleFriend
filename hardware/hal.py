# hardware/hal.py
from typing import Any
import config

power_button: Any = None

if config.IS_PI:
    from gpiozero import Button

    # hold_time as int (3) satisfies gpiozero type definition
    power_button = Button(config.PIN_POWER_BUTTON, hold_time=3)
else:
    print(
        "[HAL] Running on Desktop: Keyboard controls active (Space=Power/Sleep,"
        " Up/Down=Vol)"
    )


def setup_hardware_callbacks(
    on_sleep_toggle, on_shutdown, on_volume_change
):
    if config.IS_PI and power_button is not None:
        power_button.when_activated = on_sleep_toggle
        power_button.when_held = on_shutdown