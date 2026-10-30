# web/server.py
import json
import os
from typing import Any
import config
from bottle import Bottle, request, response, static_file


def start_web_server(app_state):
    """Runs the companion web server in a background thread."""
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
        player = app_state.player
        return json.dumps({
            "show": app_state.current_show,
            "season": app_state.current_season,
            "is_playing": not player.is_paused(),
            "position_ms": player.get_time(),
            "duration_ms": player.get_duration(),
        })

    @app.route("/api/library")
    def api_library():
        response.content_type = "application/json"
        catalog_data = {}
        for show, seasons in app_state.library.catalog.items():
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
        player = app_state.player

        if action == "play":
            player.resume()
        elif action == "pause":
            player.pause()
        elif action == "toggle":
            player.toggle_pause()
        elif action == "skip_intro":
            player.seek(config.INTRO_SKIP_SECS)
        elif action == "seek_forward":
            player.seek(config.SEEK_FORWARD_SECS)
        elif action == "seek_backward":
            player.seek(-config.SEEK_BACKWARD_SECS)
        return {"status": "ok"}

    @app.route("/api/play_episode", method="POST")
    def api_play_episode():
        req: Any = request
        data = req.json or {}
        show = data.get("show")
        season = int(data.get("season", 1))
        title = data.get("title")

        if show and title:
            app_state.play_specific_episode(show, season, title)
            return {"status": "ok"}
        return {"status": "error", "message": "Invalid parameters"}

    print(f"[Web] Attempting to start server on port {config.WEB_PORT}...")
    try:
        app.run(host="0.0.0.0", port=config.WEB_PORT, quiet=True)
    except PermissionError:
        print(f"[Web] Port {config.WEB_PORT} restricted. Falling back to 8080...")
        app.run(host="0.0.0.0", port=8080, quiet=True)
    except Exception as e:
        print(f"[Web Error] Could not start server: {e}")