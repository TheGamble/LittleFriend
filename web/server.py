# web/server.py
import json
import os
from typing import Any
import config
from bottle import Bottle, request, response, static_file


def start_web_server(ui, player, state, library):
    app: Any = Bottle()
    static_dir = os.path.join(config.BASE_DIR, "web", "static")

    @app.route("/")
    def index():
        if os.path.exists(os.path.join(static_dir, "index.html")):
            return static_file("index.html", root=static_dir)
        return "<h3>LittleFriend Web Companion</h3><p>Place index.html in web/static/</p>"

    @app.route("/static/<filename:path>")
    def serve_static(filename):
        return static_file(filename, root=static_dir)

    @app.route("/api/status")
    def api_status():
        response.content_type = "application/json"
        return json.dumps({
            "show": state.data.get("active_show"),
            "season": ui.browse_season,
            "is_playing": player.is_playing(),
            "position_ms": player.get_time(),
            "duration_ms": player.get_length(),
            "volume": player.get_volume(),
        })

    @app.route("/api/library")
    def api_library():
        response.content_type = "application/json"
        catalog_data = {}
        for show, seasons in library.catalog.items():
            catalog_data[show] = {
                str(season): [ep.title for ep in episodes]
                for season, episodes in seasons.items()
            }
        return json.dumps(catalog_data)

    @app.route("/api/control", method="POST")
    def api_control():
        req: Any = request
        payload = req.json or {}
        action = payload.get("action")
        if action == "play":
            player.play()
        elif action == "pause":
            player.pause()
        elif action == "toggle":
            player.toggle_pause()
        elif action == "skip_intro":
            player.seek_relative(config.INTRO_SKIP_SECS)
        elif action == "seek_forward":
            player.seek_relative(config.SEEK_FORWARD_SECS)
        elif action == "seek_backward":
            player.seek_relative(-config.SEEK_BACKWARD_SECS)
        elif action == "volume":
            vol = int(payload.get("value", 70))
            ui.adjust_volume(vol)
        return {"status": "ok"}

    @app.route("/api/play_episode", method="POST")
    def api_play_episode():
        req: Any = request
        data = req.json or {}
        show = data.get("show")
        season = int(data.get("season", 1))
        title = data.get("title")

        if show and title:
            ui.play_show_episode(show, season, title, start_ms=0)
            return {"status": "ok"}
        return {"status": "error", "message": "Invalid parameters"}

    print(f"[Web] Server listening on http://localhost:{config.WEB_PORT}")
    try:
        app.run(host="0.0.0.0", port=config.WEB_PORT, quiet=True)
    except Exception as e:
        print(f"[Web Error] Could not start server: {e}")