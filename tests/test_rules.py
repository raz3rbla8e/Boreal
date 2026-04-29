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


# ── BULK CREATE ────────────────────────────────────────────────────────────────

def test_bulk_create_multiple_rules(client):
    """Create multiple hide rules at once."""
    r = client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Auto-hide: CREDIT CARD PAYMENT",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "CREDIT CARD PAYMENT"}],
        },
        {
            "name": "Auto-hide: E-TRANSFER TO VISA",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "E-TRANSFER TO VISA"}],
        },
    ]})
    j = r.get_json()
    assert j["ok"] is True
    assert j["created"] == 2
    assert len(j["ids"]) == 2
    # Verify rules exist
    rules = client.get("/api/rules").get_json()
    assert len(rules) == 2
    names = {r["name"] for r in rules}
    assert "Auto-hide: CREDIT CARD PAYMENT" in names
    assert "Auto-hide: E-TRANSFER TO VISA" in names


def test_bulk_create_single_rule(client):
    r = client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Auto-hide: Transfer",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "transfer"}],
        },
    ]})
    j = r.get_json()
    assert j["created"] == 1


def test_bulk_create_skips_invalid_action(client):
    """Invalid actions are silently skipped."""
    r = client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Good Rule",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "good"}],
        },
        {
            "name": "Bad Rule",
            "action": "explode",
            "conditions": [{"field": "description", "operator": "contains", "value": "bad"}],
        },
    ]})
    j = r.get_json()
    assert j["created"] == 1  # only the valid one


def test_bulk_create_skips_empty_name(client):
    r = client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "x"}],
        },
    ]})
    j = r.get_json()
    assert j["created"] == 0


def test_bulk_create_skips_no_conditions(client):
    r = client.post("/api/rules/bulk-create", json={"rules": [
        {"name": "No Cond", "action": "hide", "conditions": []},
    ]})
    j = r.get_json()
    assert j["created"] == 0


def test_bulk_create_skips_invalid_field(client):
    r = client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Bad Field",
            "action": "hide",
            "conditions": [{"field": "invalid_field", "operator": "contains", "value": "x"}],
        },
    ]})
    j = r.get_json()
    assert j["created"] == 0


def test_bulk_create_skips_invalid_operator(client):
    r = client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Bad Op",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "explodes", "value": "x"}],
        },
    ]})
    j = r.get_json()
    assert j["created"] == 0


def test_bulk_create_skips_empty_value(client):
    r = client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Empty Val",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": ""}],
        },
    ]})
    j = r.get_json()
    assert j["created"] == 0


def test_bulk_create_empty_list(client):
    r = client.post("/api/rules/bulk-create", json={"rules": []})
    assert r.status_code == 400


def test_bulk_create_no_body(client):
    r = client.post("/api/rules/bulk-create", json={})
    assert r.status_code == 400


def test_bulk_create_priority_ordering(client):
    """Bulk-created rules get sequential priorities after existing rules."""
    # Create an existing rule first
    _create_rule(client, name="Existing Rule")
    # Now bulk create
    client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Bulk Rule 1",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "one"}],
        },
        {
            "name": "Bulk Rule 2",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "two"}],
        },
    ]})
    rules = client.get("/api/rules").get_json()
    assert len(rules) == 3
    # Existing rule should have lower priority (comes first)
    assert rules[0]["name"] == "Existing Rule"
    assert rules[1]["name"] == "Bulk Rule 1"
    assert rules[2]["name"] == "Bulk Rule 2"
    # Priorities should be ascending
    assert rules[0]["priority"] < rules[1]["priority"]
    assert rules[1]["priority"] < rules[2]["priority"]


def test_bulk_create_special_characters(client):
    """Rules with special characters in description values are created correctly."""
    r = client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Auto-hide: TIM HORTON'S #1234",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "TIM HORTON'S #1234"}],
        },
    ]})
    j = r.get_json()
    assert j["created"] == 1
    rules = client.get("/api/rules").get_json()
    assert rules[0]["conditions"][0]["value"] == "TIM HORTON'S #1234"


# ── END-TO-END: HIDE → CREATE RULES → IMPORT ─────────────────────────────────

def test_e2e_hide_create_rule_hides_future_imports(client):
    """Full flow: hide transactions → create rules → new import is auto-hidden."""
    import io
    # Step 1: Seed transactions
    seed_transaction(client, name="CREDIT CARD PAYMENT", amount="500.00")
    seed_transaction(client, name="CREDIT CARD PAYMENT", amount="600.00")
    txns = client.get("/api/transactions?month=2026-03").get_json()
    ids = [t["id"] for t in txns]

    # Step 2: Bulk hide
    client.post("/api/bulk-hide", json={"ids": ids})
    visible = client.get("/api/transactions?month=2026-03").get_json()
    assert len(visible) == 0

    # Step 3: Get suggestions
    suggestions = client.post("/api/suggest-hide-rules", json={"ids": ids}).get_json()
    assert len(suggestions["suggestions"]) == 1
    assert suggestions["suggestions"][0]["description"] == "CREDIT CARD PAYMENT"

    # Step 4: Create rules from suggestions
    client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": f"Auto-hide: {s['description']}",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": s["description"]}],
        }
        for s in suggestions["suggestions"]
    ]})

    # Step 5: Verify rule exists
    rules = client.get("/api/rules").get_json()
    assert len(rules) == 1
    assert rules[0]["action"] == "hide"

    # Step 6: Import a CSV with the same description (new date/amount so not deduplicated)
    csv = "Date,Transaction,Name,Memo,Amount\n3/20/2026,DEBIT,CREDIT CARD PAYMENT,,700.00\n"
    data = {"files": (io.BytesIO(csv.encode()), "tangerine.csv")}
    r = client.post("/api/import", data=data, content_type="multipart/form-data")
    assert r.get_json()[0]["added"] == 1

    # Step 7: New transaction should be auto-hidden by the rule
    visible_after = client.get("/api/transactions?month=2026-03").get_json()
    assert all(t["name"] != "CREDIT CARD PAYMENT" for t in visible_after)
    hidden_after = client.get("/api/transactions?month=2026-03&hidden=1").get_json()
    cc_hidden = [t for t in hidden_after if t["name"] == "CREDIT CARD PAYMENT"]
    assert len(cc_hidden) == 3  # 2 original + 1 newly imported


def test_e2e_rule_does_not_over_match(client):
    """Rules created from specific descriptions don't hide unrelated transactions."""
    import io
    # Create a rule for "CREDIT CARD PAYMENT"
    client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Auto-hide: CREDIT CARD PAYMENT",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "CREDIT CARD PAYMENT"}],
        },
    ]})

    # Import a CSV with a different description
    csv = "Date,Transaction,Name,Memo,Amount\n3/20/2026,DEBIT,SHOPPERS DRUG MART,,25.00\n"
    data = {"files": (io.BytesIO(csv.encode()), "tangerine.csv")}
    client.post("/api/import", data=data, content_type="multipart/form-data")

    # SHOPPERS should be visible, NOT hidden
    visible = client.get("/api/transactions?month=2026-03").get_json()
    shoppers = [t for t in visible if "SHOPPERS" in t["name"]]
    assert len(shoppers) == 1


def test_e2e_multiple_rules_different_descriptions(client):
    """Creating rules for multiple different descriptions works correctly."""
    import io
    # Create rules for two descriptions
    client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Auto-hide: CREDIT CARD PAYMENT",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "CREDIT CARD PAYMENT"}],
        },
        {
            "name": "Auto-hide: E-TRANSFER TO VISA",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "E-TRANSFER TO VISA"}],
        },
    ]})

    # Import CSV with both descriptions plus one unrelated
    csv = (
        "Date,Transaction,Name,Memo,Amount\n"
        "3/20/2026,DEBIT,CREDIT CARD PAYMENT,,500.00\n"
        "3/21/2026,DEBIT,E-TRANSFER TO VISA,,800.00\n"
        "3/22/2026,DEBIT,GROCERIES LOBLAWS,,120.00\n"
    )
    data = {"files": (io.BytesIO(csv.encode()), "tangerine.csv")}
    client.post("/api/import", data=data, content_type="multipart/form-data")

    # Only GROCERIES should be visible
    visible = client.get("/api/transactions?month=2026-03").get_json()
    visible_names = [t["name"] for t in visible]
    assert "GROCERIES LOBLAWS" in visible_names
    assert "CREDIT CARD PAYMENT" not in visible_names
    assert "E-TRANSFER TO VISA" not in visible_names

    # Hidden should have the two
    hidden = client.get("/api/transactions?month=2026-03&hidden=1").get_json()
    hidden_names = [t["name"] for t in hidden]
    assert "CREDIT CARD PAYMENT" in hidden_names
    assert "E-TRANSFER TO VISA" in hidden_names


def test_e2e_rule_case_insensitive(client):
    """Rules with 'contains' operator match case-insensitively."""
    import io
    # Create rule with lowercase value
    client.post("/api/rules/bulk-create", json={"rules": [
        {
            "name": "Auto-hide: credit card",
            "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "credit card payment"}],
        },
    ]})

    # Import with uppercase description
    csv = "Date,Transaction,Name,Memo,Amount\n3/20/2026,DEBIT,CREDIT CARD PAYMENT,,500.00\n"
    data = {"files": (io.BytesIO(csv.encode()), "tangerine.csv")}
    client.post("/api/import", data=data, content_type="multipart/form-data")

    # Should still be hidden (case-insensitive match)
    visible = client.get("/api/transactions?month=2026-03").get_json()
    assert all(t["name"] != "CREDIT CARD PAYMENT" for t in visible)
