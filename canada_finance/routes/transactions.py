import sqlite3

from flask import Blueprint, jsonify, request

from canada_finance.models.database import get_db, tx_hash

transactions_bp = Blueprint("transactions", __name__)


@transactions_bp.route("/api/transactions")
def api_transactions():
    month = request.args.get("month", "")
    cat = request.args.get("category", "")
    typ = request.args.get("type", "")
    search = request.args.get("search", "").strip()
    show_hidden = request.args.get("hidden", "0") == "1"
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", 0, type=int)
    db = get_db()
    hidden_filter = "hidden=1" if show_hidden else "hidden=0"
    if search:
        term = f"%{search}%"
        q = f"""SELECT * FROM transactions WHERE {hidden_filter} AND
               (name LIKE ? OR category LIKE ? OR account LIKE ? OR notes LIKE ? OR date LIKE ?)"""
        params = [term] * 5
        if typ:
            q += " AND type=?"
            params.append(typ)
        q += " ORDER BY date DESC, id DESC"
    else:
        q = f"SELECT * FROM transactions WHERE {hidden_filter} AND date LIKE ?"
        params = [f"{month}%"]
        if cat:
            q += " AND category=?"
            params.append(cat)
        if typ:
            q += " AND type=?"
            params.append(typ)
        q += " ORDER BY date DESC, id DESC"

    if limit is not None:
        # Count total before limiting
        count_q = f"SELECT COUNT(*) as c FROM ({q})"
        total = db.execute(count_q, params).fetchone()["c"]
        q += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = db.execute(q, params).fetchall()
        return jsonify({
            "transactions": [dict(r) for r in rows],
            "has_more": offset + len(rows) < total,
            "total": total,
        })
    else:
        rows = db.execute(q, params).fetchall()
        return jsonify([dict(r) for r in rows])


@transactions_bp.route("/api/add", methods=["POST"])
def api_add():
    d = request.json
    for f in ["date", "type", "name", "category", "amount", "account"]:
        if not d.get(f):
            return jsonify({"error": f"Missing: {f}"}), 400
    try:
        amount = float(d["amount"])
        h = tx_hash(d["date"], d["name"], amount, d["account"])
        get_db().execute("""INSERT INTO transactions
            (date,type,name,category,amount,account,notes,source,tx_hash)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (d["date"], d["type"], d["name"], d["category"],
             amount, d["account"], d.get("notes", ""), "manual", h))
        get_db().commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Duplicate transaction"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@transactions_bp.route("/api/update/<int:tid>", methods=["PATCH"])
def api_update(tid):
    d = request.json
    allowed = ["date", "type", "name", "category", "amount", "account", "notes"]
    sets = ", ".join(f"{k}=?" for k in d if k in allowed)
    vals = [d[k] for k in d if k in allowed] + [tid]
    if not sets:
        return jsonify({"error": "Nothing to update"}), 400
    db = get_db()
    db.row_factory = sqlite3.Row
    original = db.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    db.execute(f"UPDATE transactions SET {sets} WHERE id=?", vals)
    retro_fixed = 0
    if "category" in d and original:
        new_cat = d["category"]
        orig_name = original["name"].lower().strip()
        db.execute("""INSERT INTO learned_merchants (keyword, category) VALUES (?,?)
            ON CONFLICT(keyword) DO UPDATE SET category=excluded.category, updated_at=datetime('now')
        """, (orig_name, new_cat))
        all_learned = db.execute("SELECT keyword, category FROM learned_merchants").fetchall()
        for row in db.execute("SELECT id, name FROM transactions WHERE category='UNCATEGORIZED'").fetchall():
            rn = row["name"].lower()
            for lrow in all_learned:
                words = [w for w in lrow["keyword"].split() if len(w) > 3]
                if any(w in rn for w in words):
                    db.execute("UPDATE transactions SET category=? WHERE id=?", (lrow["category"], row["id"]))
                    retro_fixed += 1
                    break
    db.commit()
    return jsonify({"ok": True, "retro_fixed": retro_fixed})


@transactions_bp.route("/api/delete/<int:tid>", methods=["DELETE"])
def api_delete(tid):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id=?", (tid,))
    db.commit()
    return jsonify({"ok": True})


@transactions_bp.route("/api/transactions/<int:tid>/hide", methods=["PATCH"])
def api_transaction_hide(tid):
    db = get_db()
    db.execute("UPDATE transactions SET hidden=1 WHERE id=?", (tid,))
    db.commit()
    return jsonify({"ok": True})


@transactions_bp.route("/api/transactions/<int:tid>/unhide", methods=["PATCH"])
def api_transaction_unhide(tid):
    db = get_db()
    db.execute("UPDATE transactions SET hidden=0 WHERE id=?", (tid,))
    db.commit()
    return jsonify({"ok": True})


@transactions_bp.route("/api/transactions/hidden-count")
def api_hidden_count():
    db = get_db()
    count = db.execute("SELECT COUNT(*) as c FROM transactions WHERE hidden=1").fetchone()["c"]
    return jsonify({"count": count})
