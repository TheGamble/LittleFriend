# core/library.py
import config
import os
import re


class Episode:

    def __init__(self, title, path, season_num, ep_num):
        self.title = title
        self.path = path
        self.season = season_num
        self.episode = ep_num


class Library:

    def __init__(self, media_dir=config.MEDIA_DIR):
        self.media_dir = media_dir
        self.catalog = {}  # { "Friends": { 1: [Episode, ...], 2: [...] } }
        self.scan()

    def scan(self):
        self.catalog.clear()
        if not os.path.exists(self.media_dir):
            return

        for show_name in sorted(os.listdir(self.media_dir)):
            show_path = os.path.join(self.media_dir, show_name)
            if not os.path.isdir(show_path) or show_name.startswith("."):
                continue

            seasons_dict = {}

            # Scan seasons
            for season_entry in sorted(os.listdir(show_path)):
                season_path = os.path.join(show_path, season_entry)
                if not os.path.isdir(season_path):
                    continue

                # Match "Season 01", "Season 1", "S1", etc.
                match = re.search(r"(?:Season|S)\s*(\d+)", season_entry, re.I)
                season_num = int(match.group(1)) if match else 1

                episodes = []
                for file in sorted(os.listdir(season_path)):
                    if file.lower().endswith((".mp4", ".mkv", ".avi", ".mov")):
                        ep_match = re.search(r"[Ee](\d+)", file)
                        ep_num = (
                            int(ep_match.group(1))
                            if ep_match
                            else len(episodes) + 1
                        )
                        title = os.path.splitext(file)[0]
                        episodes.append(
                            Episode(
                                title,
                                os.path.join(season_path, file),
                                season_num,
                                ep_num,
                            )
                        )

                if episodes:
                    seasons_dict[season_num] = episodes

            # Only register the show if it actually contains playable episodes
            if seasons_dict:
                self.catalog[show_name] = seasons_dict