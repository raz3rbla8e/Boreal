import os

from flask import Flask

from canada_finance.config import DB_PATH
from canada_finance.models.database import init_db, close_db
from canada_finance.routes import register_blueprints


def create_app():
    app = Flask(__name__)
    app.config["DB_PATH"] = DB_PATH
    app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

    init_db(app)
    app.teardown_appcontext(close_db)
    register_blueprints(app)

    return app


def main():
    app = create_app()
    print("\n🍁 CanadaFinance")
    print("   Open: http://localhost:5000")
    print("   Stop: Ctrl+C\n")
    app.run(debug=False, port=5000)
