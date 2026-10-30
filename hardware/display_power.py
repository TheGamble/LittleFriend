# hardware/display_power.py
import os
import subprocess
import config


class DisplayPower:

    @staticmethod
    def set_backlight(enabled: bool):
        """Turns the physical LCD backlight on or off."""
        if not config.IS_PI:
            print(f"[Display] Backlight: {'ON' if enabled else 'OFF'}")
            return

        # 1. Standard Linux sysfs backlight interface
        bl_path = "/sys/class/backlight/rpi_backlight/bl_power"
        if os.path.exists(bl_path):
            try:
                with open(bl_path, "w") as f:
                    # 0 = on, 1 = off in Linux backlight sysfs
                    f.write("0" if enabled else "1")
                return
            except Exception:
                pass

        # 2. Raspberry Pi display power toggle fallback
        cmd = ["vcgencmd", "display_power", "1" if enabled else "0"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)