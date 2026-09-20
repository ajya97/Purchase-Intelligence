from pathlib import Path

from flask import Flask, jsonify, render_template, request

from app.routes import main

# templates/ and static/ live at the project root (next to run.py), not inside the app/ package,
# so Flask has to be told where they are.
BASE_DIR = Path(__file__).resolve().parent.parent


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # a prediction request is well under 2 KB
    app.json.sort_keys = False  # keep keys in the order we define them

    app.register_blueprint(main)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def _error(status: int, message: str):
        """JSON for /api/*, the friendly home page for everything else."""
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": message}), status
        from app.routes import render_home
        return render_home(error=message), status

    @app.errorhandler(404)
    def not_found(_e):
        return _error(404, "That page or endpoint doesn't exist.")

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return _error(405, "That method isn't allowed for this address.")

    @app.errorhandler(413)
    def too_large(_e):
        return _error(413, "The request was too large.")

    @app.errorhandler(500)
    def server_error(_e):
        return _error(500, "Something went wrong on the server. Please try again.")

    return app
