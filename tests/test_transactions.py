"""Tests for transaction CRUD, search, pagination, hide/unhide."""
from tests.conftest import seed_transaction, seed_many_transactions


# ── Add ────────────────────────────────────────────────────────────────────────

def test_add_expense(client):
    res = seed_transaction(client)
    assert res["ok"] is True


def test_add_income(client):
    res = seed_transaction(client, type="Income", category="Job", name="Payroll")
    assert res["ok"] is True


def test_add_missing_field(client):
    r = client.post("/api/add", json={"date": "2026-03-15", "type": "Expense"})
    assert r.status_code == 400


def test_add_duplicate(client):
    seed_transaction(client)
    r = client.post("/api/add", json={
        "date": "2026-03-15", "type": "Expense", "name": "Tim Hortons",
        "category": "Eating Out", "amount": "12.50", "account": "Tangerine Chequing",
    })
    assert r.status_code == 409


# ── Get / Search / Filter ─────────────────────────────────────────────────────

def test_get_transactions_by_month(client):
    seed_transaction(client, date="2026-03-15")
    seed_transaction(client, date="2026-04-01", name="Costco", amount="55.00")
    r = client.get("/api/transactions?month=2026-03").get_json()
    assert isinstance(r, list)
    assert len(r) == 1
    assert r[0]["name"] == "Tim Hortons"


def test_search_transactions(client):
    seed_transaction(client, name="Costco Wholesale")
    seed_transaction(client, name="Tim Hortons")
    r = client.get("/api/transactions?search=costco").get_json()
    assert len(r) == 1
    assert "Costco" in r[0]["name"]


def test_filter_by_type(client):
    seed_transaction(client, type="Expense", name="Groceries")
    seed_transaction(client, type="Income", name="Payroll", category="Job")
    r = client.get("/api/transactions?month=2026-03&type=Income").get_json()
    assert len(r) == 1
    assert r[0]["type"] == "Income"


def test_filter_by_category(client):
    seed_transaction(client, category="Eating Out")
    seed_transaction(client, category="Groceries", name="Loblaws", amount="88.00")
    r = client.get("/api/transactions?month=2026-03&category=Groceries").get_json()
    assert len(r) == 1
    assert r[0]["category"] == "Groceries"


# ── Pagination ─────────────────────────────────────────────────────────────────

def test_pagination_basic(client):
    seed_many_transactions(client, 60)
    r = client.get("/api/transactions?month=2026-03&limit=10&offset=0").get_json()
    assert "transactions" in r
    assert len(r["transactions"]) == 10
    assert r["has_more"] is True
    assert r["total"] == 30  # half of 60 are March


def test_pagination_offset(client):
    seed_many_transactions(client, 60)
    r1 = client.get("/api/transactions?month=2026-03&limit=10&offset=0").get_json()
    r2 = client.get("/api/transactions?month=2026-03&limit=10&offset=10").get_json()
    ids1 = {t["id"] for t in r1["transactions"]}
    ids2 = {t["id"] for t in r2["transactions"]}
    assert ids1.isdisjoint(ids2)


def test_pagination_last_page(client):
    seed_many_transactions(client, 10)
    r = client.get("/api/transactions?month=2026-03&limit=50&offset=0").get_json()
    assert r["has_more"] is False


def test_no_limit_returns_flat_array(client):
    """Without limit param, response should be a flat array (backwards compatible)."""
    seed_transaction(client)
    r = client.get("/api/transactions?month=2026-03").get_json()
    assert isinstance(r, list)


# ── Update ─────────────────────────────────────────────────────────────────────

def test_update_transaction(client):
    seed_transaction(client)
    txns = client.get("/api/transactions?month=2026-03").get_json()
    tid = txns[0]["id"]
    r = client.patch(f"/api/update/{tid}", json={"category": "Groceries"})
    assert r.get_json()["ok"] is True
    # Verify change persisted
    txns2 = client.get("/api/transactions?month=2026-03").get_json()
    assert txns2[0]["category"] == "Groceries"


def test_update_learns_merchant(client, app):
    seed_transaction(client, name="Costco Wholesale")
    txns = client.get("/api/transactions?month=2026-03").get_json()
    tid = txns[0]["id"]
    client.patch(f"/api/update/{tid}", json={"category": "Groceries"})
    with app.app_context():
        from canada_finance.models.database import get_db
        db = get_db()
        row = db.execute("SELECT category FROM learned_merchants WHERE keyword='costco wholesale'").fetchone()
        assert row is not None
        assert row["category"] == "Groceries"


def test_update_nothing_returns_400(client):
    seed_transaction(client)
    txns = client.get("/api/transactions?month=2026-03").get_json()
    tid = txns[0]["id"]
    r = client.patch(f"/api/update/{tid}", json={"invalid_field": "x"})
    assert r.status_code == 400


# ── Delete ─────────────────────────────────────────────────────────────────────

def test_delete_transaction(client):
    seed_transaction(client)
    txns = client.get("/api/transactions?month=2026-03").get_json()
    tid = txns[0]["id"]
    r = client.delete(f"/api/delete/{tid}")
    assert r.get_json()["ok"] is True
    txns2 = client.get("/api/transactions?month=2026-03").get_json()
    assert len(txns2) == 0


# ── Hide / Unhide ─────────────────────────────────────────────────────────────

def test_hide_transaction(client):
    seed_transaction(client)
    txns = client.get("/api/transactions?month=2026-03").get_json()
    tid = txns[0]["id"]
    r = client.patch(f"/api/transactions/{tid}/hide")
    assert r.get_json()["ok"] is True
    # Should not appear in normal listing
    txns2 = client.get("/api/transactions?month=2026-03").get_json()
    assert len(txns2) == 0
    # Should appear in hidden listing
    txns3 = client.get("/api/transactions?month=2026-03&hidden=1").get_json()
    assert len(txns3) == 1


def test_unhide_transaction(client):
    seed_transaction(client)
    txns = client.get("/api/transactions?month=2026-03").get_json()
    tid = txns[0]["id"]
    client.patch(f"/api/transactions/{tid}/hide")
    client.patch(f"/api/transactions/{tid}/unhide")
    txns2 = client.get("/api/transactions?month=2026-03").get_json()
    assert len(txns2) == 1


def test_hidden_count(client):
    seed_transaction(client)
    txns = client.get("/api/transactions?month=2026-03").get_json()
    tid = txns[0]["id"]
    client.patch(f"/api/transactions/{tid}/hide")
    r = client.get("/api/transactions/hidden-count").get_json()
    assert r["count"] == 1
