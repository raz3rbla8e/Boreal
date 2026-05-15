"""Tests for bank CSV detection — ensures each bank YAML matches the right header
and that no two banks produce a false positive on each other's headers."""
from canada_finance.services.csv_parser import load_bank_configs, detect_bank_config

# Simulated CSV headers (first line) for each Canadian bank
BANK_HEADERS = {
    "amex": ",Transaction Details: ,American Express® Green Card,,,,,,,",
    "bmo": "Date,Description,Withdrawals,Deposits,Balance",
    "cibc": "Transaction Date,Description,Withdrawals,Deposits,Balance",
    "national_bank": "Date de transaction,Description,Débit,Crédit,Solde",
    "rbc": "Date,Transaction,Description,Debit,Credit,Balance",
    "scotiabank": "Date,Description,Amount,Balance",
    "tangerine_credit": "Transaction date,Transaction,Name,Memo,Amount",
    "tangerine_debit": "Date,Transaction,Name,Memo,Amount",
    "td": "Date,Description,Withdrawals ($),Deposits ($),Total Balance",
    "wealthsimple": "transaction_date,description,net_cash_amount,account_type",
    "canada_finance_export": "Date,Type,Name,Category,Amount,Account,Notes,Source",
}

EXPECTED_NAMES = {
    "amex": "American Express (Credit Card)",
    "bmo": "BMO (Chequing)",
    "cibc": "CIBC (Chequing)",
    "national_bank": "National Bank",
    "rbc": "RBC (Chequing)",
    "scotiabank": "Scotiabank",
    "tangerine_credit": "Tangerine (Credit Card)",
    "tangerine_debit": "Tangerine (Chequing)",
    "td": "TD Canada Trust (Chequing)",
    "wealthsimple": "Wealthsimple",
    "canada_finance_export": "Boreal Export",
}


def _configs():
    return load_bank_configs()


# ── Each bank header matches the correct config ───────────────────────────────

def test_detect_amex():
    cfg, _ = detect_bank_config(BANK_HEADERS["amex"], _configs())
    assert cfg is not None, "Amex header not detected"
    assert cfg["name"] == EXPECTED_NAMES["amex"]


def test_detect_bmo():
    cfg, _ = detect_bank_config(BANK_HEADERS["bmo"], _configs())
    assert cfg is not None, "BMO header not detected"
    assert cfg["name"] == EXPECTED_NAMES["bmo"]


def test_detect_cibc():
    cfg, _ = detect_bank_config(BANK_HEADERS["cibc"], _configs())
    assert cfg is not None, "CIBC header not detected"
    assert cfg["name"] == EXPECTED_NAMES["cibc"]


def test_detect_national_bank():
    cfg, _ = detect_bank_config(BANK_HEADERS["national_bank"], _configs())
    assert cfg is not None, "National Bank header not detected"
    assert cfg["name"] == EXPECTED_NAMES["national_bank"]


def test_detect_rbc():
    cfg, _ = detect_bank_config(BANK_HEADERS["rbc"], _configs())
    assert cfg is not None, "RBC header not detected"
    assert cfg["name"] == EXPECTED_NAMES["rbc"]


def test_detect_scotiabank():
    cfg, _ = detect_bank_config(BANK_HEADERS["scotiabank"], _configs())
    assert cfg is not None, "Scotiabank header not detected"
    assert cfg["name"] == EXPECTED_NAMES["scotiabank"]


def test_detect_tangerine_credit():
    cfg, _ = detect_bank_config(BANK_HEADERS["tangerine_credit"], _configs())
    assert cfg is not None, "Tangerine Credit header not detected"
    assert cfg["name"] == EXPECTED_NAMES["tangerine_credit"]


def test_detect_tangerine_debit():
    cfg, _ = detect_bank_config(BANK_HEADERS["tangerine_debit"], _configs())
    assert cfg is not None, "Tangerine Debit header not detected"
    assert cfg["name"] == EXPECTED_NAMES["tangerine_debit"]


def test_detect_td():
    cfg, _ = detect_bank_config(BANK_HEADERS["td"], _configs())
    assert cfg is not None, "TD header not detected"
    assert cfg["name"] == EXPECTED_NAMES["td"]


def test_detect_wealthsimple():
    cfg, _ = detect_bank_config(BANK_HEADERS["wealthsimple"], _configs())
    assert cfg is not None, "Wealthsimple header not detected"
    assert cfg["name"] == EXPECTED_NAMES["wealthsimple"]


def test_detect_canada_finance_export():
    cfg, _ = detect_bank_config(BANK_HEADERS["canada_finance_export"], _configs())
    assert cfg is not None, "Boreal Export header not detected"
    assert cfg["name"] == EXPECTED_NAMES["canada_finance_export"]


# ── No cross-contamination — each header matches ONLY its own bank ────────────

def test_no_cross_detection():
    """Every bank header must match exactly one config, and it must be the right one."""
    configs = _configs()
    errors = []
    for bank_key, header in BANK_HEADERS.items():
        cfg, config_name = detect_bank_config(header, configs)
        expected = EXPECTED_NAMES[bank_key]
        if cfg is None:
            errors.append(f"{bank_key}: not detected at all")
        elif cfg["name"] != expected:
            errors.append(f"{bank_key}: detected as '{cfg['name']}' (expected '{expected}')")
    assert not errors, "Cross-detection errors:\n" + "\n".join(errors)


def test_unknown_csv_returns_none():
    """A random CSV header should not match any bank."""
    cfg, name = detect_bank_config("Col1,Col2,Col3,Col4", _configs())
    assert cfg is None
    assert name == "unknown"
