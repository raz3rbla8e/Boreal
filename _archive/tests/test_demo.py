"""Tests for DEMO_MODE functionality."""
import os
import tempfile

import pytest

from canada_finance import create_app
from canada_finance.models.database import get_db


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def demo_app(monkeypatch):
    """Create app with DEMO_MODE=true and a temp database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DEMO_MODE", "true")

    import canada_finance.config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    monkeypatch.setattr(cfg, "DEMO_MODE", True)
    import canada_finance as cf
    monkeypatch.setattr(cf, "DB_PATH", db_path)
    monkeypatch.setattr(cf, "DEMO_MODE", True)

    app = create_app()
    app.config.update({"TESTING": True})

    yield app

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture()
def demo_client(demo_app):
    return demo_app.test_client()


@pytest.fixture()
def normal_app(monkeypatch):
    """Create app with DEMO_MODE=false (default) and a temp database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DEMO_MODE", "false")

    import canada_finance.config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    monkeypatch.setattr(cfg, "DEMO_MODE", False)
    import canada_finance as cf
    monkeypatch.setattr(cf, "DB_PATH", db_path)
    monkeypatch.setattr(cf, "DEMO_MODE", False)

    app = create_app()
    app.config.update({"TESTING": True})

    yield app

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture()
def normal_client(normal_app):
    return normal_app.test_client()


# ── Helper ─────────────────────────────────────────────────────────────────────

def _seed_one(client):
    """Seed a transaction via the API (only works when demo mode is off)."""
    return client.post("/api/add", json={
        "date": "2026-03-15", "type": "Expense", "name": "Tim Hortons",
        "category": "Eating Out", "amount": "5.00", "account": "Tangerine Chequing",
    })


# ── GET /api/demo ──────────────────────────────────────────────────────────────

class TestDemoEndpoint:
    def test_demo_true(self, demo_client):
        res = demo_client.get("/api/demo")
        assert res.status_code == 200
        assert res.get_json() == {"demo": True}

    def test_demo_false(self, normal_client):
        res = normal_client.get("/api/demo")
        assert res.status_code == 200
        assert res.get_json() == {"demo": False}


# ── Auto-seed on startup ──────────────────────────────────────────────────────

class TestAutoSeed:
    def test_demo_seeds_sample_data(self, demo_app):
        """Demo mode should auto-seed transactions from sample_data on startup."""
        with demo_app.app_context():
            db = get_db()
            count = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            assert count > 0, "Demo mode should have seeded sample transactions"

    def test_normal_mode_no_seed(self, normal_app):
        """Normal mode should NOT seed any transactions."""
        with normal_app.app_context():
            db = get_db()
            count = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            assert count == 0


# ── POST /api/demo/reset ──────────────────────────────────────────────────────

class TestDemoReset:
    def test_reset_works_in_demo_mode(self, demo_app, demo_client):
        """Reset should wipe and re-seed transactions."""
        with demo_app.app_context():
            db = get_db()
            original = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]

        res = demo_client.post("/api/demo/reset")
        assert res.status_code == 200
        data = res.get_json()
        assert data["ok"] is True

        with demo_app.app_context():
            db = get_db()
            after = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            assert after > 0, "Reset should re-seed data"

    def test_reset_blocked_in_normal_mode(self, normal_client):
        """Reset should return 403 when not in demo mode."""
        res = normal_client.post("/api/demo/reset")
        assert res.status_code == 403


# ── Demo guard: blocked routes ─────────────────────────────────────────────────

class TestDemoGuardBlocked:
    """Routes that should return 403 in demo mode."""

    def test_import_blocked(self, demo_client):
        res = demo_client.post("/api/import")
        assert res.status_code == 403
        assert "demo" in res.get_json()["error"].lower()

    def test_restore_blocked(self, demo_client):
        res = demo_client.post("/api/restore")
        assert res.status_code == 403

    def test_save_bank_config_blocked(self, demo_client):
        res = demo_client.post("/api/save-bank-config")
        assert res.status_code == 403

    def test_add_transaction_blocked(self, demo_client):
        res = demo_client.post("/api/add", json={
            "date": "2026-03-15", "type": "Expense", "name": "Test",
            "category": "Eating Out", "amount": "5.00", "account": "Cash",
        })
        assert res.status_code == 403

    def test_delete_transaction_blocked(self, demo_client):
        res = demo_client.delete("/api/delete/1")
        assert res.status_code == 403

    def test_bulk_delete_blocked(self, demo_client):
        res = demo_client.post("/api/bulk-delete", json={"ids": [1]})
        assert res.status_code == 403

    def test_add_category_blocked(self, demo_client):
        res = demo_client.post("/api/categories", json={
            "name": "Test", "type": "Expense", "icon": "🧪",
        })
        assert res.status_code == 403

    def test_delete_category_blocked(self, demo_client):
        res = demo_client.delete("/api/categories/1")
        assert res.status_code == 403

    def test_update_category_blocked(self, demo_client):
        res = demo_client.patch("/api/categories/1", json={"name": "X"})
        assert res.status_code == 403

    def test_settings_blocked(self, demo_client):
        res = demo_client.post("/api/settings", json={"theme": "light"})
        assert res.status_code == 403

    def test_create_rule_blocked(self, demo_client):
        res = demo_client.post("/api/rules", json={
            "name": "test", "action": "hide",
            "conditions": [{"field": "description", "operator": "contains", "value": "x"}],
        })
        assert res.status_code == 403

    def test_bulk_create_rules_blocked(self, demo_client):
        res = demo_client.post("/api/rules/bulk-create", json={"rules": []})
        assert res.status_code == 403

    def test_update_rule_blocked(self, demo_client):
        res = demo_client.patch("/api/rules/1", json={"name": "x"})
        assert res.status_code == 403

    def test_delete_rule_blocked(self, demo_client):
        res = demo_client.delete("/api/rules/1")
        assert res.status_code == 403

    def test_reorder_rules_blocked(self, demo_client):
        res = demo_client.post("/api/rules/reorder", json={"order": []})
        assert res.status_code == 403

    def test_load_rule_template_blocked(self, demo_client):
        res = demo_client.post("/api/rule-templates/load", json={"file": "default.yaml"})
        assert res.status_code == 403

    def test_set_budget_blocked(self, demo_client):
        res = demo_client.post("/api/budgets", json={"category": "Groceries", "amount": 500})
        assert res.status_code == 403

    def test_delete_budget_blocked(self, demo_client):
        res = demo_client.delete("/api/budgets/Groceries")
        assert res.status_code == 403

    def test_delete_learned_blocked(self, demo_client):
        res = demo_client.delete("/api/learned/tim%20hortons")
        assert res.status_code == 403


# ── Demo guard: allowed routes ─────────────────────────────────────────────────

class TestDemoGuardAllowed:
    """Routes that should still work in demo mode."""

    def test_get_demo(self, demo_client):
        res = demo_client.get("/api/demo")
        assert res.status_code == 200

    def test_get_health(self, demo_client):
        res = demo_client.get("/api/health")
        assert res.status_code == 200

    def test_get_transactions(self, demo_client):
        res = demo_client.get("/api/transactions")
        assert res.status_code == 200

    def test_get_months(self, demo_client):
        res = demo_client.get("/api/months")
        assert res.status_code == 200

    def test_get_categories(self, demo_client):
        res = demo_client.get("/api/categories")
        assert res.status_code == 200

    def test_get_settings(self, demo_client):
        res = demo_client.get("/api/settings")
        assert res.status_code == 200

    def test_get_rules(self, demo_client):
        res = demo_client.get("/api/rules")
        assert res.status_code == 200

    def test_get_budgets(self, demo_client):
        res = demo_client.get("/api/budgets")
        assert res.status_code == 200

    def test_get_export(self, demo_client):
        res = demo_client.get("/api/export")
        assert res.status_code == 200

    def test_edit_transaction_allowed(self, demo_app, demo_client):
        """Editing transactions should work in demo mode."""
        with demo_app.app_context():
            db = get_db()
            row = db.execute("SELECT id FROM transactions LIMIT 1").fetchone()
        if row:
            res = demo_client.patch(f"/api/update/{row['id']}", json={
                "category": "Groceries",
            })
            assert res.status_code == 200

    def test_hide_transaction_allowed(self, demo_app, demo_client):
        """Hiding transactions should work in demo mode."""
        with demo_app.app_context():
            db = get_db()
            row = db.execute("SELECT id FROM transactions LIMIT 1").fetchone()
        if row:
            res = demo_client.patch(f"/api/transactions/{row['id']}/hide")
            assert res.status_code == 200

    def test_unhide_transaction_allowed(self, demo_app, demo_client):
        """Unhiding transactions should work in demo mode."""
        with demo_app.app_context():
            db = get_db()
            row = db.execute("SELECT id FROM transactions LIMIT 1").fetchone()
        if row:
            res = demo_client.patch(f"/api/transactions/{row['id']}/unhide")
            assert res.status_code == 200

    def test_bulk_categorize_allowed(self, demo_app, demo_client):
        """Bulk categorize should work in demo mode."""
        with demo_app.app_context():
            db = get_db()
            rows = db.execute("SELECT id FROM transactions LIMIT 2").fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            res = demo_client.post("/api/bulk-categorize", json={
                "ids": ids, "category": "Groceries",
            })
            assert res.status_code == 200

    def test_bulk_hide_allowed(self, demo_app, demo_client):
        """Bulk hide should work in demo mode."""
        with demo_app.app_context():
            db = get_db()
            rows = db.execute("SELECT id FROM transactions LIMIT 2").fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            res = demo_client.post("/api/bulk-hide", json={"ids": ids})
            assert res.status_code == 200

    def test_bulk_unhide_allowed(self, demo_app, demo_client):
        """Bulk unhide should work in demo mode."""
        with demo_app.app_context():
            db = get_db()
            rows = db.execute("SELECT id FROM transactions LIMIT 2").fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            res = demo_client.post("/api/bulk-unhide", json={"ids": ids})
            assert res.status_code == 200

    def test_rules_test_allowed(self, demo_client):
        """Testing rules should work in demo mode."""
        res = demo_client.post("/api/rules/test", json={
            "conditions": [{"field": "description", "operator": "contains", "value": "test"}],
        })
        assert res.status_code == 200

    def test_rules_apply_all_allowed(self, demo_client):
        """Applying all rules should work in demo mode."""
        res = demo_client.post("/api/rules/apply-all")
        assert res.status_code == 200


# ── Normal mode: nothing blocked ──────────────────────────────────────────────

class TestNormalModeUnaffected:
    """When DEMO_MODE=false, no routes should be blocked."""

    def test_add_works(self, normal_client):
        res = _seed_one(normal_client)
        assert res.status_code == 200

    def test_settings_works(self, normal_client):
        res = normal_client.post("/api/settings", json={"theme": "light"})
        assert res.status_code == 200

    def test_add_category_works(self, normal_client):
        res = normal_client.post("/api/categories", json={
            "name": "TestCat", "type": "Expense", "icon": "🧪",
        })
        assert res.status_code == 200

    def test_demo_endpoint_returns_false(self, normal_client):
        res = normal_client.get("/api/demo")
        data = res.get_json()
        assert data["demo"] is False
