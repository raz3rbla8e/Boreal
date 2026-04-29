import os

from flask import Blueprint, render_template, jsonify

from canada_finance.config import DB_PATH

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "db_exists": os.path.isfile(DB_PATH),
    })
