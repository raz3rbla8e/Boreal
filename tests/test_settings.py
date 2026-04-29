"""Tests for settings: theme, budgets, learned merchants."""
from tests.conftest import seed_transaction


# ── Theme / Settings ───────────────────────────────────────────────────────────

def test_default_theme(client):
    r = client.get("/api/settings").get_json()
    assert r["theme"] == "dark"


def test_set_theme(client):
    client.post("/api/settings", json={"theme": "light"})
    r = client.get("/api/settings").get_json()
    assert r["theme"] == "light"


def test_set_multiple_settings(client):
    client.post("/api/settings", json={"theme": "light", "custom_key": "value"})
    r = client.get("/api/settings").get_json()
    assert r["theme"] == "light"
    assert r["custom_key"] == "value"


# ── Budgets ────────────────────────────────────────────────────────────────────

def test_budgets_empty(client):
    r = client.get("/api/budgets").get_json()
    assert r == []


def test_set_budget(client):
    r = client.post("/api/budgets", json={"category": "Eating Out", "amount": 200})
    assert r.get_json()["ok"] is True
    budgets = client.get("/api/budgets").get_json()
    assert len(budgets) == 1
    assert budgets[0]["category"] == "Eating Out"
    assert budgets[0]["monthly_limit"] == 200


def test_update_budget(client):
    client.post("/api/budgets", json={"category": "Eating Out", "amount": 200})
    client.post("/api/budgets", json={"category": "Eating Out", "amount": 300})
    budgets = client.get("/api/budgets").get_json()
    assert len(budgets) == 1
    assert budgets[0]["monthly_limit"] == 300


def test_delete_budget(client):
    client.post("/api/budgets", json={"category": "Eating Out", "amount": 200})
    r = client.delete("/api/budgets/Eating%20Out")
    assert r.get_json()["ok"] is True
    budgets = client.get("/api/budgets").get_json()
    assert len(budgets) == 0


# ── Learned Merchants ─────────────────────────────────────────────────────────

def test_learned_empty(client):
    r = client.get("/api/learned").get_json()
    assert r == []


def test_learned_after_recategorize(client):
    """When a transaction is recategorized, the merchant should be learned."""
    seed_transaction(client, name="Costco Wholesale", category="UNCATEGORIZED")
    txns = client.get("/api/transactions?month=2026-03").get_json()
    tid = txns[0]["id"]
    client.patch(f"/api/update/{tid}", json={"category": "Groceries"})
    learned = client.get("/api/learned").get_json()
    assert len(learned) >= 1
    assert any(l["keyword"] == "costco wholesale" for l in learned)


def test_delete_learned(client):
    seed_transaction(client, name="Costco Wholesale", category="UNCATEGORIZED")
    txns = client.get("/api/transactions?month=2026-03").get_json()
    client.patch(f"/api/update/{txns[0]['id']}", json={"category": "Groceries"})
    r = client.delete("/api/learned/costco%20wholesale")
    assert r.get_json()["ok"] is True
    learned = client.get("/api/learned").get_json()
    assert not any(l["keyword"] == "costco wholesale" for l in learned)
