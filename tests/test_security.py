"""Tests for security: SECRET_KEY, upload limit, XSS storage."""


def test_secret_key_is_set(app):
    assert app.secret_key is not None
    assert app.secret_key != ""


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
