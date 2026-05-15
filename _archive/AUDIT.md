# Boreal — Complete Codebase Audit

Every file in the repository has been read end-to-end. Below is the full catalog of findings.

---

## 1. File Inventory

| File | ~Lines | Purpose |
|------|--------|---------|
| `app.py` | 20 | Entry point |
| `canada_finance/__init__.py` | 160 | App factory, CSRF, demo guard |
| `canada_finance/__main__.py` | 7 | Module entry point |
| `canada_finance/config.py` | 11 | Path constants |
| `canada_finance/models/database.py` | 300 | SQLite schema, 8 migrations, seeding |
| `canada_finance/routes/transactions.py` | 340 | Transaction CRUD, bulk ops, search |
| `canada_finance/routes/import_export.py` | 430 | CSV/OFX import, export, backup/restore |
| `canada_finance/routes/summary.py` | 170 | Dashboard summary, year review, trends |
| `canada_finance/routes/settings.py` | 330 | Categories, budgets, goals, groups |
| `canada_finance/routes/rules.py` | 250 | Import rules CRUD, templates |
| `canada_finance/routes/accounts.py` | 350 | Accounts, net worth, schedules, transfers, undo |
| `canada_finance/routes/main.py` | ~20 | Index, health, CSRF token routes |
| `canada_finance/services/categorization.py` | 200 | 300+ keyword rules, priority matching |
| `canada_finance/services/csv_parser.py` | 250 | Bank config loading, CSV parsing |
| `canada_finance/services/helpers.py` | 35 | Date parsing, float sanitization |
| `canada_finance/services/rules_engine.py` | 130 | Rule evaluation and application |
| `canada_finance/templates/index.html` | 1050 | Single-page HTML shell, all modals |
| `canada_finance/templates/icon_compare.html` | ~small | Icon comparison page |
| `canada_finance/static/js/app.js` | 2300 | All client-side logic |
| `canada_finance/static/css/style.css` | 1200 | Full styling, themes, responsive |
| `canada_finance/static/manifest.json` | 20 | PWA manifest |
| `canada_finance/static/sw.js` | 35 | Service worker |
| `pyproject.toml` | 35 | Package config |
| `requirements.txt` | 4 | Pip dependencies |
| `Dockerfile` | 12 | Docker build |
| `README.md` | ~250 | Documentation |
| `start.bat` / `start.sh` | 40/45 | Launch scripts |
| `banks/*.yaml` (11 files) | ~20 each | Bank detection configs |
| `rules/templates/*.yaml` (5 files) | ~20 each | Rule presets |
| `tests/*.py` (14 files) | ~3500 total | Test suite |
| `sample_data/*.csv` (6 files) | — | Sample bank CSVs |

---

## 2. Bugs & Inconsistencies

### 2.1 Broken Emoji in Terminal Output
**Files:** `app.py` line 18, `canada_finance/__init__.py` `main()` function  
The print statements use an emoji that renders as `�` in many terminals:
```python
print("\n🌲 Boreal ...")  # may display as \n� Boreal
```
**Fix:** Use ASCII art or check terminal encoding before printing emoji.

### 2.2 CSS Escaped Quotes + Literal `\n`
**File:** `canada_finance/static/css/style.css` line 67  
```css
}\n[data-theme=\"light\"] .logo-mark { background: oklch(92% 0.02 240); }
```
This line contains a literal `\n` (backslash-n) instead of a real newline, and uses JavaScript-style escaped quotes `\"` which are invalid in CSS. Should be:
```css
}
[data-theme="light"] .logo-mark { background: oklch(92% 0.02 240); }
```

### 2.3 Theme Color Mismatch (PWA)
**File:** `canada_finance/static/manifest.json` has `"theme_color": "#6ee7b7"` (mint green)  
**File:** `canada_finance/templates/index.html` has `<meta name="theme-color" content="#3b82f6">` (blue)  
These should match.

### 2.4 Google Fonts Loaded Twice
**File:** `canada_finance/static/css/style.css` line 1 — `@import url(https://fonts.googleapis.com/css2?...)`  
**File:** `canada_finance/templates/index.html` — `<link href="https://fonts.googleapis.com/css2?...">` in `<head>`  
The font is loaded twice. Remove one (prefer the HTML `<link>` for render performance).

### 2.5 Dockerfile Port Mismatch
**File:** `Dockerfile` — `EXPOSE 8080` and CMD runs gunicorn on port 8080  
**File:** `app.py` — defaults to `port=5000`  
**File:** `README.md` Docker section — `docker run -p 5000:5000`  
The README maps port 5000 but the container listens on 8080. Should be `docker run -p 5000:8080`.

### 2.6 Duplicate Pip Install in Dockerfile
**File:** `Dockerfile`  
Runs both `pip install -r requirements.txt` AND `pip install .` — the latter already handles dependencies from `pyproject.toml`. One is redundant (though `pyproject.toml` is missing some deps — see 2.7).

### 2.7 Dependency Mismatch: pyproject.toml vs requirements.txt
**File:** `pyproject.toml` dependencies: `flask>=3.0.0`, `pyyaml>=6.0`  
**File:** `requirements.txt`: `flask>=3.0.0`, `gunicorn>=22.0.0`, `pyyaml>=6.0`, `fpdf2>=2.7.0`  
**Missing from pyproject.toml:** `gunicorn` and `fpdf2`. PDF export will crash if installed only via `pip install .`

### 2.8 Hardcoded Account Options in Add Transaction Modal
**File:** `canada_finance/templates/index.html` — the "Add Transaction" modal has a hardcoded `<select>` with account names (Tangerine, Wealthsimple, RBC, TD, etc.) instead of dynamically populating from the user's registered accounts via API. The Transfer modal correctly fetches accounts from `/api/accounts`, but the Add modal does not.

### 2.9 Monthly Advance Loses Day Precision
**Files:** `canada_finance/models/database.py`, `canada_finance/routes/accounts.py`  
Scheduled transactions use `min(d.day, 28)` when advancing monthly. A bill due on the 31st will permanently shift to the 28th after first advance, never returning to the 31st even in months that have 31 days.

### 2.10 `resetDemo()` Bypasses CSRF
**File:** `canada_finance/static/js/app.js`  
The `resetDemo()` function uses raw `fetch()` instead of the app's `apiFetch()` wrapper. While it does manually attach the CSRF token header, it's inconsistent and bypasses the centralized error handling.

### 2.11 No-Op Functions Left in JS
**File:** `canada_finance/static/js/app.js`  
Three empty functions exist from removed features:
```javascript
function openExportModal(preselect) {}
function onExportFormatChange() {}
function doExport() {}
function toggleQuickActions(e) {}
function closeQuickActions() {}
function toggleMonthMenu(e) {}
function closeMonthMenu() {}
```
These are dead code. They should be removed.

### 2.12 Service Worker Cache Never Updated
**File:** `canada_finance/static/sw.js`  
Cache name is hardcoded as `'boreal-v1'` and never changes. App updates won't bust the cache. The SW also doesn't cache CDN resources (Google Fonts, Chart.js) which it relies on.

---

## 3. Code Style Issues

### 3.1 Inconsistent Entry Points
Three different ways to start the app exist:
- `python app.py` — uses `app.py`
- `python -m canada_finance` — uses `__main__.py` → calls `main()`
- `canada-finance` CLI — uses entry point in `pyproject.toml` → calls `main()`

`app.py` and `__main__.py` both duplicate the startup logic.

### 3.2 switchSettingsTab Is a No-Op
**File:** `canada_finance/static/js/app.js`  
```javascript
function switchSettingsTab(tabName) {
  // Settings tabs removed — flat layout now; no-op for backward compatibility
}
```
This can be removed along with any calls to it.

### 3.3 Broad Exception Swallowing
**File:** `canada_finance/services/csv_parser.py`  
```python
except Exception:
    continue
```
In the row-parsing loop, any exception is silently swallowed. Malformed rows disappear without warning. At minimum, these should be counted and reported to the user.

### 3.4 Connection Management in rules_engine.py
**File:** `canada_finance/services/rules_engine.py`  
`load_enabled_rules()` and `save_transactions()` open standalone SQLite connections when called outside Flask context. These connections may not be properly closed in all code paths, risking connection leaks.

---

## 4. Security Assessment

### What's Good
- **CSRF protection** — Token-based validation on all mutating endpoints. Tests verify it works.
- **SQL injection** — Parameterized queries used consistently throughout. Dynamic query construction in `transactions.py` uses `f"IN ({placeholders})"` but values are always parameterized.
- **XSS** — Server stores raw data, client uses `escapeHtml()`/`escapeAttr()` for all dynamic content rendering. This is a documented design decision with test coverage.
- **Path traversal** — Rule template loading validates with `os.path.realpath()` to prevent directory escape.
- **Secret key** — Auto-generated with `secrets.token_hex(32)`, persisted to `.secret_key` file. Supports `SECRET_KEY` env var override.
- **File upload** — 16 MB limit enforced. Backup restore validates SQLite file header bytes.
- **Hash algorithm** — SHA-256 for transaction deduplication. Legacy MD5 hashes auto-migrated on startup.

### Concerns

| # | Issue | Severity |
|---|-------|----------|
| 4.1 | **No authentication** — the app has zero auth. By design it's local-only, but if the Docker container is exposed to a network, anyone can read/modify all financial data. | Medium |
| 4.2 | **No rate limiting** — API endpoints have no throttling. If exposed, could be abused. | Low |
| 4.3 | **Backup downloads entire DB into memory** — `api_backup()` reads the full SQLite file with `open(db_path,'rb').read()`. For very large databases this could cause OOM. | Low |
| 4.4 | **Restore race condition** — `api_restore()` closes the current DB connection then overwrites the file. Concurrent requests could hit a broken state. | Low |
| 4.5 | **Demo timer recursive threading** — `_start_demo_reset_timer` creates a new `threading.Timer` recursively every 30 min. Over days of uptime, this is fine, but there's no explicit cleanup on app shutdown. | Low |

---

## 5. UX Issues

### 5.1 Hardcoded Account Dropdown
The "Add Transaction" modal has a fixed list of Canadian banks instead of showing the user's actual registered accounts. The Transfer modal dynamically loads accounts — the Add modal should do the same.

### 5.2 No Account Edit in Settings
The Accounts settings section shows a delete button per account but no edit/rename button in the UI (though the API supports PATCH). Users must delete and recreate to rename.

### 5.3 Category Group Assignment Not in UI
Category groups exist (backend migration v4 creates them, API supports CRUD), but there's no UI to assign/reassign individual categories to groups. The groups are pre-assigned in the migration and can only be managed by adding/deleting entire groups.

### 5.4 Scheduled Transactions Missing Account Selector
When adding a scheduled transaction in Settings, the JS picks the first account from the API or falls back to "Default". There's no `<select>` for the user to choose which account.

### 5.5 oklch() Browser Compatibility
The entire color system uses `oklch()` which isn't supported in older browsers (Safari <15.4, Chrome <111). There are no fallback values. Users on older browsers see no colors at all.

---

## 6. Missing Error Handling

| Location | Issue |
|----------|-------|
| `csv_parser.py` row parsing | `except Exception: continue` — silently drops rows |
| `rules_engine.py` standalone connections | No guarantee connections close on error paths |
| `api_year()` in `summary.py` | 24 separate DB queries with no try/except — one failure crashes the whole endpoint |
| `api_backup()` | No handling for DB file being locked/inaccessible |
| JS `init()` function | Multiple parallel `await` calls — if one fails, others may still run against stale state |

---

## 7. Performance Concerns

| Location | Issue |
|----------|-------|
| `api_year()` | 24 separate DB queries (2 per month x 12). Could be 2 queries with `GROUP BY`. |
| `api_rules_test()` and `api_rules_apply_all()` | Load ALL transactions into memory. O(n) for every test/apply. |
| `api_bulk_categorize()` retro-fix | For each selected transaction, queries ALL transactions to find similar ones. O(n²) worst case. |
| Account balance computation | Multiple queries per account (separate income/expense sums). Could be one query with CASE. |
| Net worth endpoint | Multiple queries per account per month — O(accounts × months). |

---

## 8. README vs Reality

| README Claim | Reality | Status |
|--------------|---------|--------|
| "389 tests across 13 test files" | **440 tests** across **14 test files** (grep counts `def test_` occurrences) | **Outdated** — more tests than claimed |
| `.env.example` referenced | File exists | **Correct** |
| `docker run -p 5000:5000` | Container `EXPOSE 8080`, gunicorn binds to `0.0.0.0:8080` | **Wrong** — should be `-p 5000:8080` |
| Feature descriptions | All features described are implemented and functional | **Correct** |
| Bank support table | All 11 banks have YAML configs, all detected correctly | **Correct** |
| Entry point `python app.py` | Works, also `python -m canada_finance` and `canada-finance` CLI | **Correct** |
| Project name "Boreal" | `pyproject.toml` names it "boreal" but CLI entry point is `canada-finance` | **Inconsistent** |

---

## 9. Test Coverage Gaps

The test suite is strong (440 tests), but the following areas have no coverage:

| Gap | Risk |
|-----|------|
| Net worth with credit card accounts (negative balances) | Balance math could be wrong for credit accounts |
| Unicode characters in category/account names | Emoji icons in category names are a feature but untested |
| Concurrent database access | SQLite locking under simultaneous requests |
| `icon_compare.html` route | Route exists but no test hits it |
| End-to-end import → categorize → dashboard summary flow | Individual pieces tested but not the full flow |
| Service worker behavior | No tests for offline caching strategy |
| CSV wizard end-to-end via API | Wizard preview/save tested individually but not the full wizard flow |
| Scheduled transaction yearly/biweekly frequency advance | Only weekly and monthly are tested |
| Large dataset performance | No load tests for any endpoint |
| `_fix_legacy_hashes` in database.py | MD5→SHA256 migration tested in test_security but edge cases (empty DB, partial migration) not covered |
| `api_export_pdf()` with various data shapes | PDF generation tested once but not with edge cases (empty month, huge transaction list) |

---

## 10. TODO/FIXME/HACK Comments

**None found.** The codebase is clean of marker comments.

---

## 11. Summary of Actionable Items

### Priority: High (should fix)
1. Fix CSS escaped quotes + literal `\n` on line 67 of `style.css`
2. Fix Dockerfile port mapping documentation in README (`-p 5000:8080`)
3. Add `fpdf2` and `gunicorn` to `pyproject.toml` dependencies
4. Make "Add Transaction" account dropdown dynamic (match Transfer modal pattern)

### Priority: Medium (should improve)
5. Fix theme-color mismatch between `manifest.json` and `index.html`
6. Remove duplicate Google Fonts loading (drop the CSS `@import`)
7. Remove 7 dead no-op functions from `app.js`
8. Replace broad `except Exception: continue` in `csv_parser.py` with error counting
9. Update README test count (440 tests, 14 files)
10. Version the service worker cache name
11. Fix monthly advance to preserve original day-of-month

### Priority: Low (nice to have)
12. Add oklch() fallback values for older browsers
13. Optimize `api_year()` to 2 queries instead of 24
14. Add account selector to scheduled transaction UI
15. Add edit button for accounts in settings
16. Add UI for reassigning categories to groups
17. Remove `switchSettingsTab` no-op function
18. Consolidate the 3 entry points (app.py, __main__.py, main())
19. Add authentication option for non-local deployments
20. Fix Docker double `pip install` redundancy
