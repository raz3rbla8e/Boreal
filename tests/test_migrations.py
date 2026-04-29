import os
import sqlite3
import tempfile

import pytest

from canada_finance import create_app
from canada_finance.models.database import (
    LATEST_VERSION,
    _fix_legacy_hashes,
    _get_schema_version,
    _is_existing_db,
    run_migrations,
    tx_hash,
)


@pytest.fixture()
def raw_db():
    """Provide a raw SQLite connection (no Flask app) for migration tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    db = sqlite3.connect(path)
    yield db
    db.close()
    os.close(fd)
    os.unlink(path)


@pytest.fixture()
def app_with_db(monkeypatch):
    """Create an app with a temp database and return (app, db_path)."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", db_path)
    import canada_finance.config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    import canada_finance as cf
    monkeypatch.setattr(cf, "DB_PATH", db_path)

    app = create_app()
    app.config.update({"TESTING": True})
    yield app, db_path
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


# ── Fresh database ─────────────────────────────────────────────────────────────

class TestFreshDatabase:
    def test_fresh_db_reaches_latest_version(self, raw_db):
        run_migrations(raw_db)
        assert _get_schema_version(raw_db) == LATEST_VERSION

    def test_fresh_db_creates_all_tables(self, raw_db):
        run_migrations(raw_db)
        tables = {
            row[0]
            for row in raw_db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {
            "schema_version",
            "transactions",
            "learned_merchants",
            "budgets",
            "settings",
            "categories",
            "import_rules",
            "rule_conditions",
        }
        assert expected.issubset(tables)

    def test_transactions_has_hidden_column(self, raw_db):
        run_migrations(raw_db)
        raw_db.execute("SELECT hidden FROM transactions LIMIT 0")

    def test_schema_version_table_has_one_row(self, raw_db):
        run_migrations(raw_db)
        count = raw_db.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
        assert count == 1


# ── Pre-migration database ────────────────────────────────────────────────────

class TestPreMigrationDatabase:
    def _create_pre_migration_db(self, db):
        """Simulate a database created by the old init_db (no schema_version)."""
        db.executescript("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                account TEXT NOT NULL,
                notes TEXT DEFAULT '',
                source TEXT DEFAULT 'manual',
                tx_hash TEXT UNIQUE,
                hidden INTEGER DEFAULT 0
            );
            CREATE TABLE learned_merchants (keyword TEXT PRIMARY KEY, category TEXT NOT NULL);
            CREATE TABLE budgets (category TEXT PRIMARY KEY, monthly_limit REAL NOT NULL);
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                icon TEXT DEFAULT '',
                user_created INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0
            );
            CREATE TABLE import_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                action TEXT NOT NULL,
                action_value TEXT,
                updated_at TEXT
            );
            CREATE TABLE rule_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                field TEXT NOT NULL,
                operator TEXT NOT NULL,
                value TEXT NOT NULL
            );
        """)
        db.commit()

    def test_detected_as_existing(self, raw_db):
        self._create_pre_migration_db(raw_db)
        assert _is_existing_db(raw_db) is True

    def test_empty_db_not_detected_as_existing(self, raw_db):
        assert _is_existing_db(raw_db) is False

    def test_sets_version_to_1(self, raw_db):
        self._create_pre_migration_db(raw_db)
        run_migrations(raw_db)
        assert _get_schema_version(raw_db) == 1

    def test_preserves_existing_data(self, raw_db):
        self._create_pre_migration_db(raw_db)
        raw_db.execute(
            "INSERT INTO transactions (date, type, name, category, amount, account, tx_hash) "
            "VALUES ('2026-03-01', 'Expense', 'Tim Hortons', 'Eating Out', 5.50, 'TD', 'abc123')"
        )
        raw_db.execute("INSERT INTO settings (key, value) VALUES ('theme', 'light')")
        raw_db.commit()

        run_migrations(raw_db)

        row = raw_db.execute("SELECT name FROM transactions").fetchone()
        assert row[0] == "Tim Hortons"
        theme = raw_db.execute(
            "SELECT value FROM settings WHERE key='theme'"
        ).fetchone()
        assert theme[0] == "light"


# ── Idempotency ────────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_double_init_does_not_error(self, raw_db):
        run_migrations(raw_db)
        run_migrations(raw_db)
        assert _get_schema_version(raw_db) == LATEST_VERSION

    def test_double_init_via_app(self, app_with_db):
        app, db_path = app_with_db
        with sqlite3.connect(db_path) as db:
            assert _get_schema_version(db) == LATEST_VERSION
        # Creating the app again (simulating restart) should work fine
        from canada_finance.models.database import init_db
        init_db(app)
        with sqlite3.connect(db_path) as db:
            assert _get_schema_version(db) == LATEST_VERSION


# ── Future migration simulation ───────────────────────────────────────────────

class TestFutureMigration:
    def test_new_migration_runs_on_existing_db(self, raw_db):
        run_migrations(raw_db)
        assert _get_schema_version(raw_db) == 1

        # Simulate a v2 migration that adds a column
        def _migrate_v2(db):
            db.execute("ALTER TABLE transactions ADD COLUMN label TEXT DEFAULT ''")

        from canada_finance.models import database as dbmod
        original = dbmod.MIGRATIONS[:]
        try:
            dbmod.MIGRATIONS.append((2, "add label column", _migrate_v2))
            dbmod.LATEST_VERSION = 2
            run_migrations(raw_db)
            assert _get_schema_version(raw_db) == 2
            # Verify the column exists
            raw_db.execute("SELECT label FROM transactions LIMIT 0")
        finally:
            dbmod.MIGRATIONS[:] = original
            dbmod.LATEST_VERSION = original[-1][0]

    def test_new_migration_skips_already_applied(self, raw_db):
        """A v2 migration should not run if the DB is already at v2."""
        run_migrations(raw_db)
        call_count = 0

        def _migrate_v2(db):
            nonlocal call_count
            call_count += 1
            db.execute("ALTER TABLE transactions ADD COLUMN label TEXT DEFAULT ''")

        from canada_finance.models import database as dbmod
        original = dbmod.MIGRATIONS[:]
        try:
            dbmod.MIGRATIONS.append((2, "add label column", _migrate_v2))
            dbmod.LATEST_VERSION = 2
            run_migrations(raw_db)
            assert call_count == 1
            # Run again — should NOT call _migrate_v2
            run_migrations(raw_db)
            assert call_count == 1
        finally:
            dbmod.MIGRATIONS[:] = original
            dbmod.LATEST_VERSION = original[-1][0]


# ── MD5-to-SHA256 migration ───────────────────────────────────────────────────

class TestMD5Migration:
    def test_md5_hashes_converted(self, raw_db):
        run_migrations(raw_db)
        # Insert a row with a fake 32-char MD5 hash
        raw_db.execute(
            "INSERT INTO transactions (date, type, name, category, amount, account, tx_hash, hidden) "
            "VALUES ('2026-01-01', 'Expense', 'Test', 'Misc', 10.00, 'TD', ?, 0)",
            ("a" * 32,),
        )
        raw_db.commit()
        # Run the legacy hash fix (called by init_db every startup)
        _fix_legacy_hashes(raw_db)
        row = raw_db.execute("SELECT tx_hash FROM transactions").fetchone()
        expected = tx_hash("2026-01-01", "Test", 10.00, "TD")
        assert row[0] == expected
        assert len(row[0]) == 64  # SHA256 hex length


# ── Full app integration ──────────────────────────────────────────────────────

class TestAppIntegration:
    def test_app_starts_with_correct_version(self, app_with_db):
        app, db_path = app_with_db
        with sqlite3.connect(db_path) as db:
            assert _get_schema_version(db) == LATEST_VERSION

    def test_app_seeds_default_categories(self, app_with_db):
        app, db_path = app_with_db
        with sqlite3.connect(db_path) as db:
            count = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            assert count == 26  # 21 expense + 5 income

    def test_app_seeds_default_theme(self, app_with_db):
        app, db_path = app_with_db
        with sqlite3.connect(db_path) as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key='theme'"
            ).fetchone()
            assert row[0] == "dark"
