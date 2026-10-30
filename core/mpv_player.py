# core/mpv_client.py
import json
import os
import socket
import time

SOCKET_PATH = "/tmp/mpv.sock"


class MPVClient:

    def __init__(self, socket_path=SOCKET_PATH):
        self.socket_path = socket_path
        self.sock = None

    def connect(self, timeout=10.0):
        """Waits for MPV's IPC socket to appear and connects."""
        start = time.time()
        while time.time() - start < timeout:
            if os.path.exists(self.socket_path):
                try:
                    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self.sock.connect(self.socket_path)
                    print(f"[MPV] Connected to IPC socket at {self.socket_path}")
                    return True
                except Exception:
                    pass
            time.sleep(0.2)
        print("[MPV Error] Could not connect to IPC socket (timed out)")
        return False

    def send(self, command: list):
        """Sends a JSON-IPC command to MPV and returns the response."""
        if not self.sock:
            return None
        try:
            payload = json.dumps({"command": command}) + "\n"
            self.sock.sendall(payload.encode("utf-8"))
            # Read single-line response
            data = self.sock.recv(4096).decode("utf-8")
            if data:
                return json.loads(data.split("\n")[0])
        except Exception as e:
            print(f"[MPV Socket Error] {e}")
            self.sock = None
        return None

    # --- Core Controls ---

    def load_file(self, filepath: str, start_sec: float | int = 0):
        if start_sec > 0:
            # MPV 0.38+ syntax: loadfile <file> <flags> <index> <options>
            return self.send(
                ["loadfile", filepath, "replace", 0, f"start={int(start_sec)}"]
            )
        return self.send(["loadfile", filepath, "replace"])

    def toggle_pause(self):
        return self.send(["cycle", "pause"])

    def pause(self):
        return self.send(["set_property", "pause", True])

    def resume(self):
        return self.send(["set_property", "pause", False])

    def seek(self, seconds_relative):
        return self.send(["seek", seconds_relative, "relative"])

    def show_banner(self, text, duration_ms=3000):
        """Pops up the TV-style banner on the screen."""
        return self.send(["show-text", text, duration_ms])

    # --- Properties ---

    def get_time(self):
        """Returns current playback position in milliseconds."""
        res = self.send(["get_property", "time-pos"])
        if res and res.get("data") is not None:
            return int(res["data"] * 1000)
        return 0

    def get_duration(self):
        """Returns total duration in milliseconds."""
        res = self.send(["get_property", "duration"])
        if res and res.get("data") is not None:
            return int(res["data"] * 1000)
        return 0

    def is_paused(self):
        res = self.send(["get_property", "pause"])
        if res and res.get("data") is not None:
            return bool(res["data"])
        return False