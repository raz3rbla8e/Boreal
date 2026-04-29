"""Tests for CSV import, detect, wizard preview, export, and file size limit."""
import io

from tests.conftest import SAMPLE_TANGERINE_CSV, XSS_CSV


# ── Import ─────────────────────────────────────────────────────────────────────

def test_import_tangerine_csv(client):
    data = {"files": (io.BytesIO(SAMPLE_TANGERINE_CSV.encode()), "tangerine.csv")}
    r = client.post("/api/import", data=data, content_type="multipart/form-data")
    result = r.get_json()
    assert r.status_code == 200
    assert len(result) == 1
    assert result[0]["added"] >= 1


def test_import_duplicate_detection(client):
    data1 = {"files": (io.BytesIO(SAMPLE_TANGERINE_CSV.encode()), "tangerine.csv")}
    r1 = client.post("/api/import", data=data1, content_type="multipart/form-data")
    first_added = r1.get_json()[0]["added"]

    data2 = {"files": (io.BytesIO(SAMPLE_TANGERINE_CSV.encode()), "tangerine.csv")}
    r2 = client.post("/api/import", data=data2, content_type="multipart/form-data")
    assert r2.get_json()[0]["added"] == 0
    assert r2.get_json()[0]["dupes"] == first_added


def test_import_xss_payload_stored(client):
    """XSS payloads in CSV are stored in DB (escaping happens client-side)."""
    data = {"files": (io.BytesIO(XSS_CSV.encode()), "xss.csv")}
    client.post("/api/import", data=data, content_type="multipart/form-data")
    txns = client.get("/api/transactions?search=onerror").get_json()
    assert len(txns) >= 1
    assert "<img" in txns[0]["name"]


# ── File size limit ────────────────────────────────────────────────────────────

def test_import_file_too_large(client, app):
    """Files larger than MAX_CONTENT_LENGTH should be rejected with 413."""
    app.config["MAX_CONTENT_LENGTH"] = 100  # 100 bytes for testing
    huge = b"x" * 200
    data = {"files": (io.BytesIO(huge), "big.csv")}
    r = client.post("/api/import", data=data, content_type="multipart/form-data")
    assert r.status_code == 413


# ── Detect CSV ─────────────────────────────────────────────────────────────────

def test_detect_known_bank(client):
    data = {"file": (io.BytesIO(SAMPLE_TANGERINE_CSV.encode()), "tangerine.csv")}
    r = client.post("/api/detect-csv", data=data, content_type="multipart/form-data")
    j = r.get_json()
    assert j["detected"] is True


def test_detect_unknown_bank(client):
    unknown_csv = "Col1,Col2,Col3\nfoo,bar,baz\n"
    data = {"file": (io.BytesIO(unknown_csv.encode()), "unknown.csv")}
    r = client.post("/api/detect-csv", data=data, content_type="multipart/form-data")
    j = r.get_json()
    assert j["detected"] is False
    assert "headers" in j
    assert "preview" in j


def test_detect_no_file(client):
    r = client.post("/api/detect-csv", content_type="multipart/form-data")
    assert r.status_code == 400


# ── Preview Parse ──────────────────────────────────────────────────────────────

def test_preview_parse(client):
    raw_csv = "Date,Description,Amount\n2026-03-15,Coffee,4.50\n2026-03-16,Lunch,12.00\n"
    mapping = {
        "date_column": "Date",
        "description_column": "Description",
        "amount_column": "Amount",
        "amount_mode": "single",
        "bank_name": "Test Bank",
        "date_format": "%Y-%m-%d",
    }
    r = client.post("/api/preview-parse", json={"raw_text": raw_csv, "mapping": mapping})
    j = r.get_json()
    assert j["total"] == 2
    assert len(j["transactions"]) == 2


def test_preview_parse_missing_data(client):
    r = client.post("/api/preview-parse", json={})
    assert r.status_code == 400


# ── Save Bank Config ───────────────────────────────────────────────────────────

def test_save_bank_config(client, tmp_path, monkeypatch):
    import canada_finance.routes.import_export as ie
    monkeypatch.setattr(ie, "BANKS_DIR", str(tmp_path))
    monkeypatch.setattr("canada_finance.routes.import_export.BANKS_DIR", str(tmp_path))

    r = client.post("/api/save-bank-config", json={
        "bank_name": "My Test Bank",
        "date_column": "Date",
        "description_column": "Desc",
        "amount_mode": "single",
        "amount_column": "Amount",
        "date_format": "%Y-%m-%d",
        "detection_headers": ["Date", "Desc", "Amount"],
    })
    j = r.get_json()
    assert j["ok"] is True
    # Verify YAML was created
    import os
    yamls = [f for f in os.listdir(tmp_path) if f.endswith(".yaml")]
    assert len(yamls) == 1


def test_save_bank_config_missing_name(client):
    r = client.post("/api/save-bank-config", json={
        "bank_name": "",
        "date_column": "Date",
        "description_column": "Desc",
    })
    assert r.status_code == 400


# ── Export ─────────────────────────────────────────────────────────────────────

def test_export_csv(client):
    from tests.conftest import seed_transaction
    seed_transaction(client)
    r = client.get("/api/export?month=2026-03")
    assert r.status_code == 200
    assert "text/csv" in r.content_type
    assert b"Tim Hortons" in r.data


def test_export_all_time(client):
    from tests.conftest import seed_transaction
    seed_transaction(client, date="2026-03-15")
    seed_transaction(client, date="2026-04-01", name="Costco", amount="55.00")
    r = client.get("/api/export?month=")
    assert r.status_code == 200
    assert b"Tim Hortons" in r.data
    assert b"Costco" in r.data


# ── safe_abs_float ─────────────────────────────────────────────────────────────

def test_safe_abs_float_strips_sign():
    """safe_abs_float should always return absolute value."""
    from canada_finance.services.helpers import safe_abs_float
    assert safe_abs_float("-12.50") == 12.50
    assert safe_abs_float("12.50") == 12.50
    assert safe_abs_float("$1,234.56") == 1234.56


def test_safe_abs_float_unicode_minus():
    """Unicode minus signs should be handled."""
    from canada_finance.services.helpers import safe_abs_float
    assert safe_abs_float("\u221212.50") == 12.50  # U+2212 MINUS SIGN
    assert safe_abs_float("\u201312.50") == 12.50  # U+2013 EN DASH


def test_safe_abs_float_empty():
    from canada_finance.services.helpers import safe_abs_float
    assert safe_abs_float("") == 0.0
    assert safe_abs_float("   ") == 0.0


# ── Export → Re-import Round Trip ──────────────────────────────────────────────

def test_export_reimport_round_trip(client):
    """Export CSV, delete all transactions, re-import — data should survive."""
    from tests.conftest import seed_transaction
    seed_transaction(client, name="Netflix", category="Subscriptions",
                     type="Expense", amount="16.49", account="TD Chequing")
    seed_transaction(client, name="Payroll", category="Job",
                     type="Income", amount="3000.00", account="Tangerine Chequing")

    # Export
    export_resp = client.get("/api/export")
    assert export_resp.status_code == 200
    csv_data = export_resp.data

    # Delete all transactions
    txns = client.get("/api/transactions?month=2026-03").get_json()
    for t in txns:
        client.delete(f"/api/delete/{t['id']}")
    assert len(client.get("/api/transactions?month=2026-03").get_json()) == 0

    # Re-import the exported CSV
    r = client.post("/api/import",
                    data={"files": (io.BytesIO(csv_data), "export.csv")},
                    content_type="multipart/form-data")
    result = r.get_json()
    assert result[0]["bank"] == "Canada Finance Export"
    assert result[0]["added"] == 2

    # Verify data integrity
    txns = client.get("/api/transactions?month=2026-03").get_json()
    assert len(txns) == 2
    netflix = next(t for t in txns if t["name"] == "Netflix")
    payroll = next(t for t in txns if t["name"] == "Payroll")
    assert netflix["category"] == "Subscriptions"
    assert netflix["type"] == "Expense"
    assert netflix["amount"] == 16.49
    assert netflix["account"] == "TD Chequing"
    assert payroll["category"] == "Job"
    assert payroll["type"] == "Income"
    assert payroll["amount"] == 3000.00
    assert payroll["account"] == "Tangerine Chequing"


def test_export_reimport_no_duplicates(client):
    """Re-importing the same export without deleting should produce duplicates=2."""
    from tests.conftest import seed_transaction
    seed_transaction(client, name="Netflix", category="Subscriptions",
                     type="Expense", amount="16.49")
    seed_transaction(client, name="Payroll", category="Job",
                     type="Income", amount="3000.00")
    csv_data = client.get("/api/export").data
    r = client.post("/api/import",
                    data={"files": (io.BytesIO(csv_data), "export.csv")},
                    content_type="multipart/form-data")
    result = r.get_json()
    assert result[0]["added"] == 0
    assert result[0]["dupes"] == 2


# ── Backup / Restore ──────────────────────────────────────────────────────────

def test_backup_download(client):
    from tests.conftest import seed_transaction
    seed_transaction(client)
    r = client.get("/api/backup")
    assert r.status_code == 200
    assert r.content_type == "application/octet-stream"
    assert r.data[:16] == b"SQLite format 3\x00"
    assert "finance_backup_" in r.headers["Content-Disposition"]


def test_restore_valid_db(client, app):
    """Restore should accept a valid SQLite .db file."""
    from tests.conftest import seed_transaction
    # Seed data so backup has content
    seed_transaction(client, name="Before Restore")
    backup = client.get("/api/backup").data
    # Delete the transaction
    txns = client.get("/api/transactions?month=2026-03").get_json()
    client.delete(f"/api/delete/{txns[0]['id']}")
    assert len(client.get("/api/transactions?month=2026-03").get_json()) == 0
    # Restore from backup
    r = client.post("/api/restore",
                    data={"file": (io.BytesIO(backup), "backup.db")},
                    content_type="multipart/form-data")
    assert r.get_json()["ok"] is True


def test_restore_rejects_non_db(client):
    r = client.post("/api/restore",
                    data={"file": (io.BytesIO(b"not a database"), "bad.db")},
                    content_type="multipart/form-data")
    assert r.status_code == 400


def test_restore_rejects_wrong_extension(client):
    r = client.post("/api/restore",
                    data={"file": (io.BytesIO(b"something"), "data.csv")},
                    content_type="multipart/form-data")
    assert r.status_code == 400


def test_restore_no_file(client):
    r = client.post("/api/restore", content_type="multipart/form-data")
    assert r.status_code == 400
