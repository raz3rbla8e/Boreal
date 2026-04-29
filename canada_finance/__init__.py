import os
import secrets

from flask import Flask, session, request, jsonify, g

from canada_finance.config import DB_PATH, PROJECT_ROOT
from canada_finance.models.database import init_db, close_db
from canada_finance.routes import register_blueprints


def _get_secret_key() -> str:
    """Return SECRET_KEY from env, or auto-generate and persist one."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_file = os.path.join(PROJECT_ROOT, ".secret_key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(key_file, "w") as f:
        f.write(key)
    return key


def _register_csrf(app):
    """Lightweight CSRF protection for all mutating API requests."""

    @app.before_request
    def csrf_protect():
        if app.config.get("TESTING"):
            return
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return
        if not request.path.startswith("/api/"):
            return
        token = request.headers.get("X-CSRF-Token", "")
        if not token or token != session.get("csrf_token"):
            return jsonify({"error": "Invalid or missing CSRF token"}), 403

    @app.route("/api/csrf-token")
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return jsonify({"csrf_token": session["csrf_token"]})


def create_app():
    app = Flask(__name__)
    app.config["DB_PATH"] = DB_PATH
    app.secret_key = _get_secret_key()
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

    init_db(app)
    app.teardown_appcontext(close_db)
    _register_csrf(app)
    register_blueprints(app)

    return app


def main():
    app = create_app()
    print("\n🍁 CanadaFinance")
    print("   Open: http://localhost:5000")
    print("   Stop: Ctrl+C\n")
    app.run(debug=False, port=5000)
