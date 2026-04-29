"""Tests for monthly summary, year review, averages, month list."""
from tests.conftest import seed_transaction


# ── Months ─────────────────────────────────────────────────────────────────────

def test_months_empty(client):
    r = client.get("/api/months").get_json()
    assert r == []


def test_months_populated(client):
    seed_transaction(client, date="2026-03-15")
    seed_transaction(client, date="2026-04-01", name="Costco", amount="55.00")
    r = client.get("/api/months").get_json()
    assert "2026-04" in r
    assert "2026-03" in r


def test_months_excludes_hidden(client):
    seed_transaction(client, date="2026-05-01", name="Hidden one", amount="10.00")
    txns = client.get("/api/transactions?month=2026-05").get_json()
    tid = txns[0]["id"]
    client.patch(f"/api/transactions/{tid}/hide")
    months = client.get("/api/months").get_json()
    assert "2026-05" not in months


# ── Summary ────────────────────────────────────────────────────────────────────

def test_summary_correct_totals(client):
    seed_transaction(client, type="Expense", amount="100", name="Rent")
    seed_transaction(client, type="Expense", amount="50", name="Groceries", category="Groceries")
    seed_transaction(client, type="Income", amount="2000", name="Payroll", category="Job")
    r = client.get("/api/summary?month=2026-03").get_json()
    assert r["income"] == 2000
    assert r["expenses"] == 150
    assert r["net"] == 1850
    assert r["savings_rate"] > 0


def test_summary_by_category(client):
    seed_transaction(client, type="Expense", amount="100", name="Restaurant", category="Eating Out")
    seed_transaction(client, type="Expense", amount="200", name="Loblaws", category="Groceries")
    r = client.get("/api/summary?month=2026-03").get_json()
    cats = {c["category"]: c["total"] for c in r["by_category"]}
    assert cats["Groceries"] == 200
    assert cats["Eating Out"] == 100


def test_summary_includes_budget(client):
    seed_transaction(client, type="Expense", amount="100", category="Eating Out")
    client.post("/api/budgets", json={"category": "Eating Out", "amount": 200})
    r = client.get("/api/summary?month=2026-03").get_json()
    eating_out = next(c for c in r["by_category"] if c["category"] == "Eating Out")
    assert eating_out["budget"] == 200


def test_summary_previous_month_comparison(client):
    seed_transaction(client, date="2026-02-15", type="Expense", amount="300", name="Feb expense")
    seed_transaction(client, date="2026-03-15", type="Expense", amount="200", name="Mar expense")
    r = client.get("/api/summary?month=2026-03").get_json()
    assert r["prev_expenses"] == 300


# ── Year ───────────────────────────────────────────────────────────────────────

def test_year_review(client):
    seed_transaction(client, date="2026-01-15", type="Income", amount="3000", name="Jan pay", category="Job")
    seed_transaction(client, date="2026-01-20", type="Expense", amount="500", name="Jan rent")
    seed_transaction(client, date="2026-06-10", type="Expense", amount="100", name="Jun food")
    r = client.get("/api/year/2026").get_json()
    assert r["total_income"] == 3000
    assert r["total_expenses"] == 600
    assert len(r["months"]) == 12
    assert r["months"][0]["income"] == 3000  # January
    assert r["months"][0]["expenses"] == 500


def test_year_review_empty_year(client):
    r = client.get("/api/year/2020").get_json()
    assert r["total_income"] == 0
    assert r["total_expenses"] == 0


def test_year_top_categories(client):
    seed_transaction(client, date="2026-01-15", type="Expense", amount="500", category="Groceries", name="G1")
    seed_transaction(client, date="2026-02-15", type="Expense", amount="300", category="Eating Out", name="E1")
    r = client.get("/api/year/2026").get_json()
    assert len(r["top_categories"]) > 0
    assert r["top_categories"][0]["category"] == "Groceries"


# ── Averages ───────────────────────────────────────────────────────────────────

def test_averages(client):
    for m in range(1, 4):
        seed_transaction(
            client, date=f"2026-{m:02d}-15",
            type="Expense", amount="100", category="Groceries",
            name=f"Grocery {m}",
        )
    r = client.get("/api/averages").get_json()
    assert len(r) > 0
    grocery = next((a for a in r if a["category"] == "Groceries"), None)
    assert grocery is not None
    assert grocery["avg_monthly"] == 100


def test_averages_empty(client):
    r = client.get("/api/averages").get_json()
    assert r == []
