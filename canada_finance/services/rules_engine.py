import json
import sqlite3

from canada_finance.models.database import get_db_path


def load_enabled_rules():
    """Load all enabled import rules with their conditions, ordered by priority."""
    with sqlite3.connect(get_db_path()) as db:
        db.row_factory = sqlite3.Row
        rules = db.execute(
            "SELECT * FROM import_rules WHERE enabled=1 ORDER BY priority ASC, id ASC"
        ).fetchall()
        result = []
        for r in rules:
            conditions = db.execute(
                "SELECT field, operator, value FROM rule_conditions WHERE rule_id=?",
                (r["id"],)
            ).fetchall()
            result.append({
                "id": r["id"], "name": r["name"], "priority": r["priority"],
                "action": r["action"], "action_value": r["action_value"],
                "conditions": [dict(c) for c in conditions],
            })
        return result


def _condition_matches(condition, tx):
    """Check if a single condition matches a transaction dict."""
    field = condition["field"]
    op = condition["operator"]
    expected = condition["value"]
    # Map rule fields to transaction dict keys
    field_map = {"description": "name", "amount": "amount", "account": "account", "type": "type"}
    tx_key = field_map.get(field, field)
    actual = tx.get(tx_key, "")
    if op in ("greater_than", "less_than"):
        try:
            actual_num = float(actual) if not isinstance(actual, (int, float)) else actual
            expected_num = float(expected)
        except (ValueError, TypeError):
            return False
        return actual_num > expected_num if op == "greater_than" else actual_num < expected_num
    actual_str = str(actual).lower()
    expected_str = str(expected).lower()
    if op == "contains":
        return expected_str in actual_str
    if op == "not_contains":
        return expected_str not in actual_str
    if op == "equals":
        return actual_str == expected_str
    if op == "not_equals":
        return actual_str != expected_str
    if op == "contains_any":
        return any(v.strip() in actual_str for v in expected_str.split(",") if v.strip())
    if op == "starts_with":
        return actual_str.startswith(expected_str)
    if op == "ends_with":
        return actual_str.endswith(expected_str)
    return False


def evaluate_rules(tx, rules=None):
    """Run a transaction through all enabled rules. Returns matched rule or None.
    First match wins (lowest priority number). Within the same priority,
    rules with more conditions (more specific) are evaluated first."""
    if rules is None:
        rules = load_enabled_rules()
    # Sort by priority ASC, then condition count DESC (more specific first), then id ASC
    sorted_rules = sorted(rules, key=lambda r: (r["priority"], -len(r["conditions"]), r["id"]))
    for rule in sorted_rules:
        if not rule["conditions"]:
            continue  # skip rules with no conditions
        if all(_condition_matches(c, tx) for c in rule["conditions"]):
            return rule
    return None


def apply_rule_to_transaction(tx, rule):
    """Apply matched rule action to a transaction dict (mutates in place)."""
    action = rule["action"]
    if action == "hide":
        tx["hidden"] = 1
    elif action == "pass":
        tx["hidden"] = 0
    elif action == "label":
        if rule["action_value"]:
            try:
                label = json.loads(rule["action_value"])
                if "type" in label:
                    tx["type"] = label["type"]
                if "category" in label:
                    tx["category"] = label["category"]
            except (json.JSONDecodeError, TypeError):
                pass
    return tx


def save_transactions(txns: list) -> tuple:
    from canada_finance.models.database import tx_hash
    added = dupes = 0
    rules = load_enabled_rules()
    with sqlite3.connect(get_db_path()) as db:
        for t in txns:
            # Apply import rules before saving
            if "hidden" not in t:
                t["hidden"] = 0
            matched_rule = evaluate_rules(t, rules)
            if matched_rule:
                apply_rule_to_transaction(t, matched_rule)
            h = tx_hash(t["date"], t["name"], t["amount"], t["account"])
            try:
                db.execute("""INSERT INTO transactions
                    (date,type,name,category,amount,account,notes,source,tx_hash,hidden)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (t["date"], t["type"], t["name"], t["category"],
                     t["amount"], t["account"], t.get("notes", ""), t.get("source", "csv"), h,
                     t.get("hidden", 0)))
                added += 1
            except sqlite3.IntegrityError:
                dupes += 1
        db.commit()
    return added, dupes
