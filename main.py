# main.py
import os
import subprocess
import sys
import threading
import config
from core.library import Library
from core.player import VideoPlayer
from core.state import StateManager
from hardware.hal import setup_hardware_callbacks
import pygame
from ui.display import TouchUI
from web.server import start_web_server


def on_sleep_toggle():
    print("[Power] Sleep toggled.")
    ui.toggle_sleep()
    if ui.is_sleeping:
        threading.Thread(
            target=lambda: subprocess.run(
                ["/bin/bash", f"{config.BASE_DIR}/system/auto_update.sh"]
            ),
            daemon=True,
        ).start()


def on_shutdown():
    print("[Power] Safe shutdown initiated...")
    ui.show_shutdown_screen()
    if config.IS_PI:
        subprocess.run(["sudo", "systemctl", "poweroff"])


state = StateManager()
library = Library()
player = VideoPlayer()
ui = TouchUI(player, state, library)

setup_hardware_callbacks(on_sleep_toggle, on_shutdown, ui.adjust_volume)


def run_web_background():
    try:
        start_web_server(ui, player, state, library)
    except Exception as e:
        print(f"[Web] Thread exception: {e}")


web_thread = threading.Thread(target=run_web_background, daemon=True)
web_thread.start()

ui.start_playback()
ui.run()