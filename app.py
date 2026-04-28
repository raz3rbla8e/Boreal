#!/usr/bin/env python3
"""
CanadaFinance — Personal Finance Dashboard for Canadians
Run with: python app.py
Then open: http://localhost:5000

Supported banks (CSV import):
  - Tangerine (Chequing + Credit Card)
  - Wealthsimple (Chequing)
  - TD (EasyWeb Chequing CSV)
  - RBC (Online Banking CSV)
  - CIBC (Online Banking CSV)
  - Scotiabank (Online Banking CSV)
  - BMO (Online Banking CSV)
  - National Bank (CSV)
"""

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from flask import Flask, g, jsonify, render_template_string, request, Response

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "finance.db")

# ── DATABASE ──────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('Income','Expense')),
                name        TEXT NOT NULL,
                category    TEXT NOT NULL,
                amount      REAL NOT NULL CHECK(amount > 0),
                account     TEXT NOT NULL,
                notes       TEXT DEFAULT '',
                source      TEXT DEFAULT 'manual',
                tx_hash     TEXT UNIQUE
            );
            CREATE INDEX IF NOT EXISTS idx_date ON transactions(date);
            CREATE INDEX IF NOT EXISTS idx_type ON transactions(type);
            CREATE INDEX IF NOT EXISTS idx_category ON transactions(category);

            CREATE TABLE IF NOT EXISTS learned_merchants (
                keyword     TEXT PRIMARY KEY,
                category    TEXT NOT NULL,
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS budgets (
                category    TEXT PRIMARY KEY,
                monthly_limit REAL NOT NULL CHECK(monthly_limit > 0)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS categories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                type        TEXT NOT NULL CHECK(type IN ('Income','Expense')),
                icon        TEXT DEFAULT '',
                user_created INTEGER DEFAULT 0,
                sort_order  INTEGER DEFAULT 0
            );
        """)
        # Default settings
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('theme','dark')")
        # Seed default categories (only if table is empty)
        existing = db.execute("SELECT COUNT(*) as c FROM categories").fetchone()[0]
        if existing == 0:
            expense_cats = [
                ("Eating Out", "🍔"), ("Groceries", "🛒"), ("Fuel", "⛽"),
                ("Transport", "🚌"), ("Entertainment", "🎬"), ("Subscriptions", "📱"),
                ("Healthcare", "🏥"), ("Pharmacy", "💊"), ("Clothing", "👕"),
                ("Shopping", "🛍️"), ("Home", "🏠"), ("Insurance", "🛡️"),
                ("Travel", "✈️"), ("Education", "📚"), ("Phone", "📞"),
                ("Internet", "🌐"), ("Utilities", "💡"), ("Car Payment", "🚗"),
                ("Rent", "🏘️"), ("Savings Transfer", "💰"), ("Misc", "📦"),
            ]
            income_cats = [
                ("Job", "💼"), ("Freelance", "💻"), ("Bonus", "🎉"),
                ("Refund", "↩️"), ("Other Income", "💵"),
            ]
            for i, (name, icon) in enumerate(expense_cats):
                db.execute("INSERT INTO categories (name, type, icon, user_created, sort_order) VALUES (?,?,?,0,?)",
                           (name, "Expense", icon, i))
            for i, (name, icon) in enumerate(income_cats):
                db.execute("INSERT INTO categories (name, type, icon, user_created, sort_order) VALUES (?,?,?,0,?)",
                           (name, "Income", icon, i))
        db.commit()

def tx_hash(date_str, name, amount, account):
    key = f"{date_str}|{name}|{amount:.2f}|{account}"
    return hashlib.md5(key.encode()).hexdigest()

def get_setting(key, default=""):
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

# ── AUTO-CATEGORIZATION RULES ────────────────────────────────────────────────
# Keyword → category mapping used at import time.  The list of valid categories
# is stored in the DB 'categories' table (seeded on first run, editable in Settings).
# These rules just tell the auto-categorizer which keywords map to which category.

CATEGORY_RULES = {
    "Subscriptions": [
        "claude.ai","anthropic","netflix","spotify","apple.com/bill","google one",
        "microsoft 365","adobe","notion","chatgpt","openai","dropbox","icloud",
        "youtube premium","duolingo","amazon prime","prime video",
    ],
    "Fuel": [
        "shell","esso","petro-canada","petro canada","ultramar","pioneer","irving",
        "suncor","husky","pronto","gas station","circle k","couche tard",
        "shefield","sheffield","7-eleven fuel","costco gas",
    ],
    "Groceries": [
        "loblaws","no frills","sobeys","metro","food basics","freshco","farm boy",
        "whole foods","costco wholesale","superstore","real canadian","t&t","maxi",
        "provigo","iga","safeway","save on food","independent","freshmart",
        "grocery","supermarche","epicerie","wmt suprctr","wal-mart","walmart",
    ],
    "Pharmacy": [
        "shoppers drug","rexall","pharmasave","jean coutu","uniprix","proxim",
        "guardian","london drugs","pharmacy","drug mart","supplement","vitamin",
    ],
    "Healthcare": [
        "physio","dentist","dental","doctor","clinic","optometrist","medical",
        "hospital","lab","diagnosis","diagnostics","planet fitness","goodlife",
        "anytime fitness","gym","yoga","pilates","abc*planet","massage","therapy",
    ],
    "Phone": [
        "fido","koodo","public mobile","lucky mobile","virgin mobile",
        "bell mobility","telus mobile","rogers mobile","freedom mobile","chatr",
    ],
    "Internet": [
        "bell internet","rogers internet","videotron","shaw","eastlink","cogeco",
        "teksavvy","distributel",
    ],
    "Utilities": [
        "hydro ottawa","hydro one","bc hydro","enbridge","union gas",
        "atco gas","fortis","electric","water bill","toronto hydro",
    ],
    "Clothing": [
        "winners","marshalls","sport chek","atmosphere","nike","adidas",
        "h&m","zara","uniqlo","old navy","gap","aritzia","lululemon",
        "simons","the bay","hudson's bay","nordstrom","reitmans","ssense","roots",
    ],
    "Home": [
        "ikea","canadian tire","home depot","rona","home hardware",
        "wayfair","structube","article","restoration hardware","pottery barn",
    ],
    "Insurance": [
        "insurance","intact","aviva","state farm","belairdirect","wawanesa",
        "td insurance","rbc insurance","allstate","cooperators","desjardins insur",
    ],
    "Travel": [
        "airbnb","hotel","expedia","booking.com","air canada","westjet","porter",
        "swoop","flair","vrbo","marriott","hilton","delta hotel","best western",
        "kayak","hostel","motel","resort","via rail",
    ],
    "Education": [
        "carleton","university","college","textbook","udemy","coursera",
        "linkedin learn","skillshare","pluralsight","tuition","osap","bookstore",
        "mcgill","uoft","ubc","western university","queens university",
    ],
    "Entertainment": [
        "steam","epic games","xbox","playstation","nintendo","cineplex","landmark",
        "google play","disney+","twitch","riot games","crave","tidal","deezer",
        "gaming","movie","theatre","concert","ticketmaster","eventbrite",
        "billetterie","lcbo","rao #","liquor store","beer store","saq",
        "lotto","lottery",
    ],
    "Transport": [
        "uber","lyft","oc transpo","ttc","stm","translink","presto","parking",
        "taxi","transit","impark","indigo park","greyhound","flixbus","train",
        "enterprise rent","budget rent","hertz","avis","zipcar",
    ],
    "Eating Out": [
        "mcdonald","tim horton","subway","starbucks","uber eat","skip the dishes",
        "doordash","pizza","burger","wendy","kfc","taco bell","harvey's","a&w",
        "mary brown","popeye","chipotle","freshii","pita pit","swiss chalet",
        "boston pizza","jack astor","milestones","cactus club","earls","montana",
        "st-hubert","five guys","nandos","pho","sushi","thai","domino",
        "papa john","little caesar","pizza pizza","pizza hut","hero burger",
        "mucho burrito","shawarma","falafel","osmow","6ixty wing","happy lamb",
        "burrito","chick-fil","dairy queen","d spot","vietnamese","restaurant",
        "cafe","coffee","bakery","diner","bar","pub","grill","kitchen","bistro",
        "eatery","food court","hot pot","wing","ramen","poke","bubble tea",
        "moxie","denny","ihop","east side mario","the keg","joey","menchie",
    ],
    "Shopping": [
        "amazon","target","ebay","etsy","aliexpress","shein","best buy",
        "staples","the source","indigo","chapters","paypal","shopify",
        "dollarama","dollar tree","giant tiger","tanger outlet","rfbt",
        "homesense","apple store","samsung","microsoft store","dell",
    ],
    "Misc": [
        "detail my ride","car wash","car detail","auto detail","dry clean",
        "laundromat","post office","fedex","ups","purolator","canada post",
    ],
}

def categorize(name: str, learned: dict = None) -> str:
    n = name.lower().strip()
    # Hard overrides first
    if "costco gas" in n:
        return "Fuel"
    # User-learned merchants (highest priority)
    if learned:
        for keyword, cat in learned.items():
            if keyword in n:
                return cat
    # Rule-based (check specific categories before generic ones)
    priority_order = [
        "Subscriptions", "Fuel", "Groceries", "Pharmacy", "Healthcare",
        "Phone", "Internet", "Utilities", "Clothing", "Home", "Insurance",
        "Travel", "Education", "Entertainment", "Transport", "Eating Out",
        "Shopping", "Misc",
    ]
    for cat in priority_order:
        for kw in CATEGORY_RULES.get(cat, []):
            if kw in n:
                return cat
    return "UNCATEGORIZED"

def load_learned_dict(db) -> dict:
    rows = db.execute("SELECT keyword, category FROM learned_merchants").fetchall()
    return {r["keyword"]: r["category"] for r in rows}

# ── DATE PARSING ──────────────────────────────────────────────────────────────

def parse_date(raw: str) -> str:
    raw = raw.strip().replace("/", "-")
    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%d-%m-%Y", "%b %d %Y",
                "%B %d %Y", "%d %b %Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")

def safe_float(raw: str) -> float:
    cleaned = re.sub(r"[,$\s]", "", raw.strip())
    cleaned = cleaned.lstrip("-")  # remove sign, we handle direction separately
    return float(cleaned) if cleaned else 0.0

# ── YAML BANK CONFIG ENGINE ───────────────────────────────────────────────────

import yaml

BANKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banks")

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
            dt = parse_date(raw_date)

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
                amt_val = float(re.sub(r"[,$\s]", "", raw_amt))
                if amt_val == 0:
                    continue
                if amount_sign == "standard":
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
                d = safe_float(d_raw) if d_raw else 0
                c = safe_float(c_raw) if c_raw else 0
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

def save_transactions(txns: list) -> tuple:
    added = dupes = 0
    with sqlite3.connect(DB_PATH) as db:
        for t in txns:
            h = tx_hash(t["date"], t["name"], t["amount"], t["account"])
            try:
                db.execute("""INSERT INTO transactions
                    (date,type,name,category,amount,account,notes,source,tx_hash)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (t["date"], t["type"], t["name"], t["category"],
                     t["amount"], t["account"], t.get("notes",""), t.get("source","csv"), h))
                added += 1
            except sqlite3.IntegrityError:
                dupes += 1
        db.commit()
    return added, dupes

# ── API ROUTES ────────────────────────────────────────────────────────────────

@app.route("/api/months")
def api_months():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT substr(date,1,7) as m FROM transactions ORDER BY m DESC"
    ).fetchall()
    return jsonify([r["m"] for r in rows])

@app.route("/api/summary")
def api_summary():
    month = request.args.get("month", "")
    db = get_db()
    like = f"{month}%"
    income = db.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Income' AND date LIKE ?", (like,)
    ).fetchone()["t"]
    expenses = db.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND date LIKE ?", (like,)
    ).fetchone()["t"]
    by_cat = db.execute(
        """SELECT category, SUM(amount) as total FROM transactions
           WHERE type='Expense' AND date LIKE ? GROUP BY category ORDER BY total DESC""", (like,)
    ).fetchall()
    income_by_cat = db.execute(
        """SELECT category, SUM(amount) as total FROM transactions
           WHERE type='Income' AND date LIKE ? GROUP BY category ORDER BY total DESC""", (like,)
    ).fetchall()
    # Previous month for comparison
    if month:
        y, m = int(month[:4]), int(month[5:7])
        pm = date(y, m, 1) - timedelta(days=1)
        prev_like = f"{pm.year}-{pm.month:02d}%"
        prev_exp = db.execute(
            "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND date LIKE ?", (prev_like,)
        ).fetchone()["t"]
        prev_by_cat = db.execute(
            """SELECT category, SUM(amount) as total FROM transactions
               WHERE type='Expense' AND date LIKE ? GROUP BY category""", (prev_like,)
        ).fetchall()
        prev_cat_map = {r["category"]: r["total"] for r in prev_by_cat}
    else:
        prev_exp = 0
        prev_cat_map = {}
    # Budgets
    budgets = {r["category"]: r["monthly_limit"] for r in
               db.execute("SELECT category, monthly_limit FROM budgets").fetchall()}
    by_cat_out = []
    for r in by_cat:
        cat = r["category"]
        by_cat_out.append({
            "category": cat, "total": r["total"],
            "prev_total": prev_cat_map.get(cat, 0),
            "budget": budgets.get(cat),
        })
    return jsonify({
        "income": income, "expenses": expenses, "net": income - expenses,
        "prev_expenses": prev_exp,
        "savings_rate": round((income - expenses) / income * 100, 1) if income > 0 else 0,
        "by_category": by_cat_out,
        "income_by_category": [{"category": r["category"], "total": r["total"]} for r in income_by_cat],
    })

@app.route("/api/transactions")
def api_transactions():
    month  = request.args.get("month", "")
    cat    = request.args.get("category", "")
    typ    = request.args.get("type", "")
    search = request.args.get("search", "").strip()
    db     = get_db()
    if search:
        term = f"%{search}%"
        q = """SELECT * FROM transactions WHERE
               (name LIKE ? OR category LIKE ? OR account LIKE ? OR notes LIKE ? OR date LIKE ?)"""
        params = [term]*5
        if typ: q += " AND type=?"; params.append(typ)
        q += " ORDER BY date DESC, id DESC"
    else:
        q = "SELECT * FROM transactions WHERE date LIKE ?"
        params = [f"{month}%"]
        if cat: q += " AND category=?"; params.append(cat)
        if typ: q += " AND type=?"; params.append(typ)
        q += " ORDER BY date DESC, id DESC"
    rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/add", methods=["POST"])
def api_add():
    d = request.json
    for f in ["date","type","name","category","amount","account"]:
        if not d.get(f): return jsonify({"error": f"Missing: {f}"}), 400
    try:
        amount = float(d["amount"])
        h = tx_hash(d["date"], d["name"], amount, d["account"])
        get_db().execute("""INSERT INTO transactions
            (date,type,name,category,amount,account,notes,source,tx_hash)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (d["date"], d["type"], d["name"], d["category"],
             amount, d["account"], d.get("notes",""), "manual", h))
        get_db().commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Duplicate transaction"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/update/<int:tid>", methods=["PATCH"])
def api_update(tid):
    d = request.json
    allowed = ["date","type","name","category","amount","account","notes"]
    sets = ", ".join(f"{k}=?" for k in d if k in allowed)
    vals = [d[k] for k in d if k in allowed] + [tid]
    if not sets: return jsonify({"error": "Nothing to update"}), 400
    db = get_db()
    db.row_factory = sqlite3.Row
    original = db.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    db.execute(f"UPDATE transactions SET {sets} WHERE id=?", vals)
    retro_fixed = 0
    if "category" in d and original:
        new_cat = d["category"]
        orig_name = original["name"].lower().strip()
        db.execute("""INSERT INTO learned_merchants (keyword, category) VALUES (?,?)
            ON CONFLICT(keyword) DO UPDATE SET category=excluded.category, updated_at=datetime('now')
        """, (orig_name, new_cat))
        all_learned = db.execute("SELECT keyword, category FROM learned_merchants").fetchall()
        for row in db.execute("SELECT id, name FROM transactions WHERE category='UNCATEGORIZED'").fetchall():
            rn = row["name"].lower()
            for lrow in all_learned:
                words = [w for w in lrow["keyword"].split() if len(w) > 3]
                if any(w in rn for w in words):
                    db.execute("UPDATE transactions SET category=? WHERE id=?", (lrow["category"], row["id"]))
                    retro_fixed += 1
                    break
    db.commit()
    return jsonify({"ok": True, "retro_fixed": retro_fixed})

@app.route("/api/delete/<int:tid>", methods=["DELETE"])
def api_delete(tid):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id=?", (tid,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/import", methods=["POST"])
def api_import():
    db = get_db()
    learned = load_learned_dict(db)
    configs = load_bank_configs()
    results = []
    for f in request.files.getlist("files"):
        text = f.read().decode("utf-8-sig")
        first_line = text.splitlines()[0] if text.strip() else ""
        config, bank_name = detect_bank_config(first_line, configs)
        if config:
            txns = parse_with_config(text, config, learned)
            added, dupes = save_transactions(txns)
            results.append({
                "file": f.filename, "bank": config.get("name", bank_name),
                "added": added, "dupes": dupes,
                "last_verified": config.get("last_verified", ""),
            })
        else:
            results.append({
                "file": f.filename, "bank": "unknown", "added": 0, "dupes": 0,
                "last_verified": "",
            })
    return jsonify(results)

@app.route("/api/detect-csv", methods=["POST"])
def api_detect_csv():
    """Detect bank from CSV; if unknown, return headers + preview rows."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file provided"}), 400
    text = f.read().decode("utf-8-sig")
    lines = text.splitlines()
    if not lines:
        return jsonify({"error": "Empty file"}), 400
    configs = load_bank_configs()
    config, bank_name = detect_bank_config(lines[0], configs)
    if config:
        return jsonify({"detected": True, "bank": config.get("name", bank_name),
                        "config_name": bank_name})
    # Unknown — return headers + preview rows
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    preview = []
    for i, row in enumerate(reader):
        if i >= 5:
            break
        preview.append(dict(row))
    return jsonify({"detected": False, "headers": headers, "preview": preview,
                    "raw_text": text})

@app.route("/api/save-bank-config", methods=["POST"])
def api_save_bank_config():
    """Save a user-defined bank config from the unknown CSV wizard."""
    d = request.json
    bank_name = d.get("bank_name", "").strip()
    if not bank_name:
        return jsonify({"error": "Bank name is required"}), 400
    date_col = d.get("date_column", "")
    desc_col = d.get("description_column", "")
    amount_mode = d.get("amount_mode", "single")  # "single" or "split"
    date_format = d.get("date_format", "%Y-%m-%d")
    if not date_col or not desc_col:
        return jsonify({"error": "Date and description columns are required"}), 400
    # Build config
    slug = re.sub(r"[^a-z0-9]+", "_", bank_name.lower()).strip("_")
    config = {
        "name": bank_name,
        "version": 1,
        "last_verified": datetime.now().strftime("%Y-%m"),
        "account_label": bank_name,
        "encoding": "utf-8-sig",
        "detection": {"header_contains": d.get("detection_headers", [])},
        "columns": {"date": date_col, "description": desc_col},
        "date_formats": [date_format],
    }
    if amount_mode == "single":
        config["columns"]["amount"] = d.get("amount_column", "")
        config["amount_sign"] = d.get("amount_sign", "standard")
    else:
        config["columns"]["debit"] = d.get("debit_column", "")
        config["columns"]["credit"] = d.get("credit_column", "")
    # Save YAML
    fname = f"{slug}.yaml"
    fpath = os.path.join(BANKS_DIR, fname)
    os.makedirs(BANKS_DIR, exist_ok=True)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(f"# {bank_name} (user-created)\n")
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return jsonify({"ok": True, "config_file": fname, "config_name": slug})

@app.route("/api/preview-parse", methods=["POST"])
def api_preview_parse():
    """Preview parsing with a user-defined config (before saving)."""
    d = request.json
    text = d.get("raw_text", "")
    mapping = d.get("mapping", {})
    if not text or not mapping:
        return jsonify({"error": "Missing data"}), 400
    # Build a temporary config from the mapping
    config = {
        "columns": {
            "date": mapping.get("date_column", ""),
            "description": mapping.get("description_column", ""),
        },
        "date_formats": [mapping.get("date_format", "%Y-%m-%d")],
        "account_label": mapping.get("bank_name", "Unknown Bank"),
    }
    if mapping.get("amount_mode") == "single":
        config["columns"]["amount"] = mapping.get("amount_column", "")
        config["amount_sign"] = mapping.get("amount_sign", "standard")
    else:
        config["columns"]["debit"] = mapping.get("debit_column", "")
        config["columns"]["credit"] = mapping.get("credit_column", "")
    txns = parse_with_config(text, config, {})
    return jsonify({"transactions": txns[:10], "total": len(txns)})

@app.route("/api/export")
def api_export():
    month = request.args.get("month", "")
    db = get_db()
    q = "SELECT date,type,name,category,amount,account,notes,source FROM transactions"
    params = []
    if month:
        q += " WHERE date LIKE ?"; params.append(f"{month}%")
    q += " ORDER BY date DESC"
    rows = db.execute(q, params).fetchall()
    def generate():
        yield "Date,Type,Name,Category,Amount,Account,Notes,Source\n"
        for r in rows:
            yield ",".join(f'"{str(v)}"' for v in r) + "\n"
    filename = f"transactions_{month or 'all'}.csv"
    return Response(generate(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.route("/api/year/<int:year>")
def api_year(year):
    db = get_db()
    months_data = []
    for m in range(1, 13):
        like = f"{year}-{m:02d}%"
        inc = db.execute("SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Income' AND date LIKE ?", (like,)).fetchone()["t"]
        exp = db.execute("SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND date LIKE ?", (like,)).fetchone()["t"]
        months_data.append({"month": f"{year}-{m:02d}", "income": inc, "expenses": exp, "net": inc-exp})
    top_cats = db.execute("""
        SELECT category, SUM(amount) as total FROM transactions
        WHERE type='Expense' AND date LIKE ? GROUP BY category ORDER BY total DESC LIMIT 5
    """, (f"{year}%",)).fetchall()
    return jsonify({
        "months": months_data,
        "top_categories": [{"category": r["category"], "total": r["total"]} for r in top_cats],
        "total_income": sum(m["income"] for m in months_data),
        "total_expenses": sum(m["expenses"] for m in months_data),
    })

@app.route("/api/budgets", methods=["GET"])
def api_budgets_get():
    db = get_db()
    rows = db.execute("SELECT category, monthly_limit FROM budgets").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/budgets", methods=["POST"])
def api_budgets_set():
    d = request.json
    db = get_db()
    db.execute("""INSERT INTO budgets (category, monthly_limit) VALUES (?,?)
        ON CONFLICT(category) DO UPDATE SET monthly_limit=excluded.monthly_limit
    """, (d["category"], float(d["amount"])))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/budgets/<string:cat>", methods=["DELETE"])
def api_budgets_del(cat):
    db = get_db()
    db.execute("DELETE FROM budgets WHERE category=?", (cat,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/learned")
def api_learned():
    db = get_db()
    rows = db.execute("SELECT keyword, category, updated_at FROM learned_merchants ORDER BY updated_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/learned/<path:keyword>", methods=["DELETE"])
def api_learned_del(keyword):
    db = get_db()
    db.execute("DELETE FROM learned_merchants WHERE keyword=?", (keyword,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return jsonify({r["key"]: r["value"] for r in rows})

@app.route("/api/settings", methods=["POST"])
def api_settings_set():
    d = request.json
    db = get_db()
    for key, val in d.items():
        db.execute("INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, val))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/categories")
def api_categories_get():
    db = get_db()
    rows = db.execute("SELECT id, name, type, icon, user_created, sort_order FROM categories ORDER BY type, sort_order").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/categories", methods=["POST"])
def api_categories_add():
    d = request.json
    name = d.get("name", "").strip()
    cat_type = d.get("type", "Expense")
    icon = d.get("icon", "").strip()
    if not name:
        return jsonify({"error": "Category name is required"}), 400
    if cat_type not in ("Income", "Expense"):
        return jsonify({"error": "Type must be Income or Expense"}), 400
    db = get_db()
    # Get next sort order
    max_order = db.execute("SELECT COALESCE(MAX(sort_order),0) FROM categories WHERE type=?", (cat_type,)).fetchone()[0]
    try:
        db.execute("INSERT INTO categories (name, type, icon, user_created, sort_order) VALUES (?,?,?,1,?)",
                   (name, cat_type, icon, max_order + 1))
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Category already exists"}), 409

@app.route("/api/categories/<int:cat_id>", methods=["PATCH"])
def api_categories_update(cat_id):
    d = request.json
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    if not cat:
        return jsonify({"error": "Category not found"}), 404
    old_name = cat["name"]
    new_name = d.get("name", old_name).strip()
    new_icon = d.get("icon", cat["icon"]).strip()
    if not new_name:
        return jsonify({"error": "Category name is required"}), 400
    try:
        db.execute("UPDATE categories SET name=?, icon=? WHERE id=?", (new_name, new_icon, cat_id))
        # Rename in transactions, learned_merchants, and budgets if name changed
        if new_name != old_name:
            db.execute("UPDATE transactions SET category=? WHERE category=?", (new_name, old_name))
            db.execute("UPDATE learned_merchants SET category=? WHERE category=?", (new_name, old_name))
            db.execute("UPDATE budgets SET category=? WHERE category=?", (new_name, old_name))
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "A category with that name already exists"}), 409

@app.route("/api/categories/<int:cat_id>", methods=["DELETE"])
def api_categories_delete(cat_id):
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    if not cat:
        return jsonify({"error": "Category not found"}), 404
    reassign_to = request.args.get("reassign", "")
    usage = db.execute("SELECT COUNT(*) as c FROM transactions WHERE category=?", (cat["name"],)).fetchone()["c"]
    if usage > 0 and not reassign_to:
        return jsonify({"error": "in_use", "count": usage,
                        "message": f"{usage} transactions use this category. Provide a reassign target."}), 409
    if usage > 0 and reassign_to:
        db.execute("UPDATE transactions SET category=? WHERE category=?", (reassign_to, cat["name"]))
        db.execute("UPDATE budgets SET category=? WHERE category=?", (reassign_to, cat["name"]))
        db.execute("UPDATE learned_merchants SET category=? WHERE category=?", (reassign_to, cat["name"]))
    db.execute("DELETE FROM budgets WHERE category=?", (cat["name"],))
    db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    db.commit()
    return jsonify({"ok": True, "reassigned": usage if reassign_to else 0})

@app.route("/api/averages")
def api_averages():
    """Monthly average spend per category based on last 6 months."""
    db = get_db()
    months_with_data = db.execute("""
        SELECT DISTINCT substr(date,1,7) as m FROM transactions
        WHERE type='Expense' ORDER BY m DESC LIMIT 6
    """).fetchall()
    n = len(months_with_data)
    if n == 0:
        return jsonify([])
    placeholders = ','.join('?'*n)
    rows = db.execute(f"""
        SELECT category,
               ROUND(SUM(amount)/{n}, 2) as avg_monthly,
               COUNT(DISTINCT substr(date,1,7)) as months_seen
        FROM transactions WHERE type='Expense'
        AND substr(date,1,7) IN ({placeholders})
        GROUP BY category ORDER BY avg_monthly DESC
    """, [r['m'] for r in months_with_data]).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/")
def index():
    return render_template_string(HTML)

# ── HTML / CSS / JS ───────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CanadaFinance</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {
  --bg:#0e0f11; --surface:#16181c; --surface2:#1e2128; --border:#2a2d35;
  --text:#e8eaf0; --muted:#6b7280; --accent:#6ee7b7; --red:#f87171;
  --blue:#60a5fa; --purple:#a78bfa; --amber:#f59e0b;
  --mono:'DM Mono',monospace; --sans:'DM Sans',sans-serif;
  --radius:12px;
}
[data-theme=light] {
  --bg:#f8f9fa; --surface:#ffffff; --surface2:#f1f3f5; --border:#dee2e6;
  --text:#212529; --muted:#868e96;
}
*{box-sizing:border-box;margin:0;padding:0}
html{font-size:14px}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh;transition:background .2s,color .2s}

/* Layout */
.shell{display:flex;min-height:100vh}
.sidebar{width:230px;background:var(--surface);border-right:1px solid var(--border);
  padding:24px 16px;display:flex;flex-direction:column;gap:4px;flex-shrink:0;
  position:sticky;top:0;height:100vh;overflow-y:auto}
.main{flex:1;padding:28px 32px;overflow-x:hidden;max-width:1200px}

/* Sidebar */
.logo{font-family:var(--mono);font-size:12px;color:var(--accent);letter-spacing:2px;
  text-transform:uppercase;margin-bottom:24px;padding-bottom:14px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:8px}
.logo-icon{font-size:18px}
.nav-label{font-size:10px;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;
  margin:14px 0 4px 8px;font-family:var(--mono)}
.nav-btn{background:none;border:none;color:var(--muted);font-family:var(--sans);font-size:13px;
  padding:8px 12px;border-radius:8px;cursor:pointer;text-align:left;width:100%;
  transition:all .15s;display:flex;align-items:center;gap:9px;line-height:1.3}
.nav-btn:hover{background:var(--surface2);color:var(--text)}
.nav-btn.active{background:var(--surface2);color:var(--accent);font-weight:500}
.nav-btn svg{flex-shrink:0;opacity:.6}
.nav-btn.active svg{opacity:1}
.sidebar-bottom{margin-top:auto;padding-top:12px;border-top:1px solid var(--border)}

/* Month nav */
.month-row{display:flex;align-items:center;gap:10px;margin-bottom:24px}
.month-label{font-family:var(--mono);font-size:18px;font-weight:500;flex:1}
.month-btn{background:var(--surface);border:1px solid var(--border);color:var(--text);
  width:30px;height:30px;border-radius:8px;cursor:pointer;font-size:15px;
  display:flex;align-items:center;justify-content:center;transition:all .15s}
.month-btn:hover{border-color:var(--accent);color:var(--accent)}

/* Cards */
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px}
.card-label{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;
  font-family:var(--mono);margin-bottom:8px}
.card-value{font-family:var(--mono);font-size:22px;font-weight:500}
.card-value.green{color:var(--accent)}
.card-value.red{color:var(--red)}
.card-value.blue{color:var(--blue)}
.card-sub{font-size:11px;color:var(--muted);margin-top:5px;font-family:var(--mono)}
.card-sub.up{color:#4ade80}.card-sub.down{color:var(--red)}

/* Panels */
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:24px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px 22px}
.panel-title{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;
  font-family:var(--mono);margin-bottom:16px;display:flex;align-items:center;justify-content:space-between}

/* Cat list */
.cat-row{display:flex;align-items:center;gap:10px;padding:7px 0;
  border-bottom:1px solid var(--border);cursor:pointer;transition:opacity .15s}
.cat-row:last-child{border:none}
.cat-row:hover{opacity:.8}
.cat-name{flex:1;font-size:13px}
.cat-bar-wrap{width:60px;height:3px;background:var(--border);border-radius:2px}
.cat-bar{height:3px;border-radius:2px;background:var(--accent);transition:width .4s}
.cat-budget{font-size:10px;font-family:var(--mono);color:var(--muted);min-width:32px;text-align:right}
.cat-budget.over{color:var(--red)}
.cat-amt{font-family:var(--mono);font-size:12px;min-width:64px;text-align:right}

/* Budget bar */
.budget-bar-wrap{width:60px;height:3px;background:var(--border);border-radius:2px;overflow:hidden}
.budget-bar{height:3px;border-radius:2px;transition:width .4s}

/* Chart */
.chart-wrap{position:relative;height:200px}

/* Transactions */
.txn-header{display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.txn-title{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;
  font-family:var(--mono);flex:1}
.filter-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
select,input[type=text],input[type=date],input[type=number]{
  background:var(--surface2);border:1px solid var(--border);color:var(--text);
  font-family:var(--sans);font-size:13px;padding:7px 11px;border-radius:8px;outline:none}
select:focus,input:focus{border-color:var(--accent)}

.txn-table{width:100%;border-collapse:collapse}
.txn-table th{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;
  font-family:var(--mono);padding:0 10px 10px;text-align:left;white-space:nowrap}
.txn-table td{padding:10px;border-bottom:1px solid var(--border);font-size:13px;vertical-align:middle}
.txn-table tr:last-child td{border:none}
.txn-table tr:hover td{background:var(--surface2)}
.txn-table tr{cursor:pointer;transition:background .1s}
.badge{display:inline-block;font-size:11px;font-family:var(--mono);padding:2px 8px;
  border-radius:20px;background:var(--surface2);color:var(--muted);white-space:nowrap}
.badge.income{background:rgba(110,231,183,.12);color:var(--accent)}
.badge.expense{background:rgba(248,113,113,.1);color:var(--red)}
.amt-income{font-family:var(--mono);color:var(--accent)}
.amt-expense{font-family:var(--mono);color:var(--red)}
.del-btn{background:none;border:none;color:var(--border);cursor:pointer;font-size:16px;
  padding:2px 5px;border-radius:4px;transition:all .15s;line-height:1}
.del-btn:hover{color:var(--red);background:rgba(248,113,113,.1)}

/* Buttons */
.btn{background:var(--accent);color:#0e0f11;border:none;font-family:var(--sans);
  font-weight:600;font-size:13px;padding:8px 16px;border-radius:8px;cursor:pointer;transition:all .15s}
.btn:hover{opacity:.85}
.btn-ghost{background:var(--surface2);color:var(--text);border:1px solid var(--border)}
.btn-ghost:hover{border-color:var(--accent);color:var(--accent)}
.btn-sm{padding:5px 12px;font-size:12px}
.btn-red{background:rgba(248,113,113,.15);color:var(--red);border:1px solid rgba(248,113,113,.3)}
.btn-red:hover{background:rgba(248,113,113,.25)}
.btn-icon{background:none;border:none;cursor:pointer;color:var(--muted);font-size:16px;
  padding:4px 6px;border-radius:6px;transition:all .15s}
.btn-icon:hover{color:var(--text);background:var(--surface2)}

/* Modal */
.modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.65);display:none;
  align-items:center;justify-content:center;z-index:200;backdrop-filter:blur(4px)}
.modal-backdrop.open{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:18px;
  padding:26px 30px;width:480px;max-width:95vw;max-height:90vh;overflow-y:auto}
.modal-title{font-size:15px;font-weight:600;margin-bottom:20px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.form-group{display:flex;flex-direction:column;gap:5px}
.form-group.full{grid-column:1/-1}
label{font-size:10px;color:var(--muted);letter-spacing:.5px;text-transform:uppercase;font-family:var(--mono)}
.form-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:20px}

/* Import */
.drop-zone{border:2px dashed var(--border);border-radius:var(--radius);padding:36px 20px;
  text-align:center;cursor:pointer;transition:all .2s}
.drop-zone:hover,.drop-zone.drag{border-color:var(--accent);background:rgba(110,231,183,.04)}
.drop-zone p{color:var(--muted);font-size:13px;margin-top:6px}
.file-icon{font-size:26px;margin-bottom:4px}
.import-results{margin-top:16px;display:flex;flex-direction:column;gap:6px}
.result-row{background:var(--surface2);border-radius:8px;padding:10px 14px;
  display:flex;align-items:center;gap:10px;font-size:13px}
.result-bank{font-family:var(--mono);font-size:10px;color:var(--muted)}

/* Search banner */
.search-banner{padding:6px 0 12px;font-size:12px;color:var(--muted);font-family:var(--mono)}

/* Settings */
.settings-section{margin-bottom:28px}
.settings-title{font-size:12px;font-weight:600;margin-bottom:12px;color:var(--text)}
.settings-row{display:flex;align-items:center;justify-content:space-between;
  padding:10px 0;border-bottom:1px solid var(--border)}
.settings-row:last-child{border:none}
.settings-label{font-size:13px}
.settings-sub{font-size:11px;color:var(--muted);margin-top:2px}
.tag{display:inline-flex;align-items:center;gap:5px;background:var(--surface2);
  border:1px solid var(--border);border-radius:20px;padding:3px 10px;font-size:12px;
  font-family:var(--mono);margin:2px}
.tag .x{cursor:pointer;color:var(--muted);font-size:14px;line-height:1}
.tag .x:hover{color:var(--red)}

/* Year view */
.year-bar-row{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--border)}
.year-bar-row:last-child{border:none}
.year-month{font-family:var(--mono);font-size:11px;color:var(--muted);width:60px;flex-shrink:0}
.year-bar-wrap{flex:1;display:flex;flex-direction:column;gap:3px}
.year-bar{height:6px;border-radius:3px;transition:width .4s;min-width:2px}
.year-bar.income{background:var(--accent)}
.year-bar.expense{background:var(--red)}
.year-amounts{display:flex;gap:12px;font-family:var(--mono);font-size:11px}

/* Averages panel uses existing cat-row styles */

/* Toast */
.toast{position:fixed;bottom:20px;right:20px;background:var(--surface2);
  border:1px solid var(--border);border-radius:10px;padding:10px 18px;font-size:13px;
  transform:translateY(80px);opacity:0;transition:all .3s;z-index:300;max-width:320px}
.toast.show{transform:translateY(0);opacity:1}
.toast.success{border-color:var(--accent);color:var(--accent)}
.toast.error{border-color:var(--red);color:var(--red)}

/* Sections */
.section{display:none}
.section.active{display:block}
.empty{color:var(--muted);font-size:13px;text-align:center;padding:36px 0;font-family:var(--mono)}

/* Toggle switch */
.toggle{position:relative;width:40px;height:22px}
.toggle input{opacity:0;width:0;height:0}
.toggle-slider{position:absolute;inset:0;background:var(--border);border-radius:22px;cursor:pointer;transition:.3s}
.toggle-slider:before{content:'';position:absolute;width:16px;height:16px;left:3px;bottom:3px;
  background:#fff;border-radius:50%;transition:.3s}
.toggle input:checked + .toggle-slider{background:var(--accent)}
.toggle input:checked + .toggle-slider:before{transform:translateX(18px)}

/* Responsive */
@media(max-width:900px){
  .cards{grid-template-columns:1fr 1fr}
  .grid2{grid-template-columns:1fr}
}
@media(max-width:600px){
  .sidebar{display:none}
  .main{padding:16px}
  .cards{grid-template-columns:1fr}
}
</style>
</head>
<body>
<div class="shell">

<!-- SIDEBAR -->
<aside class="sidebar">
  <div class="logo"><span class="logo-icon">🍁</span>CanadaFinance</div>

  <span class="nav-label">Views</span>
  <button class="nav-btn active" onclick="nav('dashboard')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
    Dashboard
  </button>
  <button class="nav-btn" onclick="nav('transactions')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
    Transactions
  </button>
  <button class="nav-btn" onclick="nav('year')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
    Year Review
  </button>
  <button class="nav-btn" onclick="nav('import')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
    Import CSV
  </button>
  <button class="nav-btn" onclick="nav('settings')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
    Settings
  </button>

  <span class="nav-label">Actions</span>
  <button class="nav-btn" onclick="openAddModal()">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/></svg>
    Add Transaction
  </button>
  <button class="nav-btn" onclick="exportCSV(false)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
    Export Month
  </button>
  <button class="nav-btn" onclick="exportCSV(true)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
    Export All
  </button>

  <div class="sidebar-bottom">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0">
      <span style="font-size:12px;color:var(--muted)">Dark mode</span>
      <label class="toggle">
        <input type="checkbox" id="theme-toggle" onchange="toggleTheme()" checked>
        <span class="toggle-slider"></span>
      </label>
    </div>
  </div>
</aside>

<!-- MAIN -->
<main class="main">

<!-- DASHBOARD -->
<section id="sec-dashboard" class="section active">
  <div class="month-row">
    <button class="month-btn" onclick="changeMonth(-1)">←</button>
    <div class="month-label" id="month-display">—</div>
    <button class="month-btn" onclick="changeMonth(1)">→</button>
  </div>
  <div class="cards">
    <div class="card">
      <div class="card-label">Income</div>
      <div class="card-value green" id="card-income">$—</div>
      <div class="card-sub" id="card-income-src">—</div>
    </div>
    <div class="card">
      <div class="card-label">Expenses</div>
      <div class="card-value red" id="card-expense">$—</div>
      <div class="card-sub" id="card-expense-vs">—</div>
    </div>
    <div class="card">
      <div class="card-label">Net Saved</div>
      <div class="card-value" id="card-net">$—</div>
      <div class="card-sub" id="card-net-sub">—</div>
    </div>
    <div class="card">
      <div class="card-label">Savings Rate</div>
      <div class="card-value blue" id="card-rate">—%</div>
      <div class="card-sub" id="card-rate-sub">of income saved</div>
    </div>
  </div>
  <div class="grid2">
    <div class="panel">
      <div class="panel-title">
        Spending by Category
        <button class="btn-icon" title="Set budgets" onclick="nav('settings');showBudgetPanel()">⚙</button>
      </div>
      <div id="cat-list"></div>
    </div>
    <div class="panel">
      <div class="panel-title">Breakdown</div>
      <div class="chart-wrap"><canvas id="donut-chart"></canvas></div>
    </div>
  </div>
  <div class="grid2">
    <div class="panel">
      <div class="panel-title">Monthly Averages <span id="avg-subtitle" style="font-size:10px;color:var(--muted);font-weight:normal"></span></div>
      <div id="averages-list"><div class="empty">Loading…</div></div>
    </div>
    <div class="panel">
      <div class="panel-title">Recent Transactions</div>
      <table class="txn-table">
        <thead><tr><th>Date</th><th>Name</th><th>Category</th><th style="text-align:right">Amount</th></tr></thead>
        <tbody id="recent-txns"></tbody>
      </table>
    </div>
  </div>
</section>

<!-- TRANSACTIONS -->
<section id="sec-transactions" class="section">
  <div class="txn-header">
    <div class="txn-title">All Transactions</div>
    <div class="filter-row">
      <input type="text" id="search-input" placeholder="Search — costco, eating out, 2026-03…"
        style="width:260px" oninput="onSearchInput()" onkeydown="if(event.key==='Escape')clearSearch()">
      <select id="filter-type" onchange="loadTransactions()">
        <option value="">All Types</option>
        <option value="Expense">Expenses</option>
        <option value="Income">Income</option>
      </select>
      <select id="filter-cat" onchange="loadTransactions()"><option value="">All Categories</option></select>
      <button class="btn btn-sm" onclick="openAddModal()">+ Add</button>
    </div>
  </div>
  <div id="search-banner" class="search-banner" style="display:none"></div>
  <table class="txn-table">
    <thead><tr>
      <th>Date</th><th>Name</th><th>Category</th><th>Account</th>
      <th>Type</th><th style="text-align:right">Amount</th><th></th>
    </tr></thead>
    <tbody id="all-txns"></tbody>
  </table>
  <div id="txn-empty" class="empty" style="display:none">No transactions found</div>
</section>

<!-- YEAR REVIEW -->
<section id="sec-year" class="section">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px">
    <button class="month-btn" onclick="changeYear(-1)">←</button>
    <div class="month-label" id="year-display">—</div>
    <button class="month-btn" onclick="changeYear(1)">→</button>
  </div>
  <div class="cards" style="grid-template-columns:repeat(3,1fr)" id="year-cards"></div>
  <div class="grid2">
    <div class="panel">
      <div class="panel-title">Monthly Overview</div>
      <div id="year-bars"></div>
    </div>
    <div class="panel">
      <div class="panel-title">Top 5 Categories</div>
      <div id="year-cats"></div>
    </div>
  </div>
</section>

<!-- IMPORT -->
<section id="sec-import" class="section">
  <div class="panel" style="max-width:580px">
    <div class="panel-title">Import Bank CSVs</div>
    <div class="drop-zone" id="drop-zone" onclick="document.getElementById('csv-input').click()"
      ondragover="event.preventDefault();this.classList.add('drag')"
      ondragleave="this.classList.remove('drag')"
      ondrop="handleDrop(event)">
      <div class="file-icon">📂</div>
      <strong>Drop CSV files here</strong>
      <p>Tangerine · Wealthsimple · TD · RBC · CIBC · Scotiabank · BMO · National Bank</p>
    </div>
    <input type="file" id="csv-input" multiple accept=".csv" style="display:none" onchange="handleFiles(this.files)">
    <div class="import-results" id="import-results"></div>
  </div>
</section>

<!-- SETTINGS -->
<section id="sec-settings" class="section">
  <div style="max-width:600px">

    <div class="settings-section">
      <div class="settings-title">Categories</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:12px">
        Manage expense and income categories. Custom categories can be added, renamed, or deleted.
      </p>
      <div style="margin-bottom:12px">
        <div style="font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;font-family:var(--mono);margin-bottom:6px">Expense Categories</div>
        <div id="expense-cat-list"></div>
      </div>
      <div style="margin-bottom:12px">
        <div style="font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;font-family:var(--mono);margin-bottom:6px">Income Categories</div>
        <div id="income-cat-list"></div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <input type="text" id="new-cat-name" placeholder="New category name" style="flex:1;min-width:140px">
        <input type="text" id="new-cat-icon" placeholder="🏷️" style="width:50px;text-align:center" maxlength="2">
        <select id="new-cat-type" style="width:110px">
          <option value="Expense">Expense</option>
          <option value="Income">Income</option>
        </select>
        <button class="btn btn-sm" onclick="addCategory()">Add</button>
      </div>
    </div>

    <div class="settings-section" id="budget-panel">
      <div class="settings-title">Monthly Budgets</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:12px">
        Set spending limits per category. Progress bars appear on the dashboard.
      </p>
      <div id="budget-list" style="margin-bottom:12px"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <select id="budget-cat" style="flex:1;min-width:160px">
          <option value="">Select category…</option>
        </select>
        <input type="number" id="budget-amt" placeholder="$" style="width:100px" min="1">
        <button class="btn btn-sm" onclick="saveBudget()">Set Budget</button>
      </div>
    </div>

    <div class="settings-section">
      <div class="settings-title">Learned Merchants</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:12px">
        Categories you've set manually. Deleted entries revert to auto-categorization.
      </p>
      <div id="learned-list"></div>
    </div>

  </div>
</section>

</main>
</div>

<!-- ADD MODAL -->
<div class="modal-backdrop" id="add-modal">
  <div class="modal">
    <div class="modal-title">Add Transaction</div>
    <div class="form-grid">
      <div class="form-group"><label>Date</label><input type="date" id="f-date"></div>
      <div class="form-group"><label>Type</label>
        <select id="f-type" onchange="updateCatOptions('f-category','f-type')">
          <option value="Expense">Expense</option>
          <option value="Income">Income</option>
        </select>
      </div>
      <div class="form-group full"><label>Name / Description</label>
        <input type="text" id="f-name" placeholder="e.g. Tim Hortons, Dad car payment">
      </div>
      <div class="form-group"><label>Category</label><select id="f-category"></select></div>
      <div class="form-group"><label>Amount ($)</label>
        <input type="number" id="f-amount" step="0.01" min="0" placeholder="0.00">
      </div>
      <div class="form-group"><label>Account</label>
        <select id="f-account">
          <option>Tangerine Credit Card</option><option>Tangerine Chequing</option>
          <option>Wealthsimple Chequing</option><option>RBC Chequing</option>
          <option>TD Chequing</option><option>CIBC Chequing</option>
          <option>Scotiabank</option><option>BMO Chequing</option>
          <option>National Bank</option><option>Cash</option><option>Other</option>
        </select>
      </div>
      <div class="form-group full"><label>Notes (optional)</label>
        <input type="text" id="f-notes" placeholder="e.g. March car payment to Dad">
      </div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal('add-modal')">Cancel</button>
      <button class="btn" onclick="submitAdd()">Add</button>
    </div>
  </div>
</div>

<!-- EDIT MODAL -->
<div class="modal-backdrop" id="edit-modal">
  <div class="modal">
    <div class="modal-title">Edit Transaction</div>
    <input type="hidden" id="e-id">
    <div class="form-grid">
      <div class="form-group"><label>Date</label><input type="date" id="e-date"></div>
      <div class="form-group"><label>Type</label>
        <select id="e-type" onchange="updateCatOptions('e-category','e-type')">
          <option value="Expense">Expense</option><option value="Income">Income</option>
        </select>
      </div>
      <div class="form-group full"><label>Name</label><input type="text" id="e-name"></div>
      <div class="form-group"><label>Category</label><select id="e-category"></select></div>
      <div class="form-group"><label>Amount ($)</label>
        <input type="number" id="e-amount" step="0.01" min="0">
      </div>
      <div class="form-group"><label>Account</label>
        <select id="e-account">
          <option>Tangerine Credit Card</option><option>Tangerine Chequing</option>
          <option>Wealthsimple Chequing</option><option>RBC Chequing</option>
          <option>TD Chequing</option><option>CIBC Chequing</option>
          <option>Scotiabank</option><option>BMO Chequing</option>
          <option>National Bank</option><option>Cash</option><option>Other</option>
        </select>
      </div>
      <div class="form-group full"><label>Notes</label><input type="text" id="e-notes"></div>
    </div>
    <div class="form-actions">
      <button class="btn btn-red btn-sm" onclick="deleteFromEdit()">Delete</button>
      <div style="flex:1"></div>
      <button class="btn btn-ghost" onclick="closeModal('edit-modal')">Cancel</button>
      <button class="btn" onclick="submitEdit()">Save</button>
    </div>
  </div>
</div>

<!-- UNKNOWN CSV WIZARD MODAL -->
<div class="modal-backdrop" id="csv-wizard-modal">
  <div class="modal" style="width:640px">
    <!-- Step 1: Preview -->
    <div id="wizard-step-1">
      <div class="modal-title">⚠ Unknown Bank Format</div>
      <p style="font-size:13px;color:var(--muted);margin-bottom:14px">
        We don't recognize this CSV format. Map the columns below so we can import it.
      </p>
      <div style="overflow-x:auto;margin-bottom:16px">
        <table class="txn-table" id="wizard-preview-table" style="font-size:12px"></table>
      </div>
      <div class="form-actions">
        <button class="btn btn-ghost" onclick="closeModal('csv-wizard-modal')">Cancel</button>
        <button class="btn" onclick="wizardStep(2)">Map Columns →</button>
      </div>
    </div>
    <!-- Step 2: Column Mapping -->
    <div id="wizard-step-2" style="display:none">
      <div class="modal-title">Map Columns</div>
      <div class="form-grid">
        <div class="form-group">
          <label>Date Column</label>
          <select id="wiz-date-col"></select>
        </div>
        <div class="form-group">
          <label>Date Format</label>
          <select id="wiz-date-fmt">
            <option value="%Y-%m-%d">YYYY-MM-DD</option>
            <option value="%m/%d/%Y">MM/DD/YYYY</option>
            <option value="%d/%m/%Y">DD/MM/YYYY</option>
            <option value="%m-%d-%Y">MM-DD-YYYY</option>
            <option value="%d-%m-%Y">DD-MM-YYYY</option>
          </select>
        </div>
        <div class="form-group full">
          <label>Description Column</label>
          <select id="wiz-desc-col"></select>
        </div>
        <div class="form-group full">
          <label>Amount Structure</label>
          <select id="wiz-amt-mode" onchange="toggleAmountMode()">
            <option value="single">Single column (positive/negative)</option>
            <option value="split">Two columns (Debit &amp; Credit)</option>
          </select>
        </div>
        <div id="wiz-single-amt" class="form-group full">
          <label>Amount Column</label>
          <select id="wiz-amt-col"></select>
        </div>
        <div id="wiz-split-amt" style="display:none" class="form-grid full">
          <div class="form-group">
            <label>Debit / Withdrawal Column</label>
            <select id="wiz-debit-col"></select>
          </div>
          <div class="form-group">
            <label>Credit / Deposit Column</label>
            <select id="wiz-credit-col"></select>
          </div>
        </div>
      </div>
      <div class="form-actions" style="margin-top:16px">
        <button class="btn btn-ghost" onclick="wizardStep(1)">← Back</button>
        <button class="btn" onclick="wizardStep(3)">Name Bank →</button>
      </div>
    </div>
    <!-- Step 3: Name & Preview -->
    <div id="wizard-step-3" style="display:none">
      <div class="modal-title">Name This Bank</div>
      <div class="form-group" style="margin-bottom:16px">
        <label>Bank / Account Name</label>
        <input type="text" id="wiz-bank-name" placeholder="e.g. ATB Financial Chequing" style="width:100%">
      </div>
      <button class="btn btn-ghost btn-sm" onclick="wizardPreview()" style="margin-bottom:12px">
        🔍 Test — preview parsed transactions
      </button>
      <div id="wizard-preview-parsed" style="max-height:200px;overflow-y:auto;margin-bottom:12px"></div>
      <div class="form-actions">
        <button class="btn btn-ghost" onclick="wizardStep(2)">← Back</button>
        <button class="btn" onclick="wizardSaveAndImport()">Save Config & Import</button>
      </div>
      <div style="margin-top:12px;font-size:11px;color:var(--muted)">
        💡 Want to share this config with the community?
        <a href="https://github.com/topics/canadafinance" target="_blank" style="color:var(--accent)">Submit on GitHub</a>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let EXPENSE_CATS = [];
let INCOME_CATS = [];
let ALL_CATEGORIES = [];
const PALETTE = ["#6ee7b7","#f59e0b","#60a5fa","#a78bfa","#f87171","#34d399",
  "#fbbf24","#818cf8","#fb7185","#4ade80","#e879f9","#38bdf8","#fb923c","#a3e635"];

let months = [], currentMonthIdx = 0, donutChart = null;
let currentYear = new Date().getFullYear();

async function loadCategories() {
  ALL_CATEGORIES = await fetch('/api/categories').then(r=>r.json());
  EXPENSE_CATS = ALL_CATEGORIES.filter(c=>c.type==='Expense').map(c=>c.name);
  INCOME_CATS = ALL_CATEGORIES.filter(c=>c.type==='Income').map(c=>c.name);
  EXPENSE_CATS.push('UNCATEGORIZED');
}

// ── THEME ─────────────────────────────────────────────────────────────────────
function toggleTheme() {
  const dark = document.getElementById('theme-toggle').checked;
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: dark ? 'dark' : 'light'})});
}

// ── INIT ──────────────────────────────────────────────────────────────────────
async function init() {
  // Load categories from DB
  await loadCategories();

  // Load settings
  const settings = await fetch('/api/settings').then(r=>r.json());
  const dark = settings.theme !== 'light';
  document.getElementById('theme-toggle').checked = dark;
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');

  const res = await fetch('/api/months');
  months = await res.json();
  if (!months.length) {
    document.getElementById('month-display').textContent = 'No data yet — import a CSV!';
    populateCatFilter();
    updateCatOptions('f-category','f-type');
    populateBudgetCat();
    return;
  }
  currentMonthIdx = 0;
  document.getElementById('f-date').value = new Date().toISOString().slice(0,10);
  populateCatFilter();
  updateCatOptions('f-category','f-type');
  populateBudgetCat();
  renderMonth();
  loadSettings();
}

const fmt = n => '$' + Math.abs(n).toLocaleString('en-CA',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtMonth = m => { const [y,mo]=m.split('-'); return new Date(y,mo-1).toLocaleString('default',{month:'long',year:'numeric'}); };

// ── MONTH NAV ─────────────────────────────────────────────────────────────────
function changeMonth(dir) {
  currentMonthIdx = Math.max(0, Math.min(months.length-1, currentMonthIdx-dir));
  renderMonth();
}

async function renderMonth() {
  const m = months[currentMonthIdx];
  document.getElementById('month-display').textContent = fmtMonth(m);
  const [summary, txns] = await Promise.all([
    fetch(`/api/summary?month=${m}`).then(r=>r.json()),
    fetch(`/api/transactions?month=${m}`).then(r=>r.json()),
  ]);
  renderCards(summary, txns);
  renderCatList(summary.by_category);
  renderDonut(summary.by_category);
  renderRecentTxns(txns.filter(t=>t.type==='Expense').slice(0,6));
  renderAverages();
  if (document.getElementById('sec-transactions').classList.contains('active')) loadTransactions();
}

// ── CARDS ─────────────────────────────────────────────────────────────────────
function renderCards(s, txns) {
  document.getElementById('card-income').textContent = fmt(s.income);
  const srcs = s.income_by_category.map(c=>`${c.category}: ${fmt(c.total)}`).join(' · ');
  document.getElementById('card-income-src').textContent = srcs || '—';

  document.getElementById('card-expense').textContent = fmt(s.expenses);
  const diff = s.expenses - s.prev_expenses;
  const vsEl = document.getElementById('card-expense-vs');
  if (s.prev_expenses > 0) {
    vsEl.textContent = (diff>=0?'↑ ':'↓ ') + fmt(Math.abs(diff)) + ' vs last month';
    vsEl.className = 'card-sub ' + (diff>0?'down':'up');
  } else { vsEl.textContent = txns.filter(t=>t.type==='Expense').length + ' transactions'; vsEl.className='card-sub'; }

  const net = document.getElementById('card-net');
  net.textContent = (s.net<0?'-':'+') + fmt(s.net);
  net.className = 'card-value ' + (s.net>=0?'green':'red');
  document.getElementById('card-net-sub').textContent = 'income − expenses';

  document.getElementById('card-rate').textContent = s.savings_rate + '%';
  const rateEl = document.getElementById('card-rate-sub');
  rateEl.textContent = s.savings_rate >= 20 ? '🎯 great saving!' : s.savings_rate >= 10 ? 'of income saved' : 'of income saved';
  rateEl.className = 'card-sub ' + (s.savings_rate>=20?'up':s.savings_rate<0?'down':'');
}

// ── CAT LIST ──────────────────────────────────────────────────────────────────
function renderCatList(cats) {
  const max = cats[0]?.total || 1;
  document.getElementById('cat-list').innerHTML = cats.length ? cats.map(c => {
    const bPct = c.budget ? Math.min(c.total/c.budget*100,100).toFixed(0) : null;
    const bColor = c.budget ? (c.total>c.budget?'var(--red)':c.total>c.budget*.8?'var(--amber)':'var(--accent)') : 'var(--accent)';
    return `<div class="cat-row" onclick="filterByCat('${c.category}')">
      <span class="cat-name">${c.category}</span>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(c.total/max*100).toFixed(0)}%;background:${bColor}"></div></div>
      ${c.budget ? `<span class="cat-budget ${c.total>c.budget?'over':''}">${Math.round(c.total/c.budget*100)}%</span>` : ''}
      <span class="cat-amt">${fmt(c.total)}</span>
    </div>`;
  }).join('') : '<div class="empty">No expenses this month</div>';
}

// ── DONUT ─────────────────────────────────────────────────────────────────────
function renderDonut(cats) {
  const ctx = document.getElementById('donut-chart').getContext('2d');
  if (donutChart) donutChart.destroy();
  if (!cats.length) return;
  donutChart = new Chart(ctx, {
    type:'doughnut',
    data:{ labels:cats.map(c=>c.category), datasets:[{data:cats.map(c=>c.total),
      backgroundColor:PALETTE, borderWidth:2, borderColor:getComputedStyle(document.documentElement).getPropertyValue('--surface').trim()}]},
    options:{cutout:'68%',plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>` ${fmt(c.raw)}`}}}}
  });
}

// ── RECURRING ─────────────────────────────────────────────────────────────────
async function renderAverages() {
  const data = await fetch('/api/averages').then(r=>r.json());
  const el = document.getElementById('averages-list');
  if (!data.length) { el.innerHTML = '<div class="empty">Not enough data yet</div>'; return; }
  const maxAvg = data[0].avg_monthly || 1;
  const n = data[0].months_seen;
  document.getElementById('avg-subtitle').textContent = `last ${n} month${n!==1?'s':''}`;
  el.innerHTML = data.map(r => `
    <div class="cat-row" onclick="filterByCat('${r.category}')" style="cursor:pointer">
      <span class="cat-name">${r.category}</span>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(r.avg_monthly/maxAvg*100).toFixed(0)}%"></div></div>
      <span class="cat-amt">${fmt(r.avg_monthly)}<span style="color:var(--muted);font-size:10px">/mo</span></span>
    </div>`).join('');
}

// ── RECENT TXNS ───────────────────────────────────────────────────────────────
function renderRecentTxns(txns) {
  document.getElementById('recent-txns').innerHTML = txns.length
    ? txns.map(t=>`<tr onclick="openEditModal(${JSON.stringify(t).replace(/"/g,'&quot;')})">
        <td style="font-family:var(--mono);color:var(--muted);font-size:11px">${t.date}</td>
        <td>${t.name}</td>
        <td><span class="badge">${t.category}</span></td>
        <td style="text-align:right" class="amt-expense">${fmt(t.amount)}</td>
      </tr>`).join('')
    : '<tr><td colspan="4" class="empty">No transactions</td></tr>';
}

// ── SEARCH & TRANSACTIONS ─────────────────────────────────────────────────────
let searchTimer = null;
function onSearchInput() { clearTimeout(searchTimer); searchTimer = setTimeout(loadTransactions, 180); }
function clearSearch() { document.getElementById('search-input').value=''; loadTransactions(); }

async function loadTransactions() {
  const m = months[currentMonthIdx] || '';
  const typ = document.getElementById('filter-type')?.value || '';
  const cat = document.getElementById('filter-cat')?.value || '';
  const search = document.getElementById('search-input')?.value.trim() || '';
  const banner = document.getElementById('search-banner');

  const url = search
    ? `/api/transactions?search=${encodeURIComponent(search)}&type=${encodeURIComponent(typ)}`
    : `/api/transactions?month=${m}&type=${encodeURIComponent(typ)}&category=${encodeURIComponent(cat)}`;

  const txns = await fetch(url).then(r=>r.json());
  const tbody = document.getElementById('all-txns');
  const empty = document.getElementById('txn-empty');

  if (search) {
    const total = txns.reduce((s,t)=>t.type==='Expense'?s+t.amount:s,0);
    banner.style.display='block';
    banner.innerHTML = `${txns.length} result${txns.length!==1?'s':''} for "<strong>${search}</strong>"` +
      (total>0?` &nbsp;·&nbsp; ${fmt(total)} total`:'') +
      ` &nbsp;<span style="cursor:pointer;color:var(--accent)" onclick="clearSearch()">✕ clear</span>`;
  } else { banner.style.display='none'; }

  if (!txns.length) { tbody.innerHTML=''; empty.style.display='block'; return; }
  empty.style.display='none';
  tbody.innerHTML = txns.map(t=>`<tr onclick="openEditModal(${JSON.stringify(t).replace(/"/g,'&quot;')})">
    <td style="font-family:var(--mono);color:var(--muted);font-size:11px">${t.date}</td>
    <td>${t.name}</td>
    <td><span class="badge">${t.category}</span></td>
    <td style="color:var(--muted);font-size:11px">${t.account}</td>
    <td><span class="badge ${t.type.toLowerCase()}">${t.type}</span></td>
    <td style="text-align:right" class="${t.type==='Income'?'amt-income':'amt-expense'}">${fmt(t.amount)}</td>
    <td><button class="del-btn" onclick="event.stopPropagation();deleteTx(${t.id})">×</button></td>
  </tr>`).join('');
}

async function deleteTx(id) {
  if (!confirm('Delete this transaction?')) return;
  await fetch(`/api/delete/${id}`, {method:'DELETE'});
  toast('Deleted','success'); renderMonth(); loadTransactions();
}
function filterByCat(cat) {
  nav('transactions');
  document.getElementById('filter-cat').value = cat;
  document.getElementById('filter-type').value = 'Expense';
  loadTransactions();
}
function populateCatFilter() {
  const sel = document.getElementById('filter-cat');
  const current = sel.value;
  sel.innerHTML = '<option value="">All</option>';
  [...EXPENSE_CATS,...INCOME_CATS].forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o);});
  if (current) sel.value = current;
}

// ── YEAR VIEW ─────────────────────────────────────────────────────────────────
function changeYear(dir) { currentYear += dir; renderYear(); }
async function renderYear() {
  document.getElementById('year-display').textContent = currentYear;
  const data = await fetch(`/api/year/${currentYear}`).then(r=>r.json());
  const maxVal = Math.max(...data.months.map(m=>Math.max(m.income,m.expenses)), 1);

  document.getElementById('year-cards').innerHTML = `
    <div class="card"><div class="card-label">Total Income</div>
      <div class="card-value green">${fmt(data.total_income)}</div></div>
    <div class="card"><div class="card-label">Total Expenses</div>
      <div class="card-value red">${fmt(data.total_expenses)}</div></div>
    <div class="card"><div class="card-label">Net Saved</div>
      <div class="card-value ${data.total_income-data.total_expenses>=0?'green':'red'}">${fmt(data.total_income-data.total_expenses)}</div></div>`;

  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  document.getElementById('year-bars').innerHTML = data.months.map((m,i)=>`
    <div class="year-bar-row">
      <span class="year-month">${monthNames[i]}</span>
      <div class="year-bar-wrap">
        <div class="year-bar income" style="width:${(m.income/maxVal*100).toFixed(0)}%"></div>
        <div class="year-bar expense" style="width:${(m.expenses/maxVal*100).toFixed(0)}%"></div>
      </div>
      <div class="year-amounts">
        <span class="amt-income" style="font-size:11px">${m.income>0?fmt(m.income):''}</span>
        <span class="amt-expense" style="font-size:11px">${m.expenses>0?fmt(m.expenses):''}</span>
      </div>
    </div>`).join('');

  const maxCat = data.top_categories[0]?.total || 1;
  document.getElementById('year-cats').innerHTML = data.top_categories.length
    ? data.top_categories.map(c=>`
      <div class="cat-row">
        <span class="cat-name">${c.category}</span>
        <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(c.total/maxCat*100).toFixed(0)}%"></div></div>
        <span class="cat-amt">${fmt(c.total)}</span>
      </div>`).join('')
    : '<div class="empty">No data</div>';
}

// ── SETTINGS ──────────────────────────────────────────────────────────────────
async function loadSettings() {
  loadCategoryList();
  loadBudgets();
  loadLearned();
}

function renderCatRow(c) {
  const icon = c.icon ? `<span style="margin-right:4px">${c.icon}</span>` : '';
  const badge = c.user_created ? '<span style="font-size:9px;color:var(--accent);font-family:var(--mono);margin-left:6px">custom</span>' : '';
  return `<div class="settings-row" data-cat-id="${c.id}">
    <div style="display:flex;align-items:center;gap:6px;flex:1">
      ${icon}<span class="settings-label">${c.name}</span>${badge}
    </div>
    <div style="display:flex;gap:4px">
      <button class="btn-icon" onclick="renameCategory(${c.id},'${c.name.replace(/'/g,"\\'")}','${(c.icon||'').replace(/'/g,"\\'")}')">✏️</button>
      <button class="btn-icon" onclick="deleteCategory(${c.id},'${c.name.replace(/'/g,"\\'")}','${c.type}')">🗑️</button>
    </div>
  </div>`;
}

function loadCategoryList() {
  document.getElementById('expense-cat-list').innerHTML =
    ALL_CATEGORIES.filter(c=>c.type==='Expense').map(renderCatRow).join('')
    || '<div style="color:var(--muted);font-size:12px">No expense categories</div>';
  document.getElementById('income-cat-list').innerHTML =
    ALL_CATEGORIES.filter(c=>c.type==='Income').map(renderCatRow).join('')
    || '<div style="color:var(--muted);font-size:12px">No income categories</div>';
}

async function addCategory() {
  const name = document.getElementById('new-cat-name').value.trim();
  const icon = document.getElementById('new-cat-icon').value.trim();
  const type = document.getElementById('new-cat-type').value;
  if (!name) return toast('Enter a category name','error');
  const res = await fetch('/api/categories', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, type, icon})}).then(r=>r.json());
  if (res.ok) {
    document.getElementById('new-cat-name').value = '';
    document.getElementById('new-cat-icon').value = '';
    await loadCategories();
    loadCategoryList();
    populateCatFilter();
    populateBudgetCat();
    toast('Category added ✓','success');
  } else toast(res.error||'Error','error');
}

async function renameCategory(id, oldName, oldIcon) {
  const newName = prompt('Rename category:', oldName);
  if (!newName || newName.trim() === oldName) return;
  const newIcon = prompt('Icon (emoji, optional):', oldIcon) || '';
  const res = await fetch(`/api/categories/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name: newName.trim(), icon: newIcon.trim()})}).then(r=>r.json());
  if (res.ok) {
    await loadCategories();
    loadCategoryList();
    populateCatFilter();
    populateBudgetCat();
    toast('Renamed ✓','success');
  } else toast(res.error||'Error','error');
}

async function deleteCategory(id, name, type) {
  const res = await fetch(`/api/categories/${id}`, {method:'DELETE'}).then(r=>r.json());
  if (res.error === 'in_use') {
    const sameCats = ALL_CATEGORIES.filter(c=>c.type===type && c.name!==name).map(c=>c.name);
    const target = prompt(`${res.count} transactions use "${name}".\nReassign them to which category?\n\nOptions: ${sameCats.join(', ')}`);
    if (!target) return;
    if (!sameCats.includes(target)) return toast('Invalid category','error');
    const res2 = await fetch(`/api/categories/${id}?reassign=${encodeURIComponent(target)}`, {method:'DELETE'}).then(r=>r.json());
    if (res2.ok) {
      await loadCategories();
      loadCategoryList();
      populateCatFilter();
      populateBudgetCat();
      toast(`Deleted & reassigned ${res2.reassigned} transactions ✓`,'success');
      if (months.length) renderMonth();
    } else toast(res2.error||'Error','error');
  } else if (res.ok) {
    await loadCategories();
    loadCategoryList();
    populateCatFilter();
    populateBudgetCat();
    toast('Deleted ✓','success');
  } else toast(res.error||'Error','error');
}

async function loadBudgets() {
  const budgets = await fetch('/api/budgets').then(r=>r.json());
  document.getElementById('budget-list').innerHTML = budgets.length
    ? budgets.map(b=>`<div class="settings-row">
        <div><div class="settings-label">${b.category}</div>
          <div class="settings-sub">${fmt(b.monthly_limit)}/month</div></div>
        <button class="btn btn-red btn-sm" onclick="deleteBudget('${b.category}')">Remove</button>
      </div>`).join('')
    : '<div style="color:var(--muted);font-size:12px;margin-bottom:8px">No budgets set</div>';
}

function populateBudgetCat() {
  const sel = document.getElementById('budget-cat');
  const current = sel.value;
  sel.innerHTML = '<option value="">Select category…</option>';
  EXPENSE_CATS.forEach(c=>{ if(c!=='UNCATEGORIZED'){ const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o); }});
  if (current) sel.value = current;
}

async function saveBudget() {
  const cat = document.getElementById('budget-cat').value;
  const amt = document.getElementById('budget-amt').value;
  if (!cat || !amt) return toast('Select category and amount','error');
  await fetch('/api/budgets', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({category:cat, amount:parseFloat(amt)})});
  document.getElementById('budget-amt').value='';
  loadBudgets(); toast('Budget set ✓','success');
}

async function deleteBudget(cat) {
  await fetch(`/api/budgets/${encodeURIComponent(cat)}`, {method:'DELETE'});
  loadBudgets(); toast('Removed','success');
}

async function loadLearned() {
  const rows = await fetch('/api/learned').then(r=>r.json());
  document.getElementById('learned-list').innerHTML = rows.length
    ? rows.map(r=>`<div class="settings-row">
        <div><div class="settings-label" style="font-family:var(--mono);font-size:12px">${r.keyword}</div>
          <div class="settings-sub">→ ${r.category}</div></div>
        <button class="btn btn-ghost btn-sm" onclick="deleteLearned('${r.keyword.replace(/'/g,"\\'")}')">Remove</button>
      </div>`).join('')
    : '<div style="color:var(--muted);font-size:12px">None yet — edit a transaction category to start learning</div>';
}

async function deleteLearned(keyword) {
  await fetch(`/api/learned/${encodeURIComponent(keyword)}`, {method:'DELETE'});
  loadLearned(); toast('Removed','success');
}

function showBudgetPanel() {
  const el = document.getElementById('budget-panel');
  el.scrollIntoView({behavior:'smooth'});
}

// ── MODALS ────────────────────────────────────────────────────────────────────
function updateCatOptions(selId, typeId) {
  const type = document.getElementById(typeId).value;
  const sel = document.getElementById(selId);
  const cats = type === 'Income' ? INCOME_CATS : EXPENSE_CATS;
  sel.innerHTML = cats.map(c=>`<option>${c}</option>`).join('');
}

function openAddModal() {
  updateCatOptions('f-category','f-type');
  document.getElementById('add-modal').classList.add('open');
}

function openEditModal(t) {
  document.getElementById('e-id').value = t.id;
  document.getElementById('e-date').value = t.date;
  document.getElementById('e-type').value = t.type;
  document.getElementById('e-name').value = t.name;
  document.getElementById('e-amount').value = t.amount;
  document.getElementById('e-notes').value = t.notes || '';
  updateCatOptions('e-category','e-type');
  document.getElementById('e-category').value = t.category;
  const acc = document.getElementById('e-account');
  for (let o of acc.options) if (o.value===t.account) { o.selected=true; break; }
  document.getElementById('edit-modal').classList.add('open');
}

function closeModal(id) { document.getElementById(id).classList.remove('open'); }
document.querySelectorAll('.modal-backdrop').forEach(el=>
  el.addEventListener('click', e=>{ if(e.target===e.currentTarget) el.classList.remove('open'); }));

async function submitAdd() {
  const body = {
    date: document.getElementById('f-date').value,
    type: document.getElementById('f-type').value,
    name: document.getElementById('f-name').value.trim(),
    category: document.getElementById('f-category').value,
    amount: document.getElementById('f-amount').value,
    account: document.getElementById('f-account').value,
    notes: document.getElementById('f-notes').value.trim(),
  };
  if (!body.date||!body.name||!body.amount) return toast('Fill required fields','error');
  const res = await fetch('/api/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await res.json();
  if (data.ok) {
    toast('Added ✓','success'); closeModal('add-modal');
    const mr = await fetch('/api/months').then(r=>r.json()); months=mr;
    const idx = months.indexOf(body.date.slice(0,7)); if(idx!==-1) currentMonthIdx=idx;
    renderMonth();
    ['f-name','f-amount','f-notes'].forEach(id=>document.getElementById(id).value='');
  } else toast(data.error||'Error','error');
}

async function submitEdit() {
  const id = document.getElementById('e-id').value;
  const body = {
    date: document.getElementById('e-date').value,
    type: document.getElementById('e-type').value,
    name: document.getElementById('e-name').value.trim(),
    category: document.getElementById('e-category').value,
    amount: parseFloat(document.getElementById('e-amount').value),
    account: document.getElementById('e-account').value,
    notes: document.getElementById('e-notes').value.trim(),
  };
  const res = await fetch(`/api/update/${id}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await res.json();
  if (data.ok) {
    const extra = data.retro_fixed>0 ? ` · fixed ${data.retro_fixed} other${data.retro_fixed>1?'s':''}` : '';
    toast(`Saved ✓${extra}`,'success'); closeModal('edit-modal'); renderMonth(); loadTransactions();
  } else toast(data.error||'Error','error');
}

async function deleteFromEdit() {
  if (!confirm('Delete this transaction?')) return;
  await fetch(`/api/delete/${document.getElementById('e-id').value}`, {method:'DELETE'});
  toast('Deleted','success'); closeModal('edit-modal'); renderMonth(); loadTransactions();
}

// ── IMPORT ────────────────────────────────────────────────────────────────────
let wizardState = {};

function handleDrop(e) {
  e.preventDefault(); document.getElementById('drop-zone').classList.remove('drag');
  handleFiles(e.dataTransfer.files);
}

function isStaleConfig(lastVerified) {
  if (!lastVerified) return false;
  const parts = lastVerified.split('-');
  const cfgDate = new Date(parseInt(parts[0]), parseInt(parts[1])-1, 1);
  const sixMonthsAgo = new Date();
  sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
  return cfgDate < sixMonthsAgo;
}

async function handleFiles(files) {
  if (!files.length) return;
  const unknownFiles = [];
  const knownFd = new FormData();
  let hasKnown = false;

  // First pass: detect each file
  for (const f of files) {
    const detectFd = new FormData();
    detectFd.append('file', f);
    const det = await fetch('/api/detect-csv', {method:'POST', body:detectFd}).then(r=>r.json());
    if (det.detected) {
      knownFd.append('files', f);
      hasKnown = true;
    } else {
      unknownFiles.push({file: f, headers: det.headers, preview: det.preview, raw_text: det.raw_text});
    }
  }

  // Import known files normally
  if (hasKnown) {
    const data = await fetch('/api/import', {method:'POST', body:knownFd}).then(r=>r.json());
    const resultsHtml = data.map(r => {
      const staleWarn = isStaleConfig(r.last_verified)
        ? `<div style="color:var(--amber);font-size:10px;font-family:var(--mono)">⚠ config last verified ${r.last_verified}</div>` : '';
      return `<div class="result-row">
        <div style="flex:1"><div>${r.file}</div><div class="result-bank">${r.bank}</div>${staleWarn}</div>
        <div style="color:var(--accent);font-family:var(--mono)">+${r.added}</div>
        <div style="color:var(--muted);font-size:11px">${r.dupes} dupes skipped</div>
      </div>`;
    }).join('');
    document.getElementById('import-results').innerHTML = resultsHtml;
    const mr = await fetch('/api/months').then(r=>r.json()); months=mr;
    if (months.length) { currentMonthIdx=0; renderMonth(); }
    toast(`Imported ${data.reduce((s,r)=>s+r.added,0)} transactions`,'success');
  }

  // Open wizard for the first unknown file
  if (unknownFiles.length) {
    openCsvWizard(unknownFiles[0]);
    // Queue remaining unknowns
    wizardState.queue = unknownFiles.slice(1);
  }
}

function openCsvWizard(info) {
  wizardState.headers = info.headers;
  wizardState.preview = info.preview;
  wizardState.raw_text = info.raw_text;
  wizardState.file = info.file;

  // Build preview table
  const table = document.getElementById('wizard-preview-table');
  const ths = info.headers.map(h => `<th>${h}</th>`).join('');
  const rows = info.preview.map(r =>
    `<tr>${info.headers.map(h => `<td>${r[h]||''}</td>`).join('')}</tr>`
  ).join('');
  table.innerHTML = `<thead><tr>${ths}</tr></thead><tbody>${rows}</tbody>`;

  // Populate dropdowns
  const selects = ['wiz-date-col','wiz-desc-col','wiz-amt-col','wiz-debit-col','wiz-credit-col'];
  selects.forEach(id => {
    const sel = document.getElementById(id);
    sel.innerHTML = '<option value="">— select —</option>' +
      info.headers.map(h => `<option value="${h}">${h}</option>`).join('');
  });

  // Auto-guess columns
  info.headers.forEach(h => {
    const hl = h.toLowerCase();
    if (hl.includes('date')) document.getElementById('wiz-date-col').value = h;
    if (hl.includes('description') || hl.includes('payee') || hl.includes('name'))
      document.getElementById('wiz-desc-col').value = h;
    if (hl === 'amount' || hl.includes('amount'))
      document.getElementById('wiz-amt-col').value = h;
    if (hl.includes('debit') || hl.includes('withdrawal'))
      document.getElementById('wiz-debit-col').value = h;
    if (hl.includes('credit') || hl.includes('deposit'))
      document.getElementById('wiz-credit-col').value = h;
  });

  wizardStep(1);
  document.getElementById('csv-wizard-modal').classList.add('open');
}

function wizardStep(n) {
  [1,2,3].forEach(i => document.getElementById(`wizard-step-${i}`).style.display = i===n ? '' : 'none');
}

function toggleAmountMode() {
  const mode = document.getElementById('wiz-amt-mode').value;
  document.getElementById('wiz-single-amt').style.display = mode==='single' ? '' : 'none';
  document.getElementById('wiz-split-amt').style.display = mode==='split' ? '' : 'none';
}

async function wizardPreview() {
  const mapping = getWizardMapping();
  if (!mapping) return;
  const res = await fetch('/api/preview-parse', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({raw_text: wizardState.raw_text, mapping})
  }).then(r=>r.json());
  const el = document.getElementById('wizard-preview-parsed');
  if (res.transactions && res.transactions.length) {
    el.innerHTML = `<div style="font-size:11px;color:var(--muted);margin-bottom:6px">
      ${res.total} transaction${res.total!==1?'s':''} found (showing first ${res.transactions.length})</div>` +
      res.transactions.map(t => `<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:12px">
        <span style="color:var(--muted);font-family:var(--mono);width:80px">${t.date}</span>
        <span style="flex:1">${t.name}</span>
        <span class="badge ${t.type.toLowerCase()}">${t.type}</span>
        <span class="${t.type==='Income'?'amt-income':'amt-expense'}" style="font-family:var(--mono)">${fmt(t.amount)}</span>
      </div>`).join('');
  } else {
    el.innerHTML = '<div style="color:var(--red);font-size:12px">No transactions parsed — check column mapping</div>';
  }
}

function getWizardMapping() {
  const dateCol = document.getElementById('wiz-date-col').value;
  const descCol = document.getElementById('wiz-desc-col').value;
  const bankName = document.getElementById('wiz-bank-name').value.trim() || 'Unknown Bank';
  const dateFmt = document.getElementById('wiz-date-fmt').value;
  const amtMode = document.getElementById('wiz-amt-mode').value;
  if (!dateCol || !descCol) { toast('Select date and description columns','error'); return null; }
  const mapping = {date_column: dateCol, description_column: descCol,
    bank_name: bankName, date_format: dateFmt, amount_mode: amtMode};
  if (amtMode === 'single') {
    mapping.amount_column = document.getElementById('wiz-amt-col').value;
    mapping.amount_sign = 'standard';
    if (!mapping.amount_column) { toast('Select amount column','error'); return null; }
  } else {
    mapping.debit_column = document.getElementById('wiz-debit-col').value;
    mapping.credit_column = document.getElementById('wiz-credit-col').value;
    if (!mapping.debit_column || !mapping.credit_column) { toast('Select debit and credit columns','error'); return null; }
  }
  return mapping;
}

async function wizardSaveAndImport() {
  const mapping = getWizardMapping();
  if (!mapping) return;
  // Pick unique headers from the CSV for detection
  mapping.detection_headers = wizardState.headers.slice(0, 3);
  // Save config
  const saveRes = await fetch('/api/save-bank-config', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(mapping)}).then(r=>r.json());
  if (!saveRes.ok) { toast(saveRes.error||'Error saving config','error'); return; }
  // Re-import the file using the new config
  const fd = new FormData();
  fd.append('files', wizardState.file);
  const data = await fetch('/api/import', {method:'POST', body:fd}).then(r=>r.json());
  const prev = document.getElementById('import-results').innerHTML;
  document.getElementById('import-results').innerHTML = prev + data.map(r=>`
    <div class="result-row">
      <div style="flex:1"><div>${r.file}</div><div class="result-bank">${r.bank} <span style="color:var(--accent);font-size:10px">(new config)</span></div></div>
      <div style="color:var(--accent);font-family:var(--mono)">+${r.added}</div>
      <div style="color:var(--muted);font-size:11px">${r.dupes} dupes skipped</div>
    </div>`).join('');
  closeModal('csv-wizard-modal');
  const mr = await fetch('/api/months').then(r=>r.json()); months=mr;
  if (months.length) { currentMonthIdx=0; renderMonth(); }
  toast(`Config saved! Imported ${data.reduce((s,r)=>s+r.added,0)} transactions`,'success');
  // Process next unknown file in queue
  if (wizardState.queue && wizardState.queue.length) {
    setTimeout(() => openCsvWizard(wizardState.queue.shift()), 300);
  }
}

// ── NAV ───────────────────────────────────────────────────────────────────────
function nav(id) {
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById(`sec-${id}`).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b=>{
    if (b.getAttribute('onclick')?.includes(`'${id}'`)) b.classList.add('active');
  });
  if (id==='transactions') loadTransactions();
  if (id==='year') renderYear();
  if (id==='settings') loadSettings();
}

// ── EXPORT ────────────────────────────────────────────────────────────────────
function exportCSV(allTime) {
  const m = allTime ? '' : (months[currentMonthIdx]||'');
  window.location.href = `/api/export?month=${m}`;
  toast(`Downloading ${allTime?'all transactions':fmtMonth(m)} ✓`,'success');
}

// ── TOAST ─────────────────────────────────────────────────────────────────────
function toast(msg, type='success') {
  const el = document.getElementById('toast');
  el.textContent=msg; el.className=`toast ${type} show`;
  setTimeout(()=>el.classList.remove('show'), 2800);
}

init();
</script>
</body>
</html>"""

if __name__ == "__main__":
    init_db()
    print("\n🍁 CanadaFinance")
    print("   Open: http://localhost:5000")
    print("   Stop: Ctrl+C\n")
    app.run(debug=False, port=5000)
