import json
import os
import tempfile
import time
import config


class StateManager:

    def __init__(self, filepath=config.STATE_FILE):
        self.filepath = filepath
        self.data = self._load()
        self.last_save_time = 0

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[State] Corrupt state file, resetting: {e}")
        return {"active_show": None, "shows": {}}

    def save(self, force=False):
        now = time.time()
        if not force and (now - self.last_save_time < config.AUTO_SAVE_INTERVAL_SECS):
            return

        # Atomic write to protect against power cut mid-write
        dir_name = os.path.dirname(self.filepath) or "."
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False) as tf:
            json.dump(self.data, tf, indent=2)
            temp_name = tf.name

        os.replace(temp_name, self.filepath)
        self.last_save_time = now

    def update_progress(self, show_name, season_num, ep_filename, position_ms):
        if show_name not in self.data["shows"]:
            self.data["shows"][show_name] = {}

        self.data["active_show"] = show_name
        self.data["shows"][show_name]["season"] = season_num
        self.data["shows"][show_name]["episode"] = ep_filename
        self.data["shows"][show_name]["position_ms"] = position_ms
        self.save()

    def get_last_position(self, show_name):
        show_data = self.data["shows"].get(show_name, {})
        return (
            show_data.get("season"),
            show_data.get("episode"),
            show_data.get("position_ms", 0),
        )