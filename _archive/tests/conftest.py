import os
import tempfile

import pytest

from canada_finance import create_app
from canada_finance.models.database import get_db


@pytest.fixture()
def app(monkeypatch):
    """Create application with a temporary database for each test."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    monkeypatch.setenv("DB_PATH", db_path)
    # Patch both the config module AND the imported name in __init__
    import canada_finance.config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    import canada_finance as cf
    monkeypatch.setattr(cf, "DB_PATH", db_path)

    app = create_app()
    app.config.update({"TESTING": True})

    yield app

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield get_db()


# ── Seed helpers ───────────────────────────────────────────────────────────────

def seed_transaction(client, **kwargs):
    """Insert a single transaction via the API and return response JSON."""
    defaults = {
        "date": "2026-03-15",
        "type": "Expense",
        "name": "Tim Hortons",
        "category": "Eating Out",
        "amount": "12.50",
        "account": "Tangerine Chequing",
        "notes": "",
    }
    defaults.update(kwargs)
    return client.post("/api/add", json=defaults).get_json()


def seed_many_transactions(client, count=60):
    """Seed `count` expense transactions across two months."""
    for i in range(count):
        month = "2026-03" if i % 2 == 0 else "2026-04"
        day = (i % 28) + 1
        seed_transaction(
            client,
            date=f"{month}-{day:02d}",
            name=f"Store #{i}",
            amount=str(10 + i),
            account="Tangerine Chequing",
        )


def make_csv(rows, headers="Date,Description,Amount"):
    """Build a simple CSV string for import tests."""
    lines = [headers] + rows
    return "\n".join(lines)


# Sample bank CSV that matches the Tangerine chequing config header
TANGERINE_HEADER = "Date,Transaction,Name,Memo,Amount"

SAMPLE_TANGERINE_CSV = (
    "Date,Transaction,Name,Memo,Amount\n"
    "3/15/2026,DEBIT,SHOPPERS DRUG MART,,12.50\n"
    "3/16/2026,CREDIT,PAYROLL DEPOSIT,,1500.00\n"
)

SAMPLE_AMEX_CSV = (
    ",Transaction Details: ,American Express® Green Card,,,,,,,\n"
    ",TEST USER,29 Mar. 2026 - 28 Apr. 2026,,,,,,,\n"
    ",Account Number: XXX-XXXXX,,,,,,,,\n"
    ",,,,,,,,,\n"
    ",,,,,,,,,\n"
    ",,,,,,,,,\n"
    "Summary,,,Total,,,,,,\n"
    "Last billed statement,,,,,,,,,\n"
    "Charges & Adjustments,,,,,,,,,\n"
    "Payments & Credits,,,,,,,,,\n"
    "Summary for this billed period:,,,,,,,,,\n"
    ",,,,,,,,,\n"
    "Date,Date Processed,Description,Amount,Foreign Spend Amount,"
    "Commission,Exchange Rate,Merchant,Merchant Address,Additional Information\n"
    "27 Apr. 2026,27 Apr. 2026,TIM HORTONS,5.49,,,,TIM HORTONS,SCARBOROUGH,"
    "TIM HORTONS #1873       SCARBOROUGH\n"
    "25 Apr. 2026,25 Apr. 2026,FOOD BASICS,85.23,,,,FOOD BASICS,SCARBOROUGH,"
    "FOOD BASICS  628        SCARBOROUGH\n"
    "23 Apr. 2026,23 Apr. 2026,PAYMENT RECEIVED - THANK YOU,-500.00,,,,,,"
    "PAYMENT RECEIVED - THANK YOU\n"
    "22 Apr. 2026,22 Apr. 2026,GAS STATION,65.00,,,,KENNEDY GAS BAR,SCARBOROUGH,"
    "KENNEDY GAS BAR KENNEDY SCARBOROUGH\n"
)

# Amex CSV with empty Description column — tests description_fallback
SAMPLE_AMEX_REDACTED_CSV = (
    ",Transaction Details: ,American Express® Green Card,,,,,,,\n"
    ",TEST USER,29 Mar. 2026 - 28 Apr. 2026,,,,,,,\n"
    ",Account Number: XXX-XXXXX,,,,,,,,\n"
    ",,,,,,,,,\n"
    ",,,,,,,,,\n"
    ",,,,,,,,,\n"
    "Summary,,,Total,,,,,,\n"
    "Last billed statement,,,,,,,,,\n"
    "Charges & Adjustments,,,,,,,,,\n"
    "Payments & Credits,,,,,,,,,\n"
    "Summary for this billed period:,,,,,,,,,\n"
    ",,,,,,,,,\n"
    "Date,Date Processed,Description,Amount,Foreign Spend Amount,"
    "Commission,Exchange Rate,Merchant,Merchant Address,Additional Information\n"
    "27 Apr. 2026,27 Apr. 2026,,5.49,,,,,,TIM HORTONS #1873       SCARBOROUGH\n"
    "25 Apr. 2026,25 Apr. 2026,,85.23,,,,,,FOOD BASICS  628        SCARBOROUGH\n"
)

XSS_CSV = (
    "Date,Transaction,Name,Memo,Amount\n"
    '3/17/2026,DEBIT,<img onerror=alert(1) src=x>,,9.99\n'
)
