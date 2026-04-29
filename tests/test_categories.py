"""Tests for category CRUD, rename cascade, delete with reassignment."""


# ── List ───────────────────────────────────────────────────────────────────────

def test_list_default_categories(client):
    r = client.get("/api/categories").get_json()
    assert len(r) > 0
    names = [c["name"] for c in r]
    assert "Eating Out" in names
    assert "Job" in names


# ── Add ────────────────────────────────────────────────────────────────────────

def test_add_category(client):
    r = client.post("/api/categories", json={"name": "Pets", "type": "Expense", "icon": "🐶"})
    assert r.get_json()["ok"] is True
    cats = client.get("/api/categories").get_json()
    assert any(c["name"] == "Pets" for c in cats)


def test_add_category_duplicate(client):
    client.post("/api/categories", json={"name": "Pets", "type": "Expense"})
    r = client.post("/api/categories", json={"name": "Pets", "type": "Expense"})
    assert r.status_code == 409


def test_add_category_missing_name(client):
    r = client.post("/api/categories", json={"name": "", "type": "Expense"})
    assert r.status_code == 400


def test_add_category_invalid_type(client):
    r = client.post("/api/categories", json={"name": "Bad", "type": "Other"})
    assert r.status_code == 400


# ── Rename ─────────────────────────────────────────────────────────────────────

def test_rename_category(client):
    cats = client.get("/api/categories").get_json()
    eating_out = next(c for c in cats if c["name"] == "Eating Out")
    r = client.patch(f"/api/categories/{eating_out['id']}", json={"name": "Dining Out"})
    assert r.get_json()["ok"] is True
    cats2 = client.get("/api/categories").get_json()
    assert any(c["name"] == "Dining Out" for c in cats2)
    assert not any(c["name"] == "Eating Out" for c in cats2)


def test_rename_cascades_to_transactions(client):
    from tests.conftest import seed_transaction
    seed_transaction(client, category="Eating Out")

    cats = client.get("/api/categories").get_json()
    eating_out = next(c for c in cats if c["name"] == "Eating Out")
    client.patch(f"/api/categories/{eating_out['id']}", json={"name": "Dining Out"})

    txns = client.get("/api/transactions?month=2026-03").get_json()
    assert txns[0]["category"] == "Dining Out"


def test_rename_to_existing_fails(client):
    cats = client.get("/api/categories").get_json()
    eating_out = next(c for c in cats if c["name"] == "Eating Out")
    r = client.patch(f"/api/categories/{eating_out['id']}", json={"name": "Groceries"})
    assert r.status_code == 409


def test_rename_nonexistent(client):
    r = client.patch("/api/categories/99999", json={"name": "Foo"})
    assert r.status_code == 404


# ── Delete ─────────────────────────────────────────────────────────────────────

def test_delete_unused_category(client):
    client.post("/api/categories", json={"name": "DeleteMe", "type": "Expense"})
    cats = client.get("/api/categories").get_json()
    cat = next(c for c in cats if c["name"] == "DeleteMe")
    r = client.delete(f"/api/categories/{cat['id']}")
    assert r.get_json()["ok"] is True
    cats2 = client.get("/api/categories").get_json()
    assert not any(c["name"] == "DeleteMe" for c in cats2)


def test_delete_in_use_without_reassign(client):
    from tests.conftest import seed_transaction
    seed_transaction(client, category="Eating Out")
    cats = client.get("/api/categories").get_json()
    eating_out = next(c for c in cats if c["name"] == "Eating Out")
    r = client.delete(f"/api/categories/{eating_out['id']}")
    assert r.status_code == 409
    assert r.get_json()["error"] == "in_use"


def test_delete_with_reassignment(client):
    from tests.conftest import seed_transaction
    seed_transaction(client, category="Eating Out")
    cats = client.get("/api/categories").get_json()
    eating_out = next(c for c in cats if c["name"] == "Eating Out")
    r = client.delete(f"/api/categories/{eating_out['id']}?reassign=Groceries")
    j = r.get_json()
    assert j["ok"] is True
    assert j["reassigned"] == 1
    # Transactions should be reassigned
    txns = client.get("/api/transactions?month=2026-03").get_json()
    assert txns[0]["category"] == "Groceries"
