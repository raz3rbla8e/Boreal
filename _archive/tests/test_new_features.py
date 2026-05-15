"""Tests for 6 new features: split transactions, spending trends, savings goals,
category groups, budget alerts (frontend-only), PDF export."""
import json

import pytest

from tests.conftest import seed_transaction


# ── SPLIT TRANSACTIONS ────────────────────────────────────────────────────────

class TestSplitTransactions:
    def _add_txn(self, client):
        seed_transaction(client, name="Costco", amount="100.00", category="Groceries")
        txns = client.get("/api/transactions?month=2026-03").get_json()
        return txns[0]["id"]

    def test_split_basic(self, client):
        tid = self._add_txn(client)
        res = client.post(f"/api/transactions/{tid}/split", json={
            "splits": [
                {"category": "Groceries", "amount": 60},
                {"category": "Household", "amount": 40},
            ]
        })
        data = res.get_json()
        assert data["ok"]
        assert data["children"] == 2

    def test_split_requires_2_rows(self, client):
        tid = self._add_txn(client)
        res = client.post(f"/api/transactions/{tid}/split", json={
            "splits": [{"category": "Groceries", "amount": 100}]
        })
        assert res.status_code == 400

    def test_split_total_must_match(self, client):
        tid = self._add_txn(client)
        res = client.post(f"/api/transactions/{tid}/split", json={
            "splits": [
                {"category": "Groceries", "amount": 60},
                {"category": "Household", "amount": 30},
            ]
        })
        assert res.status_code == 400
        assert "must equal" in res.get_json()["error"]

    def test_split_hides_parent(self, client):
        tid = self._add_txn(client)
        client.post(f"/api/transactions/{tid}/split", json={
            "splits": [
                {"category": "Groceries", "amount": 50},
                {"category": "Household", "amount": 50},
            ]
        })
        # Parent should be hidden
        hidden = client.get("/api/transactions/hidden-count").get_json()
        assert hidden["count"] == 1

    def test_get_splits(self, client):
        tid = self._add_txn(client)
        client.post(f"/api/transactions/{tid}/split", json={
            "splits": [
                {"category": "Groceries", "amount": 70},
                {"category": "Eating Out", "amount": 30},
            ]
        })
        splits = client.get(f"/api/transactions/{tid}/splits").get_json()
        assert len(splits) == 2
        assert splits[0]["parent_id"] == tid

    def test_unsplit(self, client):
        tid = self._add_txn(client)
        client.post(f"/api/transactions/{tid}/split", json={
            "splits": [
                {"category": "Groceries", "amount": 50},
                {"category": "Household", "amount": 50},
            ]
        })
        res = client.delete(f"/api/transactions/{tid}/unsplit")
        assert res.get_json()["ok"]
        # Parent should be visible again
        hidden = client.get("/api/transactions/hidden-count").get_json()
        assert hidden["count"] == 0

    def test_unsplit_not_split_fails(self, client):
        tid = self._add_txn(client)
        res = client.delete(f"/api/transactions/{tid}/unsplit")
        assert res.status_code == 400

    def test_cannot_split_child(self, client):
        tid = self._add_txn(client)
        client.post(f"/api/transactions/{tid}/split", json={
            "splits": [
                {"category": "Groceries", "amount": 50},
                {"category": "Household", "amount": 50},
            ]
        })
        splits = client.get(f"/api/transactions/{tid}/splits").get_json()
        child_id = splits[0]["id"]
        res = client.post(f"/api/transactions/{child_id}/split", json={
            "splits": [
                {"category": "A", "amount": 25},
                {"category": "B", "amount": 25},
            ]
        })
        assert res.status_code == 400

    def test_split_nonexistent_transaction(self, client):
        res = client.post("/api/transactions/9999/split", json={
            "splits": [
                {"category": "A", "amount": 50},
                {"category": "B", "amount": 50},
            ]
        })
        assert res.status_code == 404


# ── SPENDING TRENDS ───────────────────────────────────────────────────────────

class TestSpendingTrends:
    def test_trends_empty(self, client):
        res = client.get("/api/trends")
        assert res.get_json() == []

    def test_trends_with_data(self, client):
        seed_transaction(client, date="2026-01-15", amount="100", type="Expense")
        seed_transaction(client, date="2026-01-15", amount="200", type="Income", name="Salary", category="Salary")
        seed_transaction(client, date="2026-02-15", amount="150", type="Expense", name="Store")
        res = client.get("/api/trends?months=6")
        data = res.get_json()
        assert len(data) == 2
        assert data[0]["month"] == "2026-01"
        assert data[0]["expenses"] == 100

    def test_trends_respects_limit(self, client):
        for m in range(1, 7):
            seed_transaction(client, date=f"2026-{m:02d}-15", name=f"Store{m}", amount="50")
        res = client.get("/api/trends?months=3")
        data = res.get_json()
        assert len(data) == 3

    def test_trends_max_24(self, client):
        res = client.get("/api/trends?months=100")
        # Should not crash, just return what's available
        assert res.status_code == 200


# ── SAVINGS GOALS ─────────────────────────────────────────────────────────────

class TestSavingsGoals:
    def test_add_goal(self, client):
        res = client.post("/api/goals", json={"name": "Vacation", "target_amount": 5000, "icon": "✈️"})
        assert res.get_json()["ok"]

    def test_list_goals(self, client):
        client.post("/api/goals", json={"name": "Vacation", "target_amount": 5000})
        client.post("/api/goals", json={"name": "Car", "target_amount": 20000})
        goals = client.get("/api/goals").get_json()
        assert len(goals) == 2

    def test_goal_requires_name(self, client):
        res = client.post("/api/goals", json={"name": "", "target_amount": 1000})
        assert res.status_code == 400

    def test_goal_requires_positive_target(self, client):
        res = client.post("/api/goals", json={"name": "Test", "target_amount": -100})
        assert res.status_code == 400

    def test_update_goal(self, client):
        client.post("/api/goals", json={"name": "Vacation", "target_amount": 5000})
        goals = client.get("/api/goals").get_json()
        gid = goals[0]["id"]
        res = client.patch(f"/api/goals/{gid}", json={"name": "Trip", "target_amount": 3000})
        assert res.get_json()["ok"]

    def test_delete_goal(self, client):
        client.post("/api/goals", json={"name": "Vacation", "target_amount": 5000})
        goals = client.get("/api/goals").get_json()
        gid = goals[0]["id"]
        res = client.delete(f"/api/goals/{gid}")
        assert res.get_json()["ok"]
        assert len(client.get("/api/goals").get_json()) == 0

    def test_contribute_to_goal(self, client):
        client.post("/api/goals", json={"name": "Vacation", "target_amount": 5000})
        goals = client.get("/api/goals").get_json()
        gid = goals[0]["id"]
        res = client.post(f"/api/goals/{gid}/contribute", json={"amount": 500})
        data = res.get_json()
        assert data["ok"]
        assert data["current_amount"] == 500

    def test_contribute_accumulates(self, client):
        client.post("/api/goals", json={"name": "Vacation", "target_amount": 5000})
        goals = client.get("/api/goals").get_json()
        gid = goals[0]["id"]
        client.post(f"/api/goals/{gid}/contribute", json={"amount": 500})
        res = client.post(f"/api/goals/{gid}/contribute", json={"amount": 300})
        assert res.get_json()["current_amount"] == 800

    def test_contribute_invalid_amount(self, client):
        client.post("/api/goals", json={"name": "Test", "target_amount": 1000})
        goals = client.get("/api/goals").get_json()
        gid = goals[0]["id"]
        res = client.post(f"/api/goals/{gid}/contribute", json={"amount": -50})
        assert res.status_code == 400

    def test_contribute_nonexistent_goal(self, client):
        res = client.post("/api/goals/9999/contribute", json={"amount": 100})
        assert res.status_code == 404

    def test_update_nonexistent_goal(self, client):
        res = client.patch("/api/goals/9999", json={"name": "X"})
        assert res.status_code == 404


# ── CATEGORY GROUPS ───────────────────────────────────────────────────────────

class TestCategoryGroups:
    def test_default_groups_exist(self, client):
        groups = client.get("/api/category-groups").get_json()
        names = [g["name"] for g in groups]
        assert "Essentials" in names
        assert "Lifestyle" in names

    def test_add_group(self, client):
        res = client.post("/api/category-groups", json={"name": "Fun Stuff"})
        assert res.get_json()["ok"]

    def test_add_duplicate_group(self, client):
        client.post("/api/category-groups", json={"name": "Fun"})
        res = client.post("/api/category-groups", json={"name": "Fun"})
        assert res.status_code == 409

    def test_rename_group(self, client):
        client.post("/api/category-groups", json={"name": "Fun"})
        groups = client.get("/api/category-groups").get_json()
        gid = [g for g in groups if g["name"] == "Fun"][0]["id"]
        res = client.patch(f"/api/category-groups/{gid}", json={"name": "Recreation"})
        assert res.get_json()["ok"]

    def test_delete_group(self, client):
        client.post("/api/category-groups", json={"name": "Temp"})
        groups = client.get("/api/category-groups").get_json()
        gid = [g for g in groups if g["name"] == "Temp"][0]["id"]
        res = client.delete(f"/api/category-groups/{gid}")
        assert res.get_json()["ok"]

    def test_delete_group_ungrouped_cats(self, client):
        """Deleting a group should set its categories to ungrouped."""
        # Assign a category to the group
        cats = client.get("/api/categories").get_json()
        expense_cat = [c for c in cats if c["type"] == "Expense"][0]
        client.post("/api/category-groups", json={"name": "TestG"})
        groups = client.get("/api/category-groups").get_json()
        gid = [g for g in groups if g["name"] == "TestG"][0]["id"]
        client.patch(f"/api/categories/{expense_cat['id']}", json={"group_id": gid})
        # Now delete the group
        client.delete(f"/api/category-groups/{gid}")
        # Category should have null group_id
        cats = client.get("/api/categories").get_json()
        cat = [c for c in cats if c["id"] == expense_cat["id"]][0]
        assert cat["group_id"] is None

    def test_group_empty_name(self, client):
        res = client.post("/api/category-groups", json={"name": ""})
        assert res.status_code == 400

    def test_rename_nonexistent_group(self, client):
        res = client.patch("/api/category-groups/9999", json={"name": "X"})
        assert res.status_code == 404

    def test_categories_include_group_id(self, client):
        cats = client.get("/api/categories").get_json()
        assert "group_id" in cats[0]


# ── PDF EXPORT ────────────────────────────────────────────────────────────────

class TestPdfExport:
    def test_pdf_requires_month(self, client):
        res = client.get("/api/export/pdf")
        assert res.status_code == 400

    def test_pdf_summary_only(self, client):
        seed_transaction(client)
        res = client.get("/api/export/pdf?month=2026-03")
        assert res.status_code == 200
        assert res.content_type == "application/pdf"
        assert res.data[:4] == b"%PDF"

    def test_pdf_with_transactions(self, client):
        seed_transaction(client)
        res = client.get("/api/export/pdf?month=2026-03&include_transactions=1")
        assert res.status_code == 200
        assert res.data[:4] == b"%PDF"

    def test_pdf_empty_month(self, client):
        res = client.get("/api/export/pdf?month=2020-01")
        assert res.status_code == 200
        assert res.data[:4] == b"%PDF"


# ── MIGRATION TESTS ──────────────────────────────────────────────────────────

class TestNewMigrations:
    def test_parent_id_column_exists(self, client, db):
        db.execute("SELECT parent_id FROM transactions LIMIT 0")

    def test_savings_goals_table_exists(self, client, db):
        db.execute("SELECT * FROM savings_goals LIMIT 0")

    def test_category_groups_table_exists(self, client, db):
        db.execute("SELECT * FROM category_groups LIMIT 0")

    def test_group_id_column_exists(self, client, db):
        db.execute("SELECT group_id FROM categories LIMIT 0")

    def test_default_groups_seeded(self, client, db):
        rows = db.execute("SELECT name FROM category_groups ORDER BY sort_order").fetchall()
        names = [r["name"] for r in rows]
        assert "Essentials" in names
        assert "Lifestyle" in names
