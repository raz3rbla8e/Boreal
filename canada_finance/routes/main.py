import glob
import os
import sqlite3

from flask import Blueprint, render_template, jsonify, current_app

from canada_finance.config import DB_PATH, SAMPLE_DATA_DIR, BANKS_DIR

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/icon-compare")
def icon_compare():
    return render_template("icon_compare.html")


@main_bp.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "db_exists": os.path.isfile(DB_PATH),
    })


@main_bp.route("/api/demo")
def api_demo():
    return jsonify({"demo": current_app.config.get("DEMO_MODE", False)})


@main_bp.route("/api/demo/reset", methods=["POST"])
def api_demo_reset():
    if not current_app.config.get("DEMO_MODE"):
        return jsonify({"error": "Not in demo mode"}), 403
    _seed_demo_data()
    return jsonify({"ok": True, "message": "Demo data reset"})


def _seed_demo_data(wipe=True):
    """Seed (or re-seed) the database from sample_data CSVs."""
    from canada_finance.models.database import get_db
    from canada_finance.services.categorization import load_learned_dict
    from canada_finance.services.csv_parser import load_bank_configs, detect_bank_config, parse_with_config
    from canada_finance.services.rules_engine import save_transactions

    db = get_db()
    if wipe:
        db.execute("DELETE FROM transactions")
        db.commit()

    learned = load_learned_dict(db)
    configs = load_bank_configs()
    total_added = 0

    csv_files = sorted(glob.glob(os.path.join(SAMPLE_DATA_DIR, "*.csv")))
    for csv_path in csv_files:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            text = f.read()
        first_line = text.splitlines()[0] if text.strip() else ""
        config, bank_name = detect_bank_config(first_line, configs)
        if config:
            txns = parse_with_config(text, config, learned)
            added, dupes = save_transactions(txns)
            total_added += added

    return total_added
