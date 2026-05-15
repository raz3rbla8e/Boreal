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


# ── Recurring ──────────────────────────────────────────────────────────────────

def test_recurring_empty(client):
    r = client.get("/api/recurring").get_json()
    assert r["recurring"] == []
    assert r["count"] == 0
    assert r["total_monthly_committed"] == 0


def test_recurring_detects_subscription(client):
    """A merchant appearing in 3+ months should be detected as recurring."""
    for m in range(1, 5):
        seed_transaction(
            client, date=f"2026-{m:02d}-15",
            type="Expense", amount="16.49", category="Subscriptions",
            name="NETFLIX", account="Tangerine Chequing",
        )
    r = client.get("/api/recurring").get_json()
    assert r["count"] == 1
    netflix = r["recurring"][0]
    assert netflix["name"] == "NETFLIX"
    assert netflix["months_seen"] == 4
    assert netflix["avg_amount"] == 16.49
    assert netflix["total_charges"] == 4
    assert netflix["price_changed"] is False


def test_recurring_ignores_infrequent(client):
    """A merchant appearing in only 2 months should NOT be detected."""
    for m in [1, 2]:
        seed_transaction(
            client, date=f"2026-{m:02d}-15",
            type="Expense", amount="50.00", category="Shopping",
            name="Random Store", account="Tangerine Chequing",
        )
    r = client.get("/api/recurring").get_json()
    assert r["count"] == 0


def test_recurring_detects_price_change(client):
    """Price change flag should be set when amount varies."""
    seed_transaction(client, date="2026-01-15", type="Expense", amount="16.49",
                     category="Subscriptions", name="NETFLIX")
    seed_transaction(client, date="2026-02-15", type="Expense", amount="16.49",
                     category="Subscriptions", name="NETFLIX")
    seed_transaction(client, date="2026-03-15", type="Expense", amount="17.99",
                     category="Subscriptions", name="NETFLIX")
    r = client.get("/api/recurring").get_json()
    assert r["count"] == 1
    assert r["recurring"][0]["price_changed"] is True
    assert r["recurring"][0]["min_amount"] == 16.49
    assert r["recurring"][0]["max_amount"] == 17.99


def test_recurring_total_monthly_committed(client):
    """total_monthly_committed should sum avg_amount of recurring expenses."""
    for m in range(1, 4):
        seed_transaction(client, date=f"2026-{m:02d}-15", type="Expense",
                         amount="16.49", category="Subscriptions", name="NETFLIX")
        seed_transaction(client, date=f"2026-{m:02d}-20", type="Expense",
                         amount="9.99", category="Subscriptions", name="SPOTIFY")
    r = client.get("/api/recurring").get_json()
    assert r["count"] == 2
    assert r["total_monthly_committed"] == 26.48


def test_recurring_custom_min_months(client):
    """min_months param should control the detection threshold."""
    for m in range(1, 3):
        seed_transaction(client, date=f"2026-{m:02d}-15", type="Expense",
                         amount="10.00", category="Misc", name="BIWEEKLY THING")
    # Default min_months=3 → not detected
    r = client.get("/api/recurring").get_json()
    assert r["count"] == 0
    # min_months=2 → detected
    r2 = client.get("/api/recurring?min_months=2").get_json()
    assert r2["count"] == 1


def test_recurring_excludes_hidden(client):
    """Hidden transactions should not appear in recurring detection."""
    for m in range(1, 4):
        seed_transaction(client, date=f"2026-{m:02d}-15", type="Expense",
                         amount="5.00", category="Misc", name="HIDDEN SUB")
    # Hide all of them
    txns = client.get("/api/transactions?search=HIDDEN SUB").get_json()
    for t in txns:
        client.patch(f"/api/transactions/{t['id']}/hide")
    r = client.get("/api/recurring").get_json()
    assert r["count"] == 0


def test_recurring_excludes_income(client):
    """Recurring income (e.g. salary) should NOT appear in recurring/subscriptions."""
    for m in range(1, 4):
        seed_transaction(client, date=f"2026-{m:02d}-01", type="Income",
                         amount="3000.00", category="Job", name="PAYROLL DEPOSIT")
    r = client.get("/api/recurring").get_json()
    assert r["count"] == 0
    assert r["recurring"] == []
    assert r["total_monthly_committed"] == 0
