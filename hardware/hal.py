# hardware/hal.py
from typing import Any
import config

power_button: Any = None

if config.IS_PI:
    try:
        from gpiozero import Button

        # hold_time=3 satisfies the gpiozero integer type signature
        power_button = Button(config.PIN_POWER_BUTTON, hold_time=3)
        print(f"[HAL] Button initialized on GPIO {config.PIN_POWER_BUTTON}")
    except Exception as e:
        print(f"[HAL Warning] Could not initialize GPIO button: {e}")
        power_button = None
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