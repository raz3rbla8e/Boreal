"""Tests for import rules CRUD, reorder, test, apply-all, templates."""
import json

from tests.conftest import seed_transaction


def _create_rule(client, name="Test Rule", action="hide", conditions=None, action_value=""):
    if conditions is None:
        conditions = [{"field": "description", "operator": "contains", "value": "transfer"}]
    return client.post("/api/rules", json={
        "name": name, "action": action, "action_value": action_value,
        "conditions": conditions,
    })


# ── CRUD ───────────────────────────────────────────────────────────────────────

def test_rules_empty(client):
    r = client.get("/api/rules").get_json()
    assert r == []


def test_create_rule(client):
    r = _create_rule(client)
    j = r.get_json()
    assert j["ok"] is True
    assert "id" in j


def test_create_rule_missing_name(client):
    r = client.post("/api/rules", json={
        "name": "", "action": "hide",
        "conditions": [{"field": "description", "operator": "contains", "value": "x"}],
    })
    assert r.status_code == 400


def test_create_rule_invalid_action(client):
    r = client.post("/api/rules", json={
        "name": "Bad", "action": "explode",
        "conditions": [{"field": "description", "operator": "contains", "value": "x"}],
    })
    assert r.status_code == 400


def test_create_rule_no_conditions(client):
    r = client.post("/api/rules", json={
        "name": "Bad", "action": "hide", "conditions": [],
    })
    assert r.status_code == 400


def test_create_rule_invalid_field(client):
    r = client.post("/api/rules", json={
        "name": "Bad", "action": "hide",
        "conditions": [{"field": "invalid", "operator": "contains", "value": "x"}],
    })
    assert r.status_code == 400


def test_create_rule_invalid_operator(client):
    r = client.post("/api/rules", json={
        "name": "Bad", "action": "hide",
        "conditions": [{"field": "description", "operator": "invalid", "value": "x"}],
    })
    assert r.status_code == 400


def test_list_rules_with_conditions(client):
    _create_rule(client, conditions=[
        {"field": "description", "operator": "contains", "value": "transfer"},
        {"field": "amount", "operator": "greater_than", "value": "100"},
    ])
    rules = client.get("/api/rules").get_json()
    assert len(rules) == 1
    assert len(rules[0]["conditions"]) == 2


def test_update_rule(client):
    r = _create_rule(client, name="Original")
    rule_id = r.get_json()["id"]
    r2 = client.patch(f"/api/rules/{rule_id}", json={"name": "Updated"})
    assert r2.get_json()["ok"] is True
    rules = client.get("/api/rules").get_json()
    assert rules[0]["name"] == "Updated"


def test_toggle_rule(client):
    r = _create_rule(client)
    rule_id = r.get_json()["id"]
    client.patch(f"/api/rules/{rule_id}", json={"enabled": 0})
    rules = client.get("/api/rules").get_json()
    assert rules[0]["enabled"] == 0


def test_update_rule_conditions(client):
    r = _create_rule(client)
    rule_id = r.get_json()["id"]
    r2 = client.patch(f"/api/rules/{rule_id}", json={
        "conditions": [{"field": "amount", "operator": "greater_than", "value": "500"}],
    })
    assert r2.get_json()["ok"] is True
    rules = client.get("/api/rules").get_json()
    assert rules[0]["conditions"][0]["field"] == "amount"


def test_update_nonexistent_rule(client):
    r = client.patch("/api/rules/99999", json={"name": "X"})
    assert r.status_code == 404


def test_delete_rule(client):
    r = _create_rule(client)
    rule_id = r.get_json()["id"]
    r2 = client.delete(f"/api/rules/{rule_id}")
    assert r2.get_json()["ok"] is True
    rules = client.get("/api/rules").get_json()
    assert len(rules) == 0


# ── Reorder ────────────────────────────────────────────────────────────────────

def test_reorder_rules(client):
    r1 = _create_rule(client, name="First")
    r2 = _create_rule(client, name="Second")
    id1, id2 = r1.get_json()["id"], r2.get_json()["id"]
    # Reverse order
    client.post("/api/rules/reorder", json={"order": [id2, id1]})
    rules = client.get("/api/rules").get_json()
    assert rules[0]["name"] == "Second"
    assert rules[1]["name"] == "First"


# ── Test Rule ──────────────────────────────────────────────────────────────────

def test_test_rule_matches(client):
    seed_transaction(client, name="E-TRANSFER TO JOHN")
    r = client.post("/api/rules/test", json={
        "conditions": [{"field": "description", "operator": "contains", "value": "transfer"}],
    })
    j = r.get_json()
    assert j["count"] >= 1


def test_test_rule_no_matches(client):
    seed_transaction(client, name="Tim Hortons")
    r = client.post("/api/rules/test", json={
        "conditions": [{"field": "description", "operator": "contains", "value": "nonexistent"}],
    })
    assert r.get_json()["count"] == 0


# ── Apply All ──────────────────────────────────────────────────────────────────

def test_apply_all_hides_matching(client):
    seed_transaction(client, name="E-TRANSFER TO LANDLORD")
    _create_rule(client, action="hide", conditions=[
        {"field": "description", "operator": "contains", "value": "transfer"},
    ])
    r = client.post("/api/rules/apply-all")
    j = r.get_json()
    assert j["affected"] >= 1
    # Transaction should now be hidden
    hidden = client.get("/api/transactions?month=2026-03&hidden=1").get_json()
    assert len(hidden) >= 1


def test_apply_all_labels_matching(client):
    seed_transaction(client, name="FREELANCE PAYMENT", type="Expense", category="Misc")
    action_value = json.dumps({"type": "Income", "category": "Freelance"})
    _create_rule(client, action="label", action_value=action_value, conditions=[
        {"field": "description", "operator": "contains", "value": "freelance"},
    ])
    client.post("/api/rules/apply-all")
    txns = client.get("/api/transactions?month=2026-03").get_json()
    freelance = next((t for t in txns if "FREELANCE" in t["name"]), None)
    assert freelance is not None
    assert freelance["type"] == "Income"
    assert freelance["category"] == "Freelance"


def test_apply_all_no_rules(client):
    r = client.post("/api/rules/apply-all")
    assert r.get_json()["affected"] == 0


# ── Templates ──────────────────────────────────────────────────────────────────

def test_list_templates(client):
    r = client.get("/api/rule-templates").get_json()
    assert isinstance(r, list)
    # Should have default templates from rules/templates/
    if r:
        assert "name" in r[0]
        assert "rule_count" in r[0]


def test_load_template(client):
    templates = client.get("/api/rule-templates").get_json()
    if not templates:
        return  # Skip if no templates available
    r = client.post("/api/rule-templates/load", json={"file": templates[0]["file"]})
    j = r.get_json()
    assert j["ok"] is True
    assert j["loaded"] > 0
    # Rules should now exist
    rules = client.get("/api/rules").get_json()
    assert len(rules) >= j["loaded"]
