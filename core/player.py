# core/player.py
import os
import sys
import config
import vlc

os.environ["VLC_VERBOSE"] = "-1"


class VideoPlayer:

    def __init__(self):
        vlc_args = [
            "--no-osd",
            "--no-video-title-show",
            "--quiet",
            "--no-mouse-events",
            "--no-keyboard-events",
            "--aout=alsa",
            "--file-caching=1000",
        ]
        if config.IS_PI:
            vlc_args += ["--network-caching=500"]

        instance = vlc.Instance(*vlc_args)
        if instance is None:
            raise RuntimeError("Failed to initialize libVLC instance.")
        self.instance = instance

        player = self.instance.media_player_new()
        if player is None:
            raise RuntimeError("Failed to create libVLC media player.")
        self.player = player

        self.current_path = None
        self._window_id = None
        self.last_known_time = 0

    def set_window(self, window_id):
        self._window_id = window_id
        if sys.platform.startswith("linux"):
            self.player.set_xwindow(window_id)
        elif sys.platform == "win32":
            self.player.set_hwnd(window_id)
        elif sys.platform == "darwin":
            self.player.set_nsobject(window_id)

    def load_media(self, filepath, start_ms=0):
        self.current_path = filepath
        self.last_known_time = start_ms

        media = self.instance.media_new(filepath)
        if media is None:
            print(f"[Player] Failed to load media: {filepath}")
            return

        if start_ms > 0:
            start_sec = start_ms / 1000.0
            media.add_option(f":start-time={start_sec}")

        self.player.set_media(media)

        if self._window_id:
            self.set_window(self._window_id)

        self.player.play()

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def toggle_pause(self):
        """Toggles between play and pause states."""
        if self.is_playing():
            self.pause()
        else:
            self.play()

    def stop(self):
        t = self.get_time()
        if t > 0:
            self.last_known_time = t
        self.player.stop()

    def is_playing(self):
        return bool(self.player.is_playing())

    def get_time(self):
        t = self.player.get_time()
        if t > 0:
            self.last_known_time = t
            return t
        return self.last_known_time

    def get_length(self):
        l = self.player.get_length()
        return l if l > 0 else 0

    def seek_relative(self, seconds):
        curr = self.get_time()
        target = max(0, curr + (seconds * 1000))
        self.last_known_time = target
        self.player.set_time(int(target))

    def set_volume(self, volume_percent):
        self.player.audio_set_volume(max(0, min(100, volume_percent)))

    def get_volume(self):
        return self.player.audio_get_volume()

    def take_snapshot(self, filepath="/tmp/lf_snap.png"):
        """Captures frame at native aspect ratio (0, 0 prevents stretching)."""
        try:
            return self.player.video_take_snapshot(0, filepath, 0, 0) == 0
        except Exception:
            return False