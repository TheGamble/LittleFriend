# main.py
import os
import subprocess
import sys
import threading
import time
import config
from core.library import Library
from core.mpv_player import MPVClient
from core.state import StateManager
from hardware.button import PowerButton
from hardware.display_power import DisplayPower
from hardware.touch import TouchController
from web.server import start_web_server


class LittleFriendApp:

    def __init__(self):
        self.state = StateManager()
        self.library = Library()
        self.player = MPVClient()

        self.current_show = None
        self.current_season = 1
        self.current_ep_index = 0
        self.is_sleeping = False

        self.mpv_process = None

    def start_mpv_daemon(self):
        """Spawns the MPV process configured for hardware video and socket IPC."""
        # 1. Clean up old socket
        if os.path.exists(self.player.socket_path):
            try:
                os.remove(self.player.socket_path)
            except Exception:
                pass

        # 2. Native MPV command-line arguments
        mpv_cmd = [
            "mpv",
            "--idle=yes",
            f"--input-ipc-server={self.player.socket_path}",
            "--fullscreen",
            "--no-osd-bar",
            "--osd-duration=3000",
            "--osd-font-size=28",
            # Audio Mono Downmix
            "--ao=alsa",
            "--audio-channels=mono",
            # Disable MPV's desktop mouse shortcuts so touch.py has full control
            "--input-default-bindings=no",
            "--vo=gpu",
        ]

        print("[Main] Launching MPV hardware engine...")
        # Inherit stdout/stderr so any MPV messages print directly to the console
        self.mpv_process = subprocess.Popen(mpv_cmd)

        if not self.player.connect(timeout=10.0):
            print("[Main Error] Failed to connect to MPV engine.")
            sys.exit(1)

    def launch(self):
        """Initializes hardware, loads initial media, and starts threads."""
        self.start_mpv_daemon()

        # Initialize hardware controllers
        self.button = PowerButton(
            on_sleep=self.on_sleep_toggle, on_shutdown=self.on_shutdown
        )
        self.touch = TouchController(on_gesture=self.handle_gesture)
        self.touch.start()

        # Start web companion in background
        threading.Thread(
            target=start_web_server, args=(self,), daemon=True
        ).start()

        # Restore last watched episode from state
        if not self.library.catalog:
            print("[Main] No media found in /video")
            self.player.show_banner("NO MEDIA FOUND IN /video", 5000)
            return

        active_show = self.state.data.get("active_show")
        if not active_show or active_show not in self.library.catalog:
            active_show = list(self.library.catalog.keys())[0]

        season, ep_title, pos_ms = self.state.get_last_position(active_show)
        self.play_episode(active_show, season or 1, ep_title, start_ms=pos_ms)

    def play_episode(
        self, show_name, season_num, ep_identifier=None, start_ms=0
    ):
        seasons = self.library.catalog.get(show_name, {})
        episodes = seasons.get(season_num, [])

        if not episodes:
            if seasons:
                season_num = list(seasons.keys())[0]
                episodes = seasons[season_num]
            else:
                return

        target_idx = 0
        if ep_identifier:
            for i, ep in enumerate(episodes):
                if ep_identifier in (ep.title, ep.path):
                    target_idx = i
                    break

        target_ep = episodes[target_idx]
        self.current_show = show_name
        self.current_season = season_num
        self.current_ep_index = target_idx

        # Load file in MPV
        start_sec = start_ms / 1000.0 if start_ms > 0 else 0
        self.player.load_file(target_ep.path, start_sec=start_sec)

        # Show retro TV banner for 3 seconds
        show_idx = list(self.library.catalog.keys()).index(show_name) + 1
        banner_text = f"CH {show_idx:02d}: {show_name.upper()} • S{season_num:02d}E{target_ep.episode:02d} - {target_ep.title}"
        self.player.show_banner(banner_text, 3500)

        self.state.update_progress(
            show_name, season_num, target_ep.title, start_ms
        )

    def play_specific_episode(self, show_name, season_num, ep_title):
        self.play_episode(show_name, season_num, ep_title, start_ms=0)

    # --- Gesture Handling ---

    def handle_gesture(self, gesture):
        print(f"[Gesture] {gesture}")

        if gesture == "toggle_pause":
            self.player.toggle_pause()
            time.sleep(0.05)
            status = "PAUSED" if self.player.is_paused() else "PLAYING"
            self.player.show_banner(f"[ {status} ]", 1500)

        elif gesture == "seek_forward":
            self.player.seek(config.SEEK_FORWARD_SECS)
            self.player.show_banner(f">> +{config.SEEK_FORWARD_SECS}s", 1500)

        elif gesture == "seek_backward":
            self.player.seek(-config.SEEK_BACKWARD_SECS)
            self.player.show_banner(f"<< -{config.SEEK_BACKWARD_SECS}s", 1500)

        elif gesture == "channel_next":
            self.channel_surf(1)
        elif gesture == "channel_prev":
            self.channel_surf(-1)

        elif gesture == "episode_next":
            self.step_episode(1)
        elif gesture == "episode_prev":
            self.step_episode(-1)

        elif gesture == "season_next":
            self.step_season(1)
        elif gesture == "season_prev":
            self.step_season(-1)

    def channel_surf(self, direction):
        shows = list(self.library.catalog.keys())
        if not shows:
            return
        curr_idx = (
            shows.index(self.current_show)
            if self.current_show in shows
            else 0
        )
        new_show = shows[(curr_idx + direction) % len(shows)]
        season, ep_title, pos_ms = self.state.get_last_position(new_show)
        self.play_episode(new_show, season or 1, ep_title, start_ms=pos_ms)

    def step_episode(self, direction):
        episodes = self.library.catalog.get(self.current_show, {}).get(
            self.current_season, []
        )
        if not episodes:
            return
        new_idx = self.current_ep_index + direction
        if 0 <= new_idx < len(episodes):
            self.play_episode(
                self.current_show,
                self.current_season,
                episodes[new_idx].title,
                0,
            )
        elif new_idx >= len(episodes):
            # Advance to next season
            self.step_season(1)

    def step_season(self, direction):
        seasons = sorted(
            self.library.catalog.get(self.current_show, {}).keys()
        )
        if not seasons:
            return
        curr_idx = (
            seasons.index(self.current_season)
            if self.current_season in seasons
            else 0
        )
        new_season = seasons[(curr_idx + direction) % len(seasons)]
        self.play_episode(self.current_show, new_season, start_ms=0)

    # --- Power / Sleep ---

    def on_sleep_toggle(self):
        self.is_sleeping = not self.is_sleeping
        print(f"[Power] Sleep toggle: is_sleeping={self.is_sleeping}")

        if self.is_sleeping:
            # 1. Save progress and pause playback
            pos_ms = self.player.get_time()
            if pos_ms > 0 and self.current_show:
                episodes = self.library.catalog.get(self.current_show, {}).get(
                    self.current_season, []
                )
                if episodes:
                    self.state.update_progress(
                        self.current_show,
                        self.current_season,
                        episodes[self.current_ep_index].title,
                        pos_ms,
                    )
            self.player.pause()
            DisplayPower.set_backlight(False)

            # 2. Check for Git updates while screen is off
            threading.Thread(
                target=lambda: subprocess.run(
                    ["/bin/bash", f"{config.BASE_DIR}/system/auto_update.sh"]
                ),
                daemon=True,
            ).start()
        else:
            DisplayPower.set_backlight(True)
            self.player.resume()
            self.player.show_banner("[ RESUMED ]", 1500)

    def on_shutdown(self):
        print("[Power] Shutting down...")
        self.player.show_banner("GOODNIGHT...", 2000)
        time.sleep(1.0)
        DisplayPower.set_backlight(False)
        if config.IS_PI:
            subprocess.run(["sudo", "systemctl", "poweroff"])

    # --- Heartbeat Loop ---

    def run(self):
        print("[Main] Engine running.")
        last_save = time.time()

        while True:
            time.sleep(1.0)

            if self.is_sleeping:
                continue

            now = time.time()
            if now - last_save >= config.AUTO_SAVE_INTERVAL_SECS:
                last_save = now
                if not self.player.is_paused():
                    pos_ms = self.player.get_time()
                    dur_ms = self.player.get_duration()

                    # Periodic state save
                    if pos_ms > 0 and self.current_show:
                        episodes = self.library.catalog.get(
                            self.current_show, {}
                        ).get(self.current_season, [])
                        if episodes:
                            self.state.update_progress(
                                self.current_show,
                                self.current_season,
                                episodes[self.current_ep_index].title,
                                pos_ms,
                            )

                    # Auto-advance when reaching the end of an episode
                    if (
                        dur_ms > 0
                        and (dur_ms - pos_ms)
                        <= (config.CREDITS_CUTOFF_SECS * 1000)
                    ):
                        print("[Main] Episode ended. Auto-advancing...")
                        self.step_episode(1)


if __name__ == "__main__":
    app = LittleFriendApp()
    app.launch()
    app.run()