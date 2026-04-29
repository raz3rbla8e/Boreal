import csv
import io
import os
import re

import yaml

from canada_finance.config import BANKS_DIR
from canada_finance.services.helpers import parse_date, safe_abs_float
from canada_finance.services.categorization import categorize


def load_bank_configs() -> list:
    """Load all YAML bank configs from the banks/ directory."""
    configs = []
    if not os.path.isdir(BANKS_DIR):
        return configs
    for fname in sorted(os.listdir(BANKS_DIR)):
        if fname.endswith((".yaml", ".yml")):
            fpath = os.path.join(BANKS_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                if cfg:
                    cfg["_filename"] = fname
                    configs.append(cfg)
    return configs


def detect_bank_config(header: str, configs: list = None):
    """Try every YAML config against the CSV header. Returns (config, config_name) or (None, 'unknown')."""
    if configs is None:
        configs = load_bank_configs()
    h = header.strip().lower()
    for cfg in configs:
        det = cfg.get("detection", {})
        # header_starts_with check
        starts = det.get("header_starts_with", "")
        if starts and not h.startswith(starts.lower()):
            continue
        # header_contains — ALL must be present
        contains = det.get("header_contains", [])
        if contains and not all(kw.lower() in h for kw in contains):
            # If header_contains fails, check header_contains_any as alternative
            contains_any = det.get("header_contains_any", [])
            if not contains_any or not any(kw.lower() in h for kw in contains_any):
                continue
        elif not contains:
            # No header_contains, check header_contains_any alone
            contains_any = det.get("header_contains_any", [])
            if contains_any and not any(kw.lower() in h for kw in contains_any):
                continue
        # header_excludes — NONE should be present
        excludes = det.get("header_excludes", [])
        if excludes and any(kw.lower() in h for kw in excludes):
            continue
        config_name = cfg["_filename"].rsplit(".", 1)[0]
        return cfg, config_name
    return None, "unknown"


def _find_column(row_keys, col_name, alt_name=None, flexible=False):
    """Find the actual column key in a CSV row, supporting exact match, case-insensitive, and flexible matching."""
    if col_name in row_keys:
        return col_name
    # Case-insensitive exact
    for k in row_keys:
        if k.lower().strip() == col_name.lower().strip():
            return k
    # Flexible: substring match
    if flexible:
        for k in row_keys:
            if col_name.lower() in k.lower():
                return k
    # Try alternate name
    if alt_name:
        return _find_column(row_keys, alt_name, flexible=flexible)
    return None


def parse_with_config(text: str, config: dict, learned: dict) -> list:
    """Generic parser that reads any CSV using a YAML bank config."""
    cols = config.get("columns", {})
    date_fmts = config.get("date_formats", ["%Y-%m-%d", "%m/%d/%Y"])
    account_label = config.get("account_label", "Unknown")
    skip_rules = config.get("skip_rows_where", {})
    skip_desc = [s.lower() for s in skip_rules.get("description_contains", [])]
    flexible = config.get("flexible_columns", False)
    amount_sign = config.get("amount_sign", "standard")
    credit_default = config.get("credit_default_category", "Other Income")
    desc_fallback = config.get("description_fallback", [])
    memo_col_name = cols.get("memo")

    # Resolve account label template (e.g. "Wealthsimple {account_type}")
    account_template = "{" in account_label

    txns = []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return txns

    row_keys = list(reader.fieldnames)

    # Resolve column names once from first row's keys
    date_key = _find_column(row_keys, cols.get("date", "Date"),
                            config.get("date_alt"), flexible)
    desc_key = _find_column(row_keys, cols.get("description", "Description"),
                            config.get("description_alt"), flexible)

    has_amount = "amount" in cols
    has_debit_credit = "debit" in cols and "credit" in cols

    if has_amount:
        amt_key = _find_column(row_keys, cols["amount"],
                               config.get("amount_alt"), flexible)
    elif has_debit_credit:
        debit_key = _find_column(row_keys, cols["debit"],
                                 config.get("debit_alt"), flexible)
        credit_key = _find_column(row_keys, cols["credit"],
                                  config.get("credit_alt"), flexible)
    else:
        return txns

    memo_key = _find_column(row_keys, memo_col_name, flexible=flexible) if memo_col_name else None
    acct_type_key = _find_column(row_keys, cols.get("account_type", ""), flexible=flexible) if "account_type" in cols else None

    # Support re-import of exported CSVs with preserved type/category
    preserve_type = config.get("preserve_type", False)
    preserve_cat = config.get("preserve_category", False)
    type_key = _find_column(row_keys, cols.get("type", ""), flexible=flexible) if "type" in cols else None
    cat_key = _find_column(row_keys, cols.get("category", ""), flexible=flexible) if "category" in cols else None

    for row in reader:
        try:
            # Get description
            desc = row.get(desc_key, "").strip() if desc_key else ""
            if not desc and desc_fallback:
                for fb in desc_fallback:
                    fb_key = _find_column(row_keys, fb, flexible=flexible)
                    if fb_key and row.get(fb_key, "").strip():
                        desc = row[fb_key].strip()
                        break
                if not desc:
                    desc = "Transaction"
            # Append memo if present
            if memo_key and row.get(memo_key, "").strip():
                memo = row[memo_key].strip()
                desc = f"{desc} — {memo}"

            # Skip rows
            if skip_desc and any(s in desc.lower() for s in skip_desc):
                continue

            # Parse date
            raw_date = row.get(date_key, "").strip() if date_key else ""
            if not raw_date:
                continue
            dt = parse_date(raw_date, date_fmts)

            # Resolve account label
            if account_template and acct_type_key:
                acct = account_label.replace(
                    "{account_type}", row.get(acct_type_key, "Chequing").strip())
            else:
                acct = account_label

            # Determine amount and type
            if has_amount:
                raw_amt = row.get(amt_key, "").strip() if amt_key else ""
                if not raw_amt:
                    continue
                # Normalize Unicode minus signs (\u2212, \u2013, \u2014) to ASCII
                cleaned_amt = raw_amt.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
                amt_val = float(re.sub(r"[,$\s]", "", cleaned_amt))
                if amt_val == 0:
                    continue

                # If re-importing our own export, use the Type/Category columns directly
                if preserve_type and type_key and row.get(type_key, "").strip():
                    tx_type = row[type_key].strip()
                    cat_override = row.get(cat_key, "").strip() if preserve_cat and cat_key else None
                    txn = _make_txn(dt, tx_type, desc, abs(amt_val),
                                    acct, learned, "UNCATEGORIZED")
                    if cat_override:
                        txn["category"] = cat_override
                    txns.append(txn)
                elif amount_sign == "standard":
                    if amt_val < 0:
                        txns.append(_make_txn(dt, "Expense", desc, abs(amt_val),
                                              acct, learned, "UNCATEGORIZED"))
                    else:
                        txns.append(_make_txn(dt, "Income", desc, amt_val,
                                              acct, learned, credit_default))
                else:  # inverted
                    if amt_val > 0:
                        txns.append(_make_txn(dt, "Expense", desc, amt_val,
                                              acct, learned, "UNCATEGORIZED"))
                    else:
                        txns.append(_make_txn(dt, "Income", desc, abs(amt_val),
                                              acct, learned, credit_default))
            elif has_debit_credit:
                d_raw = row.get(debit_key, "").strip() if debit_key else ""
                c_raw = row.get(credit_key, "").strip() if credit_key else ""
                d = safe_abs_float(d_raw) if d_raw else 0
                c = safe_abs_float(c_raw) if c_raw else 0
                if d > 0:
                    txns.append(_make_txn(dt, "Expense", desc, d,
                                          acct, learned, "UNCATEGORIZED"))
                elif c > 0:
                    txns.append(_make_txn(dt, "Income", desc, c,
                                          acct, learned, credit_default))
        except Exception:
            continue
    return txns


def _make_txn(dt, tx_type, desc, amount, account, learned, default_income_cat):
    """Build a transaction dict with proper categorization."""
    cat = categorize(desc, learned)
    if tx_type == "Income" and cat == "UNCATEGORIZED":
        cat = default_income_cat
    return {"date": dt, "type": tx_type, "name": desc, "category": cat,
            "amount": amount, "account": account, "notes": "", "source": "csv"}


def parse_csv_text(text: str, learned: dict = None) -> tuple:
    """Detect bank from CSV header using YAML configs, then parse."""
    if learned is None:
        learned = {}
    first_line = text.splitlines()[0] if text.strip() else ""
    configs = load_bank_configs()
    config, bank_name = detect_bank_config(first_line, configs)
    if config:
        txns = parse_with_config(text, config, learned)
        return txns, config.get("name", bank_name)
    return [], "unknown"
