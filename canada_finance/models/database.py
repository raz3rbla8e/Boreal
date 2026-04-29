import hashlib
import sqlite3

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


def get_db_path():
    return current_app.config["DB_PATH"]


def tx_hash(date_str: str, name: str, amount: float, account: str) -> str:
    key = f"{date_str}|{name}|{amount:.2f}|{account}"
    return hashlib.sha256(key.encode()).hexdigest()


def get_setting(key, default=""):
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


# ── Schema migrations ─────────────────────────────────────────────────────────

def _migrate_v1(db):
    """Initial schema: all tables and indexes."""
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
            tx_hash     TEXT UNIQUE,
            hidden      INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_date ON transactions(date);
        CREATE INDEX IF NOT EXISTS idx_type ON transactions(type);
        CREATE INDEX IF NOT EXISTS idx_category ON transactions(category);
        CREATE INDEX IF NOT EXISTS idx_hidden ON transactions(hidden);

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

        CREATE TABLE IF NOT EXISTS import_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            priority    INTEGER DEFAULT 0,
            enabled     INTEGER DEFAULT 1,
            action      TEXT NOT NULL CHECK(action IN ('hide','label','pass')),
            action_value TEXT,
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS rule_conditions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id     INTEGER NOT NULL REFERENCES import_rules(id) ON DELETE CASCADE,
            field       TEXT NOT NULL CHECK(field IN ('description','amount','account','type')),
            operator    TEXT NOT NULL CHECK(operator IN ('contains','not_contains','equals','not_equals','contains_any','starts_with','ends_with','greater_than','less_than')),
            value       TEXT NOT NULL
        );
    """)

# Register migrations in order. Each tuple: (version, description, function).
# To add a new migration, append to this list:
#   (2, "add foo column to transactions", _migrate_v2),
MIGRATIONS = [
    (1, "initial schema", _migrate_v1),
]

LATEST_VERSION = MIGRATIONS[-1][0]


def _get_schema_version(db):
    """Return current schema version, or 0 if version tracking doesn't exist."""
    try:
        row = db.execute("SELECT version FROM schema_version").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def _is_existing_db(db):
    """Detect a pre-migration database (has app tables but no schema_version)."""
    row = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='transactions'"
    ).fetchone()
    return row[0] > 0


def run_migrations(db):
    """Run any pending schema migrations in order."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
    )

    current = _get_schema_version(db)

    if current == 0 and _is_existing_db(db):
        # Pre-migration database — already has the v1 schema
        current = 1
        db.execute("INSERT INTO schema_version (version) VALUES (?)", (current,))
        db.commit()
    elif current == 0:
        db.execute("INSERT INTO schema_version (version) VALUES (0)")
        db.commit()

    for version, _desc, migrate_fn in MIGRATIONS:
        if version > current:
            migrate_fn(db)
            db.execute("UPDATE schema_version SET version = ?", (version,))
            db.commit()


def _fix_legacy_hashes(db):
    """Convert any leftover MD5 tx_hash values to SHA256 (runs every startup, cheap no-op)."""
    md5_rows = db.execute(
        "SELECT id, date, name, amount, account FROM transactions WHERE length(tx_hash) = 32"
    ).fetchall()
    for row in md5_rows:
        new_hash = tx_hash(row[1], row[2], row[3], row[4])
        db.execute("UPDATE transactions SET tx_hash=? WHERE id=?", (new_hash, row[0]))
    if md5_rows:
        db.commit()


def _seed_defaults(db):
    """Populate default settings and categories (only if tables are empty)."""
    db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('theme','dark')")
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
            db.execute(
                "INSERT INTO categories (name, type, icon, user_created, sort_order) VALUES (?,?,?,0,?)",
                (name, "Expense", icon, i),
            )
        for i, (name, icon) in enumerate(income_cats):
            db.execute(
                "INSERT INTO categories (name, type, icon, user_created, sort_order) VALUES (?,?,?,0,?)",
                (name, "Income", icon, i),
            )
    db.commit()


def init_db(app):
    db = sqlite3.connect(app.config["DB_PATH"])
    try:
        run_migrations(db)
        _fix_legacy_hashes(db)
        _seed_defaults(db)
    finally:
        db.close()
