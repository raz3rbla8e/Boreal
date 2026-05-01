import sqlite3

from flask import Blueprint, jsonify, request

from canada_finance.models.database import get_db, tx_hash
from canada_finance.routes.accounts import save_undo

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
        acct = request.args.get("account", "")
        if acct:
            q += " AND account=?"
            params.append(acct)
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
    if not d:
        return jsonify({"error": "Request body required"}), 400
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
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid transaction data"}), 400


@transactions_bp.route("/api/update/<int:tid>", methods=["PATCH"])
def api_update(tid):
    d = request.json
    if not d:
        return jsonify({"error": "Request body required"}), 400
    allowed = ["date", "type", "name", "category", "amount", "account", "notes"]
    sets = ", ".join(f"{k}=?" for k in d if k in allowed)
    vals = [d[k] for k in d if k in allowed] + [tid]
    if not sets:
        return jsonify({"error": "Nothing to update"}), 400
    db = get_db()
    db.row_factory = sqlite3.Row
    original = db.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    if original:
        save_undo(db, "update", {"id": tid, "old": dict(original)})
    db.execute(f"UPDATE transactions SET {sets} WHERE id=?", vals)
    retro_fixed = 0
    if "category" in d and original and d["category"] != original["category"]:
        new_cat = d["category"]
        orig_name = original["name"].lower().strip()
        db.execute("""INSERT INTO learned_merchants (keyword, category) VALUES (?,?)
            ON CONFLICT(keyword) DO UPDATE SET category=excluded.category, updated_at=datetime('now')
        """, (orig_name, new_cat))
        all_learned = db.execute("SELECT keyword, category FROM learned_merchants").fetchall()
        orig_cat = original["category"]
        fixable = "SELECT id, name FROM transactions WHERE id!=? AND (category='UNCATEGORIZED' OR category=?)"
        for row in db.execute(fixable, (tid, orig_cat)).fetchall():
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
    row = db.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    if row:
        save_undo(db, "delete", dict(row))
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


@transactions_bp.route("/api/accounts")
def api_accounts():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT account FROM transactions WHERE hidden=0 ORDER BY account"
    ).fetchall()
    return jsonify([r["account"] for r in rows])


@transactions_bp.route("/api/bulk-delete", methods=["POST"])
def api_bulk_delete():
    d = request.json or {}
    ids = d.get("ids", [])
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "No IDs provided"}), 400
    db = get_db()
    placeholders = ",".join("?" * len(ids))
    rows = db.execute(f"SELECT * FROM transactions WHERE id IN ({placeholders})", ids).fetchall()
    if rows:
        save_undo(db, "bulk_delete", [dict(r) for r in rows])
    db.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", ids)
    db.commit()
    return jsonify({"ok": True, "deleted": len(ids)})


@transactions_bp.route("/api/bulk-categorize", methods=["POST"])
def api_bulk_categorize():
    d = request.json or {}
    ids = d.get("ids", [])
    category = d.get("category", "").strip()
    if not ids or not isinstance(ids, list) or not category:
        return jsonify({"error": "IDs and category required"}), 400
    db = get_db()
    db.row_factory = sqlite3.Row
    placeholders = ",".join("?" * len(ids))
    # Learn merchants from the selected transactions
    rows = db.execute(
        f"SELECT DISTINCT name FROM transactions WHERE id IN ({placeholders})", ids
    ).fetchall()
    for row in rows:
        keyword = row["name"].lower().strip()
        if keyword:
            db.execute(
                """INSERT INTO learned_merchants (keyword, category) VALUES (?,?)
                ON CONFLICT(keyword) DO UPDATE SET category=excluded.category, updated_at=datetime('now')""",
                (keyword, category),
            )
    # Update selected transactions
    db.execute(
        f"UPDATE transactions SET category=? WHERE id IN ({placeholders})",
        [category] + ids,
    )
    # Retroactively fix other matching transactions
    retro_fixed = 0
    all_learned = db.execute("SELECT keyword, category FROM learned_merchants").fetchall()
    for row in rows:
        orig_name = row["name"].lower().strip()
        words = [w for w in orig_name.split() if len(w) > 3]
        if not words:
            continue
        for txn in db.execute(
            f"SELECT id, name FROM transactions WHERE id NOT IN ({placeholders}) AND (category='UNCATEGORIZED' OR category=?)",
            ids + [category],
        ).fetchall():
            rn = txn["name"].lower()
            if any(w in rn for w in words):
                db.execute("UPDATE transactions SET category=? WHERE id=?", (category, txn["id"]))
                retro_fixed += 1
    db.commit()
    return jsonify({"ok": True, "updated": len(ids), "learned": len(rows), "retro_fixed": retro_fixed})


@transactions_bp.route("/api/bulk-hide", methods=["POST"])
def api_bulk_hide():
    d = request.json or {}
    ids = d.get("ids", [])
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "No IDs provided"}), 400
    db = get_db()
    placeholders = ",".join("?" * len(ids))
    db.execute(
        f"UPDATE transactions SET hidden=1 WHERE id IN ({placeholders})", ids
    )
    db.commit()
    return jsonify({"ok": True, "hidden": len(ids)})


@transactions_bp.route("/api/bulk-unhide", methods=["POST"])
def api_bulk_unhide():
    d = request.json or {}
    ids = d.get("ids", [])
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "No IDs provided"}), 400
    db = get_db()
    placeholders = ",".join("?" * len(ids))
    db.execute(
        f"UPDATE transactions SET hidden=0 WHERE id IN ({placeholders})", ids
    )
    db.commit()
    return jsonify({"ok": True, "unhidden": len(ids)})


@transactions_bp.route("/api/suggest-hide-rules", methods=["POST"])
def api_suggest_hide_rules():
    """Given transaction IDs, return unique descriptions grouped for rule creation."""
    d = request.json or {}
    ids = d.get("ids", [])
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "No IDs provided"}), 400
    db = get_db()
    placeholders = ",".join("?" * len(ids))
    rows = db.execute(
        f"SELECT name, COUNT(*) as cnt FROM transactions WHERE id IN ({placeholders}) GROUP BY name ORDER BY cnt DESC",
        ids,
    ).fetchall()
    suggestions = [{"description": r["name"], "count": r["cnt"]} for r in rows]
    return jsonify({"suggestions": suggestions})


# ── SPLIT TRANSACTIONS ────────────────────────────────────────────────────────

@transactions_bp.route("/api/transactions/<int:tid>/split", methods=["POST"])
def api_split_transaction(tid):
    """Split a transaction into sub-rows. Body: {splits: [{category, amount}, ...]}"""
    d = request.json
    splits = d.get("splits", []) if d else []
    if len(splits) < 2:
        return jsonify({"error": "At least 2 split rows required"}), 400
    db = get_db()
    parent = db.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    if not parent:
        return jsonify({"error": "Transaction not found"}), 404
    if parent["parent_id"] is not None:
        return jsonify({"error": "Cannot split a child transaction"}), 400
    # Validate totals match
    try:
        split_total = round(sum(float(s["amount"]) for s in splits), 2)
    except (ValueError, TypeError, KeyError):
        return jsonify({"error": "Invalid split data"}), 400
    if abs(split_total - parent["amount"]) > 0.01:
        return jsonify({"error": f"Split total ({split_total}) must equal original ({parent['amount']})"}), 400
    # Remove old children if re-splitting
    db.execute("DELETE FROM transactions WHERE parent_id=?", (tid,))
    # Create children
    for i, s in enumerate(splits):
        h = tx_hash(parent["date"], f"{parent['name']}__split{i}", float(s["amount"]), parent["account"])
        db.execute(
            """INSERT INTO transactions
               (date, type, name, category, amount, account, notes, source, tx_hash, hidden, parent_id)
               VALUES (?,?,?,?,?,?,?,?,?,0,?)""",
            (parent["date"], parent["type"], parent["name"],
             s.get("category", "UNCATEGORIZED"), float(s["amount"]),
             parent["account"], s.get("notes", parent["notes"]), parent["source"], h, tid),
        )
    # Hide the parent
    db.execute("UPDATE transactions SET hidden=1 WHERE id=?", (tid,))
    db.commit()
    return jsonify({"ok": True, "children": len(splits)})


@transactions_bp.route("/api/transactions/<int:tid>/splits")
def api_get_splits(tid):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM transactions WHERE parent_id=? ORDER BY id", (tid,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@transactions_bp.route("/api/transactions/<int:tid>/unsplit", methods=["DELETE"])
def api_unsplit_transaction(tid):
    db = get_db()
    children = db.execute("SELECT id FROM transactions WHERE parent_id=?", (tid,)).fetchall()
    if not children:
        return jsonify({"error": "Transaction is not split"}), 400
    db.execute("DELETE FROM transactions WHERE parent_id=?", (tid,))
    db.execute("UPDATE transactions SET hidden=0 WHERE id=?", (tid,))
    db.commit()
    return jsonify({"ok": True})
