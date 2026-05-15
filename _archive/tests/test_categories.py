"""Tests for category CRUD, rename cascade, delete with reassignment."""

from canada_finance.services.categorization import categorize


# ── Auto-categorization rules ─────────────────────────────────────────────────

class TestExpenseCategorization:
    def test_eating_out(self):
        assert categorize("TIM HORTONS #3921") == "Eating Out"
        assert categorize("UBER EATS") == "Eating Out"
        assert categorize("STARBUCKS") == "Eating Out"

    def test_groceries(self):
        assert categorize("LOBLAWS #1042") == "Groceries"
        assert categorize("NO FRILLS") == "Groceries"
        assert categorize("COSTCO WHOLESALE") == "Groceries"

    def test_fuel(self):
        assert categorize("SHELL STATION #567") == "Fuel"
        assert categorize("COSTCO GAS") == "Fuel"
        assert categorize("PETRO-CANADA") == "Fuel"

    def test_subscriptions(self):
        assert categorize("NETFLIX.COM") == "Subscriptions"
        assert categorize("SPOTIFY") == "Subscriptions"

    def test_phone(self):
        assert categorize("ROGERS WIRELESS") == "Phone"
        assert categorize("FIDO MOBILE") == "Phone"

    def test_utilities(self):
        assert categorize("ENBRIDGE GAS") == "Utilities"
        assert categorize("HYDRO ONE") == "Utilities"

    def test_rent(self):
        assert categorize("RENT - LANDLORD") == "Rent"
        assert categorize("PROPERTY MANAGEMENT") == "Rent"

    def test_savings_transfer(self):
        assert categorize("TRANSFER TO TFSA") == "Savings Transfer"
        assert categorize("TRANSFER TO RRSP") == "Savings Transfer"

    def test_etransfer_sent(self):
        assert categorize("INTERAC e-TRANSFER SENT TO MOM") == "Misc"
        assert categorize("INTERAC e-TRANSFER SENT TO DAD") == "Misc"

    def test_atm(self):
        assert categorize("ATM WITHDRAWAL") == "Misc"

    def test_uncategorized_fallback(self):
        assert categorize("XYZZY UNKNOWN MERCHANT") == "UNCATEGORIZED"


class TestIncomeCategorization:
    def test_job(self):
        assert categorize("PAYROLL DEPOSIT") == "Job"
        assert categorize("PAYROLL - EMPLOYER") == "Job"
        assert categorize("DIRECT DEPOSIT") == "Job"
        assert categorize("SALARY PAYMENT") == "Job"

    def test_freelance(self):
        assert categorize("FREELANCE PAYMENT") == "Freelance"
        assert categorize("CONSULTING FEE") == "Freelance"

    def test_bonus(self):
        assert categorize("BONUS - Q1") == "Bonus"

    def test_refund(self):
        assert categorize("REFUND") == "Refund"
        assert categorize("REIMBURSEMENT") == "Refund"
        assert categorize("CASHBACK REWARD") == "Refund"

    def test_etransfer_received(self):
        assert categorize("INTERAC e-TRANSFER FROM MOM") == "Other Income"
        assert categorize("E-TRANSFER RECEIVED") == "Other Income"

    def test_interest(self):
        assert categorize("INTEREST PAYMENT") == "Other Income"
        assert categorize("INTEREST EARNED") == "Other Income"

    def test_government_benefits(self):
        assert categorize("GST/HST CREDIT") == "Other Income"
        assert categorize("CANADA CHILD BENEFIT") == "Other Income"
        assert categorize("TRILLIUM BENEFIT") == "Other Income"

    def test_learned_overrides_rules(self):
        learned = {"payroll deposit": "Freelance"}
        assert categorize("PAYROLL DEPOSIT", learned) == "Freelance"


class TestCategorizationPriority:
    def test_costco_gas_not_groceries(self):
        assert categorize("COSTCO GAS BAR") == "Fuel"

    def test_uber_eats_not_transport(self):
        assert categorize("UBER EATS ORDER") == "Eating Out"

    def test_store_name_overrides_refund(self):
        # "amazon" matches Shopping before "refund" matches Refund
        assert categorize("REFUND - AMAZON") == "Shopping"


# ── Category CRUD ─────────────────────────────────────────────────────────────

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
