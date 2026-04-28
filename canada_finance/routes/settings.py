import sqlite3

from flask import Blueprint, jsonify, request

from canada_finance.models.database import get_db

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/budgets", methods=["GET"])
def api_budgets_get():
    db = get_db()
    rows = db.execute("SELECT category, monthly_limit FROM budgets").fetchall()
    return jsonify([dict(r) for r in rows])


@settings_bp.route("/api/budgets", methods=["POST"])
def api_budgets_set():
    d = request.json
    db = get_db()
    db.execute("""INSERT INTO budgets (category, monthly_limit) VALUES (?,?)
        ON CONFLICT(category) DO UPDATE SET monthly_limit=excluded.monthly_limit
    """, (d["category"], float(d["amount"])))
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/budgets/<string:cat>", methods=["DELETE"])
def api_budgets_del(cat):
    db = get_db()
    db.execute("DELETE FROM budgets WHERE category=?", (cat,))
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/learned")
def api_learned():
    db = get_db()
    rows = db.execute(
        "SELECT keyword, category, updated_at FROM learned_merchants ORDER BY updated_at DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@settings_bp.route("/api/learned/<path:keyword>", methods=["DELETE"])
def api_learned_del(keyword):
    db = get_db()
    db.execute("DELETE FROM learned_merchants WHERE keyword=?", (keyword,))
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/settings", methods=["GET"])
def api_settings_get():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return jsonify({r["key"]: r["value"] for r in rows})


@settings_bp.route("/api/settings", methods=["POST"])
def api_settings_set():
    d = request.json
    db = get_db()
    for key, val in d.items():
        db.execute(
            "INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, val),
        )
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/categories")
def api_categories_get():
    db = get_db()
    rows = db.execute(
        "SELECT id, name, type, icon, user_created, sort_order FROM categories ORDER BY type, sort_order"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@settings_bp.route("/api/categories", methods=["POST"])
def api_categories_add():
    d = request.json
    name = d.get("name", "").strip()
    cat_type = d.get("type", "Expense")
    icon = d.get("icon", "").strip()
    if not name:
        return jsonify({"error": "Category name is required"}), 400
    if cat_type not in ("Income", "Expense"):
        return jsonify({"error": "Type must be Income or Expense"}), 400
    db = get_db()
    max_order = db.execute(
        "SELECT COALESCE(MAX(sort_order),0) FROM categories WHERE type=?", (cat_type,)
    ).fetchone()[0]
    try:
        db.execute(
            "INSERT INTO categories (name, type, icon, user_created, sort_order) VALUES (?,?,?,1,?)",
            (name, cat_type, icon, max_order + 1),
        )
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Category already exists"}), 409


@settings_bp.route("/api/categories/<int:cat_id>", methods=["PATCH"])
def api_categories_update(cat_id):
    d = request.json
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    if not cat:
        return jsonify({"error": "Category not found"}), 404
    old_name = cat["name"]
    new_name = d.get("name", old_name).strip()
    new_icon = d.get("icon", cat["icon"]).strip()
    if not new_name:
        return jsonify({"error": "Category name is required"}), 400
    try:
        db.execute("UPDATE categories SET name=?, icon=? WHERE id=?", (new_name, new_icon, cat_id))
        if new_name != old_name:
            db.execute("UPDATE transactions SET category=? WHERE category=?", (new_name, old_name))
            db.execute("UPDATE learned_merchants SET category=? WHERE category=?", (new_name, old_name))
            db.execute("UPDATE budgets SET category=? WHERE category=?", (new_name, old_name))
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "A category with that name already exists"}), 409


@settings_bp.route("/api/categories/<int:cat_id>", methods=["DELETE"])
def api_categories_delete(cat_id):
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    if not cat:
        return jsonify({"error": "Category not found"}), 404
    reassign_to = request.args.get("reassign", "")
    usage = db.execute(
        "SELECT COUNT(*) as c FROM transactions WHERE category=?", (cat["name"],)
    ).fetchone()["c"]
    if usage > 0 and not reassign_to:
        return jsonify({
            "error": "in_use",
            "count": usage,
            "message": f"{usage} transactions use this category. Provide a reassign target.",
        }), 409
    if usage > 0 and reassign_to:
        db.execute("UPDATE transactions SET category=? WHERE category=?", (reassign_to, cat["name"]))
        db.execute("UPDATE budgets SET category=? WHERE category=?", (reassign_to, cat["name"]))
        db.execute("UPDATE learned_merchants SET category=? WHERE category=?", (reassign_to, cat["name"]))
    db.execute("DELETE FROM budgets WHERE category=?", (cat["name"],))
    db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    db.commit()
    return jsonify({"ok": True, "reassigned": usage if reassign_to else 0})
