import os

import yaml
from flask import Blueprint, jsonify, request

from canada_finance.config import RULES_TEMPLATE_DIR
from canada_finance.models.database import get_db
from canada_finance.services.rules_engine import (
    load_enabled_rules, _condition_matches, evaluate_rules, apply_rule_to_transaction,
)

rules_bp = Blueprint("rules", __name__)

VALID_RULE_ACTIONS = {"hide", "label", "pass"}
VALID_RULE_FIELDS = {"description", "amount", "account", "type"}
VALID_RULE_OPERATORS = {"contains", "not_contains", "equals", "not_equals", "contains_any", "starts_with", "ends_with", "greater_than", "less_than"}


@rules_bp.route("/api/rules")
def api_rules_get():
    db = get_db()
    rules = db.execute(
        "SELECT * FROM import_rules ORDER BY priority ASC, id ASC"
    ).fetchall()
    result = []
    for r in rules:
        conditions = db.execute(
            "SELECT id, field, operator, value FROM rule_conditions WHERE rule_id=?",
            (r["id"],),
        ).fetchall()
        result.append({
            **dict(r),
            "conditions": [dict(c) for c in conditions],
        })
    return jsonify(result)


@rules_bp.route("/api/rules", methods=["POST"])
def api_rules_create():
    d = request.json
    name = d.get("name", "").strip()
    action = d.get("action", "")
    if not name:
        return jsonify({"error": "Rule name is required"}), 400
    if action not in VALID_RULE_ACTIONS:
        return jsonify({"error": f"Invalid action: {action}"}), 400
    conditions = d.get("conditions", [])
    if not conditions:
        return jsonify({"error": "At least one condition is required"}), 400
    for c in conditions:
        if c.get("field") not in VALID_RULE_FIELDS:
            return jsonify({"error": f"Invalid field: {c.get('field')}"}), 400
        if c.get("operator") not in VALID_RULE_OPERATORS:
            return jsonify({"error": f"Invalid operator: {c.get('operator')}"}), 400
        if not c.get("value", "").strip():
            return jsonify({"error": "Condition value cannot be empty"}), 400
    db = get_db()
    max_priority = db.execute("SELECT COALESCE(MAX(priority),0) FROM import_rules").fetchone()[0]
    cur = db.execute(
        "INSERT INTO import_rules (name, priority, action, action_value) VALUES (?,?,?,?)",
        (name, max_priority + 1, action, d.get("action_value", "")),
    )
    rule_id = cur.lastrowid
    for c in conditions:
        db.execute(
            "INSERT INTO rule_conditions (rule_id, field, operator, value) VALUES (?,?,?,?)",
            (rule_id, c["field"], c["operator"], c["value"].strip()),
        )
    db.commit()
    return jsonify({"ok": True, "id": rule_id})


@rules_bp.route("/api/rules/<int:rule_id>", methods=["PATCH"])
def api_rules_update(rule_id):
    d = request.json
    db = get_db()
    rule = db.execute("SELECT * FROM import_rules WHERE id=?", (rule_id,)).fetchone()
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    name = d.get("name", rule["name"]).strip()
    action = d.get("action", rule["action"])
    enabled = d.get("enabled", rule["enabled"])
    action_value = d.get("action_value", rule["action_value"])
    if action not in VALID_RULE_ACTIONS:
        return jsonify({"error": f"Invalid action: {action}"}), 400
    db.execute(
        "UPDATE import_rules SET name=?, action=?, action_value=?, enabled=?, updated_at=datetime('now') WHERE id=?",
        (name, action, action_value, int(enabled), rule_id),
    )
    if "conditions" in d:
        conditions = d["conditions"]
        if not conditions:
            return jsonify({"error": "At least one condition is required"}), 400
        for c in conditions:
            if c.get("field") not in VALID_RULE_FIELDS:
                return jsonify({"error": f"Invalid field: {c.get('field')}"}), 400
            if c.get("operator") not in VALID_RULE_OPERATORS:
                return jsonify({"error": f"Invalid operator: {c.get('operator')}"}), 400
        db.execute("DELETE FROM rule_conditions WHERE rule_id=?", (rule_id,))
        for c in conditions:
            db.execute(
                "INSERT INTO rule_conditions (rule_id, field, operator, value) VALUES (?,?,?,?)",
                (rule_id, c["field"], c["operator"], c["value"].strip()),
            )
    db.commit()
    return jsonify({"ok": True})


@rules_bp.route("/api/rules/<int:rule_id>", methods=["DELETE"])
def api_rules_delete(rule_id):
    db = get_db()
    db.execute("DELETE FROM rule_conditions WHERE rule_id=?", (rule_id,))
    db.execute("DELETE FROM import_rules WHERE id=?", (rule_id,))
    db.commit()
    return jsonify({"ok": True})


@rules_bp.route("/api/rules/reorder", methods=["POST"])
def api_rules_reorder():
    order = request.json.get("order", [])
    db = get_db()
    for i, rule_id in enumerate(order):
        db.execute("UPDATE import_rules SET priority=? WHERE id=?", (i, int(rule_id)))
    db.commit()
    return jsonify({"ok": True})


@rules_bp.route("/api/rules/test", methods=["POST"])
def api_rules_test():
    """Test a rule definition against existing transactions."""
    d = request.json
    conditions = d.get("conditions", [])
    if not conditions:
        return jsonify({"error": "At least one condition is required"}), 400
    db = get_db()
    rows = db.execute("SELECT * FROM transactions ORDER BY date DESC").fetchall()
    matches = []
    for r in rows:
        tx = dict(r)
        if all(_condition_matches(c, tx) for c in conditions):
            matches.append({
                "id": tx["id"], "date": tx["date"], "name": tx["name"],
                "category": tx["category"], "type": tx["type"],
                "amount": tx["amount"], "account": tx["account"],
                "hidden": tx.get("hidden", 0),
            })
    return jsonify({"count": len(matches), "transactions": matches[:50]})


@rules_bp.route("/api/rules/apply-all", methods=["POST"])
def api_rules_apply_all():
    """Apply all enabled rules retroactively to existing transactions."""
    rules = load_enabled_rules()
    if not rules:
        return jsonify({"affected": 0, "message": "No enabled rules"})
    db = get_db()
    rows = db.execute("SELECT * FROM transactions").fetchall()
    affected = 0
    for r in rows:
        tx = dict(r)
        matched = evaluate_rules(tx, rules)
        if matched:
            original_hidden = tx.get("hidden", 0)
            original_type = tx["type"]
            original_category = tx["category"]
            apply_rule_to_transaction(tx, matched)
            changed = (
                tx.get("hidden", 0) != original_hidden
                or tx["type"] != original_type
                or tx["category"] != original_category
            )
            if changed:
                db.execute(
                    "UPDATE transactions SET hidden=?, type=?, category=? WHERE id=?",
                    (tx.get("hidden", 0), tx["type"], tx["category"], tx["id"]),
                )
                affected += 1
    db.commit()
    return jsonify({"affected": affected})


@rules_bp.route("/api/rule-templates")
def api_rule_templates():
    templates = []
    if not os.path.isdir(RULES_TEMPLATE_DIR):
        return jsonify(templates)
    for fname in sorted(os.listdir(RULES_TEMPLATE_DIR)):
        if not fname.endswith(".yaml"):
            continue
        fpath = os.path.join(RULES_TEMPLATE_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            templates.append({
                "file": fname,
                "name": data.get("name", fname),
                "description": data.get("description", ""),
                "rule_count": len(data.get("rules", [])),
            })
        except Exception:
            continue
    return jsonify(templates)


@rules_bp.route("/api/rule-templates/load", methods=["POST"])
def api_rule_templates_load():
    d = request.json or {}
    fname = d.get("file", "")
    if not fname or ".." in fname:
        return jsonify({"error": "Invalid template file"}), 400
    fpath = os.path.realpath(os.path.join(RULES_TEMPLATE_DIR, fname))
    if not fpath.startswith(os.path.realpath(RULES_TEMPLATE_DIR)):
        return jsonify({"error": "Invalid template file"}), 400
    if not os.path.isfile(fpath):
        return jsonify({"error": "Template not found"}), 404
    with open(fpath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    rules = data.get("rules", [])
    if not rules:
        return jsonify({"error": "Template has no rules"}), 400
    db = get_db()
    max_priority = db.execute("SELECT COALESCE(MAX(priority),0) FROM import_rules").fetchone()[0]
    loaded = 0
    for i, r in enumerate(rules):
        action = r.get("action", "")
        if action not in VALID_RULE_ACTIONS:
            continue
        cur = db.execute(
            "INSERT INTO import_rules (name, priority, action, action_value) VALUES (?,?,?,?)",
            (r.get("name", "Unnamed"), max_priority + i + 1, action, r.get("action_value", "")),
        )
        rule_id = cur.lastrowid
        for c in r.get("conditions", []):
            if c.get("field") in VALID_RULE_FIELDS and c.get("operator") in VALID_RULE_OPERATORS:
                db.execute(
                    "INSERT INTO rule_conditions (rule_id, field, operator, value) VALUES (?,?,?,?)",
                    (rule_id, c["field"], c["operator"], c.get("value", "")),
                )
        loaded += 1
    db.commit()
    return jsonify({"ok": True, "loaded": loaded})
