"""Tests for 7 new features: PWA, accounts, net worth, scheduled transactions,
transfers, undo, OFX import."""
import json
import io

import pytest

from tests.conftest import seed_transaction


# ── ACCOUNTS ──────────────────────────────────────────────────────────────────

class TestAccounts:
    def test_list_empty(self, client):
        res = client.get("/api/accounts-list")
        assert res.status_code == 200
        assert res.get_json() == []

    def test_add_account(self, client):
        res = client.post("/api/accounts-list", json={
            "name": "TD Chequing", "account_type": "chequing", "opening_balance": 1000,
        })
        assert res.get_json()["ok"]

    def test_add_duplicate(self, client):
        client.post("/api/accounts-list", json={"name": "TD", "account_type": "chequing"})
        res = client.post("/api/accounts-list", json={"name": "TD", "account_type": "chequing"})
        assert res.status_code == 409

    def test_invalid_type(self, client):
        res = client.post("/api/accounts-list", json={
            "name": "Test", "account_type": "invalid",
        })
        assert res.status_code == 400

    def test_balance_calculation(self, client):
        client.post("/api/accounts-list", json={
            "name": "Tangerine Chequing", "account_type": "chequing", "opening_balance": 500,
        })
        seed_transaction(client, type="Income", name="Payday", category="Job",
                         amount="1000", account="Tangerine Chequing")
        seed_transaction(client, type="Expense", name="Groceries", category="Groceries",
                         amount="200", account="Tangerine Chequing")
        accounts = client.get("/api/accounts-list").get_json()
        assert len(accounts) == 1
        assert accounts[0]["balance"] == 1300.0  # 500 + 1000 - 200

    def test_update_account(self, client):
        client.post("/api/accounts-list", json={"name": "Old", "account_type": "chequing"})
        accounts = client.get("/api/accounts-list").get_json()
        aid = accounts[0]["id"]
        res = client.patch(f"/api/accounts-list/{aid}", json={"name": "New", "opening_balance": 100})
        assert res.get_json()["ok"]
        updated = client.get("/api/accounts-list").get_json()
        assert updated[0]["name"] == "New"
        assert updated[0]["opening_balance"] == 100

    def test_delete_account(self, client):
        client.post("/api/accounts-list", json={"name": "Delete Me", "account_type": "savings"})
        accounts = client.get("/api/accounts-list").get_json()
        aid = accounts[0]["id"]
        res = client.delete(f"/api/accounts-list/{aid}")
        assert res.get_json()["ok"]
        assert client.get("/api/accounts-list").get_json() == []

    def test_rename_cascades_transactions(self, client):
        client.post("/api/accounts-list", json={"name": "Old Acct", "account_type": "chequing"})
        seed_transaction(client, account="Old Acct")
        accounts = client.get("/api/accounts-list").get_json()
        client.patch(f"/api/accounts-list/{accounts[0]['id']}", json={"name": "New Acct"})
        txns = client.get("/api/transactions?month=2026-03").get_json()
        assert txns[0]["account"] == "New Acct"


# ── NET WORTH ─────────────────────────────────────────────────────────────────

class TestNetWorth:
    def test_empty(self, client):
        res = client.get("/api/net-worth")
        assert res.status_code == 200
        assert res.get_json() == []

    def test_with_accounts(self, client):
        client.post("/api/accounts-list", json={
            "name": "Tangerine Chequing", "account_type": "chequing", "opening_balance": 1000,
        })
        seed_transaction(client, type="Expense", amount="100", account="Tangerine Chequing")
        data = client.get("/api/net-worth").get_json()
        assert len(data) >= 1
        assert data[0]["net_worth"] == 900.0

    def test_multiple_accounts(self, client):
        client.post("/api/accounts-list", json={
            "name": "Tangerine Chequing", "account_type": "chequing", "opening_balance": 500,
        })
        client.post("/api/accounts-list", json={
            "name": "CIBC Savings", "account_type": "savings", "opening_balance": 2000,
        })
        seed_transaction(client, type="Expense", amount="100", account="Tangerine Chequing")
        data = client.get("/api/net-worth").get_json()
        assert data[-1]["net_worth"] == 2400.0  # 500-100 + 2000


# ── SCHEDULED TRANSACTIONS ────────────────────────────────────────────────────

class TestScheduledTransactions:
    def test_list_empty(self, client):
        assert client.get("/api/schedules").get_json() == []

    def test_add_schedule(self, client):
        res = client.post("/api/schedules", json={
            "name": "Netflix", "type": "Expense", "category": "Subscriptions",
            "amount": 15.99, "account": "TD Chequing", "frequency": "monthly",
            "next_due": "2026-05-01",
        })
        assert res.get_json()["ok"]
        schedules = client.get("/api/schedules").get_json()
        assert len(schedules) == 1
        assert schedules[0]["name"] == "Netflix"

    def test_add_missing_name(self, client):
        res = client.post("/api/schedules", json={
            "name": "", "type": "Expense", "category": "Misc",
            "amount": 10, "account": "TD", "next_due": "2026-05-01",
        })
        assert res.status_code == 400

    def test_toggle_enabled(self, client):
        client.post("/api/schedules", json={
            "name": "Test", "type": "Expense", "category": "Misc",
            "amount": 10, "account": "TD", "frequency": "monthly",
            "next_due": "2026-05-01",
        })
        schedules = client.get("/api/schedules").get_json()
        sid = schedules[0]["id"]
        client.patch(f"/api/schedules/{sid}", json={"enabled": 0})
        updated = client.get("/api/schedules").get_json()
        assert updated[0]["enabled"] == 0

    def test_delete_schedule(self, client):
        client.post("/api/schedules", json={
            "name": "Delete", "type": "Expense", "category": "Misc",
            "amount": 5, "account": "TD", "frequency": "weekly",
            "next_due": "2026-05-01",
        })
        schedules = client.get("/api/schedules").get_json()
        res = client.delete(f"/api/schedules/{schedules[0]['id']}")
        assert res.get_json()["ok"]
        assert client.get("/api/schedules").get_json() == []

    def test_post_due_creates_transaction(self, client):
        # Schedule due today (2026-04-30 or whenever test runs — use a past date)
        client.post("/api/schedules", json={
            "name": "Rent", "type": "Expense", "category": "Rent",
            "amount": 1500, "account": "TD Chequing", "frequency": "monthly",
            "next_due": "2020-01-01",  # Past date — should be due
        })
        res = client.post("/api/schedules/post-due", json={})
        data = res.get_json()
        assert data["ok"]
        assert data["posted"] == 1
        # Verify transaction was created
        txns = client.get("/api/transactions?month=2020-01").get_json()
        assert len(txns) >= 1

    def test_post_due_advances_next_due(self, client):
        client.post("/api/schedules", json={
            "name": "Test", "type": "Expense", "category": "Misc",
            "amount": 10, "account": "TD", "frequency": "monthly",
            "next_due": "2020-01-15",
        })
        client.post("/api/schedules/post-due", json={})
        schedules = client.get("/api/schedules").get_json()
        assert schedules[0]["next_due"] == "2020-02-15"

    def test_post_due_no_duplicate(self, client):
        client.post("/api/schedules", json={
            "name": "Test", "type": "Expense", "category": "Misc",
            "amount": 10, "account": "TD", "frequency": "monthly",
            "next_due": "2020-01-15",
        })
        client.post("/api/schedules/post-due", json={})
        # Post again — should advance but not duplicate
        client.post("/api/schedules/post-due", json={})
        txns = client.get("/api/transactions?month=2020-01").get_json()
        assert len(txns) == 1  # Only one, no duplicate

    def test_weekly_frequency(self, client):
        client.post("/api/schedules", json={
            "name": "Gym", "type": "Expense", "category": "Misc",
            "amount": 20, "account": "TD", "frequency": "weekly",
            "next_due": "2020-01-01",
        })
        client.post("/api/schedules/post-due", json={})
        schedules = client.get("/api/schedules").get_json()
        assert schedules[0]["next_due"] == "2020-01-08"


# ── TRANSFERS ─────────────────────────────────────────────────────────────────

class TestTransfers:
    def test_create_transfer(self, client):
        res = client.post("/api/transfers", json={
            "from_account": "Chequing", "to_account": "Savings",
            "amount": 500, "date": "2026-03-15",
        })
        data = res.get_json()
        assert data["ok"]
        assert "from_id" in data
        assert "to_id" in data

    def test_transfer_creates_two_hidden_txns(self, client):
        client.post("/api/transfers", json={
            "from_account": "Chequing", "to_account": "Savings",
            "amount": 200, "date": "2026-03-15",
        })
        hidden = client.get("/api/transactions?month=2026-03&hidden=1").get_json()
        transfer_txns = [t for t in hidden if "Transfer" in t["name"]]
        assert len(transfer_txns) == 2

    def test_transfer_same_account_rejected(self, client):
        res = client.post("/api/transfers", json={
            "from_account": "Chequing", "to_account": "Chequing",
            "amount": 100, "date": "2026-03-15",
        })
        assert res.status_code == 400

    def test_transfer_zero_amount(self, client):
        res = client.post("/api/transfers", json={
            "from_account": "A", "to_account": "B", "amount": 0,
        })
        assert res.status_code == 400

    def test_transfer_linked(self, client):
        res = client.post("/api/transfers", json={
            "from_account": "Chequing", "to_account": "Savings",
            "amount": 300, "date": "2026-03-15",
        })
        data = res.get_json()
        # Both should have transfer_id linking to each other
        hidden = client.get("/api/transactions?month=2026-03&hidden=1").get_json()
        from_txn = next(t for t in hidden if t["id"] == data["from_id"])
        to_txn = next(t for t in hidden if t["id"] == data["to_id"])
        assert from_txn["transfer_id"] == data["to_id"]
        assert to_txn["transfer_id"] == data["from_id"]


# ── UNDO ──────────────────────────────────────────────────────────────────────

class TestUndo:
    def test_undo_empty(self, client):
        res = client.post("/api/undo", json={})
        assert res.status_code == 404

    def test_undo_status_empty(self, client):
        data = client.get("/api/undo/status").get_json()
        assert data["available"] is False

    def test_undo_delete(self, client):
        seed_transaction(client, name="Will Delete")
        txns = client.get("/api/transactions?month=2026-03").get_json()
        tid = txns[0]["id"]
        client.delete(f"/api/delete/{tid}")
        # Verify deleted
        txns_after = client.get("/api/transactions?month=2026-03").get_json()
        assert len(txns_after) == 0
        # Undo
        status = client.get("/api/undo/status").get_json()
        assert status["available"] is True
        assert status["action"] == "delete"
        res = client.post("/api/undo", json={})
        assert res.get_json()["ok"]
        # Verify restored
        txns_restored = client.get("/api/transactions?month=2026-03").get_json()
        assert len(txns_restored) == 1
        assert txns_restored[0]["name"] == "Will Delete"

    def test_undo_update(self, client):
        seed_transaction(client, name="Original Name", category="Groceries")
        txns = client.get("/api/transactions?month=2026-03").get_json()
        tid = txns[0]["id"]
        # Edit it
        client.patch(f"/api/update/{tid}", json={"name": "Changed", "category": "Eating Out"})
        # Undo
        res = client.post("/api/undo", json={})
        assert res.get_json()["ok"]
        txns_after = client.get("/api/transactions?month=2026-03").get_json()
        assert txns_after[0]["name"] == "Original Name"
        assert txns_after[0]["category"] == "Groceries"

    def test_undo_bulk_delete(self, client):
        seed_transaction(client, name="Tx1")
        seed_transaction(client, name="Tx2", amount="20")
        txns = client.get("/api/transactions?month=2026-03").get_json()
        ids = [t["id"] for t in txns]
        client.post("/api/bulk-delete", json={"ids": ids})
        assert len(client.get("/api/transactions?month=2026-03").get_json()) == 0
        # Undo
        res = client.post("/api/undo", json={})
        assert res.get_json()["ok"]
        restored = client.get("/api/transactions?month=2026-03").get_json()
        assert len(restored) == 2

    def test_undo_consumed_after_use(self, client):
        seed_transaction(client, name="Test")
        txns = client.get("/api/transactions?month=2026-03").get_json()
        client.delete(f"/api/delete/{txns[0]['id']}")
        client.post("/api/undo", json={})
        # Second undo should fail (consumed)
        res = client.post("/api/undo", json={})
        assert res.status_code == 404


# ── OFX IMPORT ────────────────────────────────────────────────────────────────

SAMPLE_OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS><CODE>0</CODE></STATUS>
<DTSERVER>20260315
<LANGUAGE>ENG
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<CURDEF>CAD
<BANKACCTFROM>
<BANKID>123456
<ACCTID>RBC Chequing 1234
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260301
<DTEND>20260331
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260305
<TRNAMT>-45.67
<NAME>TIM HORTONS #1234
<MEMO>COFFEE AND DONUTS
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260315
<TRNAMT>2500.00
<NAME>EMPLOYER DIRECT DEP
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260320
<TRNAMT>-89.99
<NAME>NETFLIX.COM
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""


class TestOFXImport:
    def test_import_ofx(self, client):
        data = {"files": (io.BytesIO(SAMPLE_OFX.encode()), "test.ofx")}
        res = client.post("/api/import-ofx", data=data, content_type="multipart/form-data")
        result = res.get_json()
        assert len(result) == 1
        assert result[0]["added"] == 3
        assert result[0]["bank"] == "OFX Import"

    def test_ofx_transactions_correct(self, client):
        data = {"files": (io.BytesIO(SAMPLE_OFX.encode()), "test.ofx")}
        client.post("/api/import-ofx", data=data, content_type="multipart/form-data")
        txns = client.get("/api/transactions?month=2026-03").get_json()
        assert len(txns) == 3
        # Check one expense
        tim = next(t for t in txns if "TIM HORTONS" in t["name"])
        assert tim["type"] == "Expense"
        assert tim["amount"] == 45.67
        # Check income
        emp = next(t for t in txns if "EMPLOYER" in t["name"])
        assert emp["type"] == "Income"
        assert emp["amount"] == 2500.0

    def test_ofx_duplicate_skipped(self, client):
        data1 = {"files": (io.BytesIO(SAMPLE_OFX.encode()), "test.ofx")}
        client.post("/api/import-ofx", data=data1, content_type="multipart/form-data")
        data2 = {"files": (io.BytesIO(SAMPLE_OFX.encode()), "test2.ofx")}
        res = client.post("/api/import-ofx", data=data2, content_type="multipart/form-data")
        assert res.get_json()[0]["dupes"] == 3

    def test_invalid_ofx(self, client):
        bad = io.BytesIO(b"this is not OFX data")
        res = client.post("/api/import-ofx", data={"files": (bad, "bad.ofx")},
                          content_type="multipart/form-data")
        assert res.get_json()[0]["error"] == "Not a valid OFX/QFX file"

    def test_ofx_account_name(self, client):
        data = {"files": (io.BytesIO(SAMPLE_OFX.encode()), "test.ofx")}
        client.post("/api/import-ofx", data=data, content_type="multipart/form-data")
        txns = client.get("/api/transactions?month=2026-03").get_json()
        assert txns[0]["account"] == "RBC Chequing 1234"

    def test_ofx_via_handleFiles_route(self, client):
        """OFX files should be routed to /api/import-ofx."""
        data = {"files": (io.BytesIO(SAMPLE_OFX.encode()), "bank.qfx")}
        res = client.post("/api/import-ofx", data=data, content_type="multipart/form-data")
        assert res.get_json()[0]["added"] == 3


# ── PWA ───────────────────────────────────────────────────────────────────────

class TestPWA:
    def test_manifest_accessible(self, client):
        res = client.get("/static/manifest.json")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["name"] == "Boreal"
        assert data["display"] == "standalone"

    def test_sw_accessible(self, client):
        res = client.get("/static/sw.js")
        assert res.status_code == 200

    def test_html_has_manifest_link(self, client):
        res = client.get("/")
        assert b'rel="manifest"' in res.data

    def test_html_has_theme_color(self, client):
        res = client.get("/")
        assert b'name="theme-color"' in res.data

    def test_html_has_sw_registration(self, client):
        res = client.get("/")
        assert b"serviceWorker" in res.data


# ── MIGRATIONS V5-V8 ─────────────────────────────────────────────────────────

class TestNewMigrations:
    def test_accounts_table_exists(self, db):
        db.execute("SELECT id, name, account_type, opening_balance FROM accounts LIMIT 0")

    def test_scheduled_transactions_table_exists(self, db):
        db.execute("SELECT id, name, type, category, amount, account, frequency, next_due, enabled FROM scheduled_transactions LIMIT 0")

    def test_transfer_id_column_exists(self, db):
        db.execute("SELECT transfer_id FROM transactions LIMIT 0")

    def test_undo_history_table_exists(self, db):
        db.execute("SELECT id, action, data, created_at FROM undo_history LIMIT 0")
