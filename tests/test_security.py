"""Tests for security: SECRET_KEY, upload limit, XSS storage, CSRF, hashing."""
import hashlib
import os
import sqlite3
import tempfile


def test_secret_key_is_set(app):
    assert app.secret_key is not None
    assert app.secret_key != ""


def test_secret_key_not_hardcoded_default(app):
    """Secret key should NOT be the old hardcoded fallback."""
    assert app.secret_key != "dev-change-me-in-production"


def test_secret_key_persists_to_file(monkeypatch, tmp_path):
    """Auto-generated key should be written to .secret_key and reused."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import canada_finance as cf
    monkeypatch.setattr(cf, "PROJECT_ROOT", str(tmp_path))

    from canada_finance import _get_secret_key
    key1 = _get_secret_key()
    key2 = _get_secret_key()
    assert key1 == key2
    assert os.path.isfile(os.path.join(str(tmp_path), ".secret_key"))


def test_secret_key_from_env(monkeypatch):
    """SECRET_KEY env var should take priority."""
    monkeypatch.setenv("SECRET_KEY", "my-test-secret")
    from canada_finance import _get_secret_key
    assert _get_secret_key() == "my-test-secret"


def test_max_content_length_is_set(app):
    assert app.config["MAX_CONTENT_LENGTH"] == 16 * 1024 * 1024


def test_upload_limit_enforced(client, app):
    """Oversized uploads should return 413."""
    app.config["MAX_CONTENT_LENGTH"] = 100
    import io
    data = {"files": (io.BytesIO(b"x" * 200), "big.csv")}
    r = client.post("/api/import", data=data, content_type="multipart/form-data")
    assert r.status_code == 413


def test_xss_stored_not_escaped_server_side(client):
    """XSS payloads are stored as-is in the DB (escaping is frontend responsibility)."""
    from tests.conftest import seed_transaction
    seed_transaction(client, name='<script>alert("xss")</script>')
    txns = client.get("/api/transactions?month=2026-03").get_json()
    assert '<script>' in txns[0]["name"]


def test_index_page_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"CanadaFinance" in r.data


# ── CSRF ───────────────────────────────────────────────────────────────────────

def test_csrf_blocks_post_without_token(app):
    """Non-test apps should reject POST requests missing the CSRF token."""
    app.config["TESTING"] = False
    c = app.test_client()
    r = c.post("/api/add", json={"date": "2026-01-01", "type": "Expense",
               "name": "Test", "category": "Misc", "amount": "5", "account": "X"})
    assert r.status_code == 403
    assert "CSRF" in r.get_json()["error"]


def test_csrf_allows_post_with_valid_token(app):
    """POST with a valid CSRF token should succeed."""
    app.config["TESTING"] = False
    c = app.test_client()
    # Fetch token (this also sets the session cookie)
    token_resp = c.get("/api/csrf-token")
    token = token_resp.get_json()["csrf_token"]
    assert len(token) == 64  # hex(32 bytes)
    # Use it
    r = c.post("/api/add", json={"date": "2026-01-01", "type": "Expense",
               "name": "Test", "category": "Misc", "amount": "5", "account": "X"},
               headers={"X-CSRF-Token": token})
    assert r.status_code == 200


def test_csrf_rejects_wrong_token(app):
    """POST with an invalid CSRF token should be rejected."""
    app.config["TESTING"] = False
    c = app.test_client()
    c.get("/api/csrf-token")  # establish session
    r = c.post("/api/add", json={"date": "2026-01-01", "type": "Expense",
               "name": "Test", "category": "Misc", "amount": "5", "account": "X"},
               headers={"X-CSRF-Token": "wrong-token"})
    assert r.status_code == 403


def test_csrf_skipped_for_get(app):
    """GET requests should never require a CSRF token."""
    app.config["TESTING"] = False
    c = app.test_client()
    r = c.get("/api/categories")
    assert r.status_code == 200


def test_csrf_skipped_in_test_mode(client):
    """In TESTING mode, CSRF should be bypassed."""
    r = client.post("/api/add", json={"date": "2026-01-01", "type": "Expense",
                    "name": "Test", "category": "Misc", "amount": "5", "account": "X"})
    assert r.status_code == 200


# ── TX HASH ────────────────────────────────────────────────────────────────────

def test_tx_hash_uses_sha256():
    """tx_hash should return a SHA256 hex digest (64 chars), not MD5 (32 chars)."""
    from canada_finance.models.database import tx_hash
    h = tx_hash("2026-01-01", "Test", 10.00, "Acct")
    assert len(h) == 64  # SHA256
    # Verify it matches a manual SHA256
    expected = hashlib.sha256("2026-01-01|Test|10.00|Acct".encode()).hexdigest()
    assert h == expected


def test_md5_to_sha256_migration(app):
    """Old MD5 hashes should be auto-migrated to SHA256 on init_db."""
    db_path = app.config["DB_PATH"]
    # Insert a row with an MD5 hash directly
    md5_hash = hashlib.md5("2026-01-01|Fake|5.00|Bank".encode()).hexdigest()
    assert len(md5_hash) == 32
    with sqlite3.connect(db_path) as db:
        db.execute("""INSERT INTO transactions
            (date,type,name,category,amount,account,notes,source,tx_hash,hidden)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("2026-01-01", "Expense", "Fake", "Misc", 5.00, "Bank", "", "csv", md5_hash, 0))
        db.commit()
    # Re-run init_db (simulates app restart)
    from canada_finance.models.database import init_db
    init_db(app)
    # Verify the hash was upgraded
    with sqlite3.connect(db_path) as db:
        row = db.execute("SELECT tx_hash FROM transactions WHERE name='Fake'").fetchone()
        new_hash = row[0]
    assert len(new_hash) == 64  # SHA256
    expected = hashlib.sha256("2026-01-01|Fake|5.00|Bank".encode()).hexdigest()
    assert new_hash == expected


# ── ERROR HANDLING ─────────────────────────────────────────────────────────────

def test_add_transaction_bad_amount_no_leak(client):
    """Invalid amount should return a generic error, not a Python traceback."""
    r = client.post("/api/add", json={
        "date": "2026-01-01", "type": "Expense", "name": "Test",
        "category": "Misc", "amount": "not-a-number", "account": "X",
    })
    assert r.status_code == 400
    body = r.get_json()
    assert "error" in body
    # Should NOT contain Python exception class names
    assert "Traceback" not in body["error"]
    assert "ValueError" not in body["error"]


# ── HEALTH ENDPOINT ───────────────────────────────────────────────────────────

def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert "db_exists" in data
