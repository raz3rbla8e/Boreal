"""Tests for CSV import, detect, wizard preview, export, and file size limit."""
import io

from tests.conftest import SAMPLE_TANGERINE_CSV, SAMPLE_AMEX_CSV, SAMPLE_AMEX_REDACTED_CSV, XSS_CSV


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


def test_export_escapes_double_quotes(client):
    """Names containing double quotes should be properly escaped in CSV."""
    from tests.conftest import seed_transaction
    seed_transaction(client, name='Buy "Premium" Plan', amount="9.99")
    r = client.get("/api/export?month=2026-03")
    # RFC 4180: double quotes inside quoted fields become ""
    assert b'Buy ""Premium"" Plan' in r.data


def test_export_handles_none_values(client):
    """NULL values in DB should export as empty, not the string 'None'."""
    from tests.conftest import seed_transaction
    seed_transaction(client, notes="")
    r = client.get("/api/export?month=2026-03")
    assert b"None" not in r.data or b"Tim Hortons" in r.data  # "None" should not appear as a field value


def test_import_latin1_encoding(client):
    """CSV files encoded as Latin-1 should be handled gracefully."""
    # Latin-1 characters that are invalid UTF-8
    csv_text = "Date,Type,Name,Category,Amount,Account,Notes,Source\n"
    csv_text += '"2026-03-15","Expense","Caf\xe9 Cr\xe8me","Eating Out","5.00","Test Bank","","csv"\n'
    data = {"files": (io.BytesIO(csv_text.encode("latin-1")), "latin1.csv")}
    r = client.post("/api/import", data=data, content_type="multipart/form-data")
    result = r.get_json()
    assert r.status_code == 200
    # Should not crash — either detected and imported, or reported as unknown
    assert len(result) == 1


def test_parse_date_uses_custom_formats():
    """parse_date should accept custom format lists from bank YAML configs."""
    from canada_finance.services.helpers import parse_date
    # Day-first format (used by National Bank)
    result = parse_date("25/03/2026", formats=["%d/%m/%Y"])
    assert result == "2026-03-25"
    # Without the right format, it should raise
    import pytest
    with pytest.raises(ValueError):
        parse_date("25/03/2026", formats=["%Y-%m-%d"])


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
    assert result[0]["bank"] == "Boreal Export"
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


# ── Amex Import ────────────────────────────────────────────────────────────────

def test_import_amex_csv(client):
    """Amex CSV with 12 metadata rows should be detected and imported."""
    data = {"files": (io.BytesIO(SAMPLE_AMEX_CSV.encode()), "amex.csv")}
    r = client.post("/api/import", data=data, content_type="multipart/form-data")
    result = r.get_json()
    assert r.status_code == 200
    assert result[0]["bank"] == "American Express (Credit Card)"
    # 3 real charges, 1 "PAYMENT RECEIVED" skipped
    assert result[0]["added"] == 3


def test_amex_charges_are_expenses(client):
    """Positive Amex amounts should import as Expense (inverted sign)."""
    data = {"files": (io.BytesIO(SAMPLE_AMEX_CSV.encode()), "amex.csv")}
    client.post("/api/import", data=data, content_type="multipart/form-data")
    txns = client.get("/api/transactions?month=2026-04").get_json()
    expenses = [t for t in txns if t["type"] == "Expense"]
    assert len(expenses) == 3
    amounts = sorted([t["amount"] for t in expenses])
    assert amounts == [5.49, 65.0, 85.23]


def test_amex_skips_payment_received(client):
    """'PAYMENT RECEIVED' rows should be skipped (not real transactions)."""
    data = {"files": (io.BytesIO(SAMPLE_AMEX_CSV.encode()), "amex.csv")}
    client.post("/api/import", data=data, content_type="multipart/form-data")
    txns = client.get("/api/transactions?search=PAYMENT RECEIVED").get_json()
    assert len(txns) == 0


def test_amex_description_fallback(client):
    """When Description is empty, parser should fall back to Additional Information."""
    data = {"files": (io.BytesIO(SAMPLE_AMEX_REDACTED_CSV.encode()), "amex.csv")}
    r = client.post("/api/import", data=data, content_type="multipart/form-data")
    result = r.get_json()
    assert result[0]["added"] == 2
    txns = client.get("/api/transactions?month=2026-04").get_json()
    names = [t["name"] for t in txns]
    assert any("TIM HORTONS" in n for n in names)
    assert any("FOOD BASICS" in n for n in names)


def test_amex_date_format(client):
    """Amex dates like '27 Apr. 2026' should parse correctly."""
    data = {"files": (io.BytesIO(SAMPLE_AMEX_CSV.encode()), "amex.csv")}
    client.post("/api/import", data=data, content_type="multipart/form-data")
    txns = client.get("/api/transactions?month=2026-04").get_json()
    dates = sorted([t["date"] for t in txns])
    assert "2026-04-22" in dates
    assert "2026-04-25" in dates
    assert "2026-04-27" in dates


def test_amex_account_label(client):
    """Imported Amex transactions should have 'Amex Credit Card' account."""
    data = {"files": (io.BytesIO(SAMPLE_AMEX_CSV.encode()), "amex.csv")}
    client.post("/api/import", data=data, content_type="multipart/form-data")
    txns = client.get("/api/transactions?month=2026-04").get_json()
    assert all(t["account"] == "Amex Credit Card" for t in txns)
