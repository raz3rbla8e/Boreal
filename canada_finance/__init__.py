import os
import re
import secrets
import threading

from flask import Flask, session, request, jsonify, g

from canada_finance.config import DB_PATH, PROJECT_ROOT, DEMO_MODE
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
        # Skip CSRF for demo reset endpoint
        if request.path == "/api/demo/reset":
            return
        token = request.headers.get("X-CSRF-Token", "")
        if not token or token != session.get("csrf_token"):
            return jsonify({"error": "Invalid or missing CSRF token"}), 403

    @app.route("/api/csrf-token")
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return jsonify({"csrf_token": session["csrf_token"]})


# ── DEMO MODE GUARD ───────────────────────────────────────────────────────────

# Routes blocked in demo mode: (method, path_pattern)
# Path patterns use regex — anchored with ^ and $
_DEMO_BLOCKED = [
    ("POST",   r"^/api/import$"),
    ("POST",   r"^/api/restore$"),
    ("POST",   r"^/api/save-bank-config$"),
    ("POST",   r"^/api/add$"),
    ("DELETE", r"^/api/delete/\d+$"),
    ("POST",   r"^/api/bulk-delete$"),
    ("POST",   r"^/api/categories$"),
    ("DELETE", r"^/api/categories/\d+$"),
    ("PATCH",  r"^/api/categories/\d+$"),
    ("POST",   r"^/api/settings$"),
    ("POST",   r"^/api/rules$"),
    ("POST",   r"^/api/rules/bulk-create$"),
    ("PATCH",  r"^/api/rules/\d+$"),
    ("DELETE", r"^/api/rules/\d+$"),
    ("POST",   r"^/api/rules/reorder$"),
    ("POST",   r"^/api/rule-templates/load$"),
    ("POST",   r"^/api/budgets$"),
    ("DELETE", r"^/api/budgets/.+$"),
    ("DELETE", r"^/api/learned/.+$"),
]

_DEMO_BLOCKED_COMPILED = [(m, re.compile(p)) for m, p in _DEMO_BLOCKED]


def _register_demo_guard(app):
    """Block destructive routes when DEMO_MODE is active."""

    @app.before_request
    def demo_guard():
        if not app.config.get("DEMO_MODE"):
            return
        for method, pattern in _DEMO_BLOCKED_COMPILED:
            if request.method == method and pattern.match(request.path):
                return jsonify({
                    "error": "This feature is disabled in demo mode"
                }), 403


def _start_demo_reset_timer(app):
    """Reset demo data every 60 minutes."""
    def _reset():
        with app.app_context():
            from canada_finance.routes.main import _seed_demo_data
            _seed_demo_data(wipe=True)
            print("🔄 Demo data auto-reset")
        # Schedule next reset
        timer = threading.Timer(3600, _reset)
        timer.daemon = True
        timer.start()

    timer = threading.Timer(3600, _reset)
    timer.daemon = True
    timer.start()


def create_app():
    app = Flask(__name__)
    app.config["DB_PATH"] = DB_PATH
    app.config["DEMO_MODE"] = DEMO_MODE
    app.secret_key = _get_secret_key()
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

    init_db(app)
    app.teardown_appcontext(close_db)
    _register_csrf(app)
    _register_demo_guard(app)
    register_blueprints(app)

    # Auto-seed sample data in demo mode
    if DEMO_MODE:
        with app.app_context():
            from canada_finance.models.database import get_db
            db = get_db()
            count = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            if count == 0:
                from canada_finance.routes.main import _seed_demo_data
                added = _seed_demo_data(wipe=False)
                print(f"🍁 Demo mode: seeded {added} sample transactions")
        _start_demo_reset_timer(app)

    return app


def main():
    import os
    port = int(os.environ.get("PORT", 5000))
    app = create_app()
    print("\n🍁 CanadaFinance")
    print(f"   Open: http://localhost:{port}")
    print("   Stop: Ctrl+C\n")
    app.run(debug=False, host="0.0.0.0", port=port)
