# � Boreal

A free, private, self-hosted personal finance dashboard for Canadians. Runs locally on your laptop — your bank data never leaves your computer.

## Features

### Core
- **Import bank CSVs** — drag and drop, auto-detects your bank format
- **Import OFX/QFX files** — import directly from OFX/QFX bank downloads (common format from RBC, TD, etc.)
- **Unknown CSV wizard** — if your bank isn't recognized, a step-by-step wizard maps columns and saves the config for future imports
- **Auto-categorization** — 300+ merchant rules built in, gets smarter as you use it
- **Monthly dashboard** — income, expenses, net saved, savings rate
- **Month-over-month comparison** — see if you're spending more or less than last month
- **Year in review** — full annual breakdown with monthly bars and top 5 categories
- **Dark/light mode** — toggle in the sidebar
- **PWA support** — install as a standalone app on desktop or mobile (works offline for cached pages)

### Budgeting & Tracking
- **Budget targets** — set spending limits per category with visual progress bars and alerts
- **Monthly averages** — see your average spend per category over the last 6 months
- **Recurring/subscription detection** — automatically identifies merchants that charge you every month, flags price changes
- **Savings goals** — set targets (e.g. "Vacation Fund $3,000"), contribute manually, track progress on the dashboard
- **Category groups** — organize categories into logical groups (Essentials, Lifestyle) for grouped spending breakdowns
- **Spending trends** — 6-month bar chart showing your spending trajectory

### Accounts & Net Worth
- **Account balances** — register your bank accounts (chequing, savings, credit card, investment) with opening balances; the dashboard shows live computed balances based on all imported transactions
- **Net worth chart** — a line chart on the dashboard tracking your total net worth (sum of all account balances) over time, month by month
- **Transfers between accounts** — move money between accounts (e.g. chequing → savings); creates linked hidden transactions so balances stay accurate without polluting your spending data

### Scheduled Transactions
- **Recurring schedules** — set up transactions that repeat on a schedule (weekly, biweekly, monthly, yearly) with a name, category, amount, and account
- **Auto-post on due date** — when you open the app, due scheduled transactions are automatically posted as real transactions and the next due date advances
- **Pause/resume** — disable a schedule temporarily without deleting it (e.g. pausing a gym membership over summer)

### Transactions
- **Account filter** — filter transactions by bank account (TD, Tangerine, etc.)
- **Open search** — search "costco" and get both Costco Gas and Wholesale across all months
- **Bulk actions** — select multiple transactions and delete, categorize, or hide them all at once
- **Edit & learn** — fix a category once, it remembers forever (learned merchants)
- **Retro-fix** — when you fix a category, the app automatically re-categorizes similar UNCATEGORIZED transactions
- **Manual entries** — add cash, e-transfers, or any transaction not in a CSV
- **Undo** — accidentally delete a transaction? Click the undo button to restore it instantly (supports delete, edit, and bulk delete)
- **Transaction splitting** — split a single transaction into multiple categories

### Import & Export
- **Import rules** — create rules to auto-hide, label, or force-show transactions at import time
- **Rule templates** — one-click presets (Default, Freelancer, Student, Self-Employed, Carpool)
- **Hide/unhide transactions** — hide internal transfers or noise; view and restore hidden items
- **Custom categories** — add, rename, or delete categories with emoji icons
- **Export CSV** — export any month or all time (re-importable — full round trip)
- **Export PDF** — generate a formatted PDF report of any month's transactions
- **Backup/restore** — download your entire database as a backup, restore from a backup file

### Privacy & Cost
- **Zero cost** — no subscriptions, no cloud, no ads, no tracking
- **Fully local** — all data stays on your machine in a single SQLite file

---

## Supported Banks

| Bank | Account Type | Format | Notes |
|------|-------------|--------|-------|
| **Tangerine** | Chequing | CSV | E-transfers, memo field included |
| **Tangerine** | Credit Card | CSV | All purchases and refunds |
| **Wealthsimple** | Chequing | CSV | Auto-detects account type from CSV |
| **RBC** | Chequing | CSV | Debit/Credit columns |
| **TD** | Chequing | CSV | EasyWeb → Download Transactions → CSV |
| **CIBC** | Chequing | CSV | Account Activity → Export |
| **Scotiabank** | Chequing | CSV | Single amount column |
| **BMO** | Chequing | CSV | Withdrawals/Deposits columns |
| **National Bank** | Chequing | CSV | Bilingual (EN/FR) supported |
| **American Express** | Credit Card | CSV | Amex online statement export |
| **Any bank** | Any | OFX/QFX | Standard bank download format — works with most Canadian banks |
| **Any other bank** | Any | CSV | Use the CSV wizard to map columns — config is saved automatically |

> **OFX/QFX support:** Most Canadian banks offer OFX or QFX downloads (sometimes called "Quicken" or "Money" format). Just drag the `.ofx` or `.qfx` file into the import area — the app parses it automatically, extracts the account name, and categorizes transactions.

> **Credit cards at most banks** (TD, RBC, CIBC, BMO) are only available as PDFs — not CSVs. Tangerine is the main exception. If your bank only gives you PDFs, try a free converter like [DocuClipper](https://docuclipper.com) to get a CSV first.

---

## Setup

### Easiest: double-click to launch

1. Install [Python 3.9+](https://www.python.org/downloads/) (check "Add Python to PATH" during install)
2. Download this repo (green **Code** button → **Download ZIP**), unzip it
3. **Windows:** double-click `start.bat`
4. **Mac/Linux:** open a terminal in the folder, run `chmod +x start.sh && ./start.sh`

The app installs dependencies automatically on first launch and opens your browser.

### Manual setup

```bash
git clone https://github.com/raz3rbla8e/Boreal
cd Boreal
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

### Standalone `.exe` (no Python needed)

Download `Boreal.exe` from the [Releases](https://github.com/raz3rbla8e/Boreal/releases) page — just run it.

To build the `.exe` yourself:
```bash
pip install pyinstaller
pyinstaller canada_finance.spec
# Output: dist/Boreal.exe
```

### Docker

```bash
docker build -t boreal .
docker run -p 5000:8080 -v finance_data:/app boreal
```

### Running tests

```bash
pip install -e ".[dev]"
pytest
```

**499 tests** across 14 test files covering all endpoints, bank detection, security, new features, and edge cases.

**Environment variables** (optional — see `.env.example`):
- `SECRET_KEY` — custom session secret (auto-generated if not set)
- `DB_PATH` — custom database file path (defaults to `finance.db`)

---

## Usage

### Importing transactions

1. Log into your bank's online banking
2. Download your transactions as CSV or OFX/QFX (usually under "Account Activity" → "Export" or "Download")
3. Open **http://localhost:5000** → **Import CSV** tab
4. Drag and drop one or more CSV, OFX, or QFX files
5. Done — duplicates are automatically skipped

**You can import the same file multiple times safely.** The app uses a SHA-256 hash of date + name + amount + account to deduplicate — it will never double-count.

**Unknown banks?** If the CSV format isn't recognized, a wizard opens automatically. You map the date, description, and amount columns, name the bank, preview the parsed data, and save. A YAML config is created in `banks/` and future imports auto-detect.

**Re-importing your own exports?** If you export a CSV from Boreal and re-import it (or share it with a friend), the app recognizes its own format and preserves all categories, types, and account names.

### Monthly routine

```
1. Download CSVs from each bank
2. Drag into Import CSV tab
3. Check dashboard for the new month
4. Fix any UNCATEGORIZED transactions by clicking them
```

### Fixing categories

Click any transaction row → Edit modal → Change category → Save.

The merchant name is saved to your `learned_merchants` database. Next time that merchant appears in a CSV, it's auto-categorized correctly. The app also retro-fixes any other UNCATEGORIZED transactions that match.

You can manage or delete learned merchants in **Settings → Learned Merchants**.

### Bulk actions

In the **Transactions** tab, use the checkboxes to select multiple transactions, then:
- **Categorize** — assign the same category to all selected
- **Hide** — hide selected transactions from your dashboard
- **Delete** — remove selected transactions permanently

### Manual transactions

Click **Add Transaction** in the sidebar for:
- Cash purchases
- E-transfers (e.g. car payment to family)
- Any expense not captured by a bank CSV

### Setting budgets

Go to **Settings → Monthly Budgets** → pick a category and set your limit. Progress bars appear on the dashboard showing how close you are (green → amber → red).

### Recurring & subscriptions

The dashboard automatically detects merchants that charge you in 3 or more distinct months (Netflix, Spotify, gym membership, etc.) and shows:
- Average monthly amount
- Total monthly committed spend
- Price change warnings (e.g. Netflix went from $16.49 to $17.99)

### Import rules

Go to **Settings → Import Rules** to create rules that run automatically on every CSV import:

- **Hide** — suppress internal transfers, credit card payments, etc. from your dashboard
- **Label** — auto-tag matching transactions with a specific type/category (e.g. label all Interac e-transfers from a specific person as Income / Freelance)
- **Pass** — force-show transactions that would otherwise be hidden by another rule

Rules have conditions (description contains, amount greater than, etc.) and first match wins by priority. You can test rules against your existing data before saving.

**Templates:** One-click presets for common setups — Default, Freelancer, Student, Self-Employed, Carpool/Commuter. Load a template and customize.

### Hidden transactions

Transactions hidden by rules (or manually) don't affect your dashboard numbers. View them from the **Transactions** tab → **Hidden** toggle. You can unhide any transaction to restore it.

### Custom categories

In **Settings → Categories**, you can:
- Add new expense or income categories with emoji icons
- Rename existing categories (all transactions are updated automatically)
- Delete categories (with option to reassign transactions to another category)

### Year in review

Switch to the **Year Review** tab to see:
- Total income, expenses, and net saved for the year
- Monthly bar chart comparing income vs. expenses
- Top 5 spending categories for the year

### Backup & restore

- **Backup:** Settings → Download Backup (downloads your `finance.db` file with a timestamp)
- **Restore:** Settings → Restore from Backup (upload a `.db` file to overwrite your current data)
- **Export CSV:** Export tab → download all transactions as CSV (can be re-imported)

### Accounts & balances

The **Accounts** feature lets you register the actual bank accounts you use (chequing, savings, credit card, investment) and track their balances over time.

**How it works:**
1. Go to **Settings → Accounts**
2. Add each account with a name (e.g. "TD Chequing"), type, and opening balance (your balance before any imported transactions)
3. The app computes each account's live balance: `opening balance + all income − all expenses` for that account
4. The **Account Balances** panel on the dashboard shows each account's current balance and a total across all accounts

**Why it's useful:** Without accounts, Boreal just shows spending and income in aggregate. With accounts, you can see _where_ your money actually sits — how much is in chequing vs. savings vs. investments. It turns the app from a spending tracker into a full financial picture.

When you rename an account in Settings, all transactions linked to it are updated automatically.

### Net worth

The **Net Worth** panel on the dashboard shows a line chart of your total net worth over time.

**How it works:**
- Net worth = sum of all account balances at each month-end
- Each account's balance at a given month = `opening balance + income up to that month − expenses up to that month`
- The chart plots one data point per month, so you can see your net worth grow (or shrink) over time

**Why it's useful:** Month-to-month spending is important, but the bigger question is: _am I building wealth?_ The net worth chart answers that. If you're saving $500/month but your net worth is flat, something's off. If it's trending up, you're on track.

> You need at least one account set up (in Settings → Accounts) for net worth to appear.

### Scheduled transactions

**Scheduled transactions** let you pre-define recurring expenses or income that happen on a predictable schedule.

**How it works:**
1. Go to **Settings → Scheduled Transactions**
2. Add a schedule: name, type (Expense/Income), category, amount, account, frequency (weekly/biweekly/monthly/yearly), and next due date
3. When you open the app and a schedule is due, it's automatically posted as a real transaction and the next due date advances
4. You can also manually post all due schedules by clicking **⚡ Post due now**
5. Pause a schedule (⏸ button) to skip it temporarily — useful for seasonal expenses

**Why it's useful:** Rent, Netflix, gym membership, car payment — these happen every month like clockwork. Instead of waiting for them to appear in a CSV (which might be delayed), scheduled transactions let you:
- See upcoming expenses _before_ they hit your bank
- Keep your budget accurate even if you haven't imported this month's CSV yet
- Auto-categorize recurring expenses perfectly every time (no more UNCATEGORIZED rent)

### Transfers

Click **Transfer** in the sidebar to move money between accounts (e.g. chequing → savings).

**How it works:**
- A transfer creates two linked hidden transactions: an expense from the source account and income to the destination account
- Both are hidden from your dashboard so they don't inflate your spending or income numbers
- Account balances update correctly — the money moves from one account to the other
- The transactions are linked by a `transfer_id` so the app knows they're a pair

**Why it's useful:** When you move $500 from chequing to savings, that's not spending — it's just moving your own money. Without transfers, you'd either have to manually add two transactions and hide them, or your account balances would be wrong. Transfers handle this in one click.

### Undo

When you delete a transaction (single or bulk), an **Undo** button appears at the bottom-right of the screen. Click it to restore the deleted transaction(s) instantly.

Undo also works for edits — if you change a transaction's name or category, undo reverts it to the previous values.

The undo history keeps the last 50 actions and each undo is consumed after use (you can't undo the same action twice).

---

## Data & Privacy

- All data is stored in `finance.db` — a local SQLite file on your machine
- Nothing is sent to any server, ever
- The only external request is loading Google Fonts and Chart.js from CDNs (for the UI)
- Session tokens use SHA-256 and are auto-generated per install
- CSRF protection on all mutating API endpoints
- To back up your data: use the in-app backup, or copy `finance.db` somewhere safe
- To start fresh: delete `finance.db` and restart the app

---

## File Structure

```
Boreal/
├── app.py                          ← Entry point
├── pyproject.toml                  ← Package config and dependencies
├── requirements.txt                ← Pip dependencies
├── start.bat                       ← Windows launcher (auto-installs deps)
├── start.sh                        ← Mac/Linux launcher
├── canada_finance.spec             ← PyInstaller build config
├── Dockerfile                      ← Docker container config
├── .env.example                    ← Environment variable reference
├── banks/                          ← YAML bank configs (auto-detect CSV formats)
│   ├── amex.yaml
│   ├── bmo_chequing.yaml
│   ├── canada_finance_export.yaml  ← Recognizes re-imported exports
│   ├── cibc_chequing.yaml
│   ├── national_bank.yaml
│   ├── rbc_chequing.yaml
│   ├── scotiabank.yaml
│   ├── tangerine_credit.yaml
│   ├── tangerine_debit.yaml
│   ├── td_chequing.yaml
│   └── wealthsimple.yaml
├── rules/templates/                ← Import rule presets
│   ├── default.yaml
│   ├── freelancer.yaml
│   ├── student.yaml
│   ├── self_employed.yaml
│   └── carpool_commuter.yaml
├── canada_finance/                 ← Application package
│   ├── __init__.py                 ← Flask app factory, CSRF middleware
│   ├── __main__.py                 ← python -m canada_finance
│   ├── config.py                   ← Paths and config constants
│   ├── models/
│   │   └── database.py             ← SQLite schema, init, tx_hash, migrations
│   ├── routes/
│   │   ├── __init__.py             ← Blueprint registration
│   │   ├── main.py                 ← Homepage, health check
│   │   ├── transactions.py         ← CRUD, search, pagination, bulk actions, undo
│   │   ├── import_export.py        ← CSV/OFX import, export, bank wizard, backup/restore
│   │   ├── summary.py              ← Dashboard, year review, averages, recurring detection
│   │   ├── settings.py             ← Budgets, categories, learned merchants
│   │   ├── rules.py                ← Import rules CRUD, templates, test/apply
│   │   └── accounts.py             ← Accounts, net worth, scheduled transactions, transfers, undo
│   ├── services/
│   │   ├── categorization.py       ← 300+ keyword → category mapping
│   │   ├── csv_parser.py           ← YAML-driven CSV parsing engine
│   │   ├── helpers.py              ← Date parsing, number parsing
│   │   └── rules_engine.py         ← Rule evaluation and transaction saving
│   ├── templates/
│   │   └── index.html              ← Single-page HTML shell
│   └── static/
│       ├── css/style.css           ← Full app styling (dark/light themes)
│       ├── js/app.js               ← Frontend logic (~2000 lines, vanilla JS)
│       ├── manifest.json           ← PWA manifest for installability
│       ├── sw.js                   ← Service worker for offline caching
│       └── icons/                  ← PWA icons (192px, 512px)
├── tests/                          ← 499 tests across 14 files
│   ├── conftest.py                 ← Fixtures, helpers, sample CSV data
│   ├── test_bank_detection.py      ← Bank YAML detection (10 banks + cross-check)
│   ├── test_categories.py          ← Category CRUD and cascading
│   ├── test_demo.py                ← Demo mode and reset
│   ├── test_import_export.py       ← Import, export, round-trip, backup/restore
│   ├── test_migrations.py          ← Database migration system (v1–v8)
│   ├── test_mobile.py              ← Mobile responsiveness
│   ├── test_new_features_v2.py     ← Accounts, net worth, schedules, transfers, undo, OFX, PWA
│   ├── test_new_features.py        ← Progressive features
│   ├── test_progressive_disclosure.py ← Progressive disclosure tests
│   ├── test_rules.py               ← Import rules CRUD and evaluation
│   ├── test_security.py            ← CSRF, path traversal, input validation
│   ├── test_settings.py            ← Budgets, learned merchants, goals, groups
│   ├── test_summary.py             ← Summary, year, averages, recurring
│   └── test_transactions.py        ← CRUD, search, bulk actions, account filter
└── finance.db                      ← Your data (auto-created, gitignored)
```

---

## Adding a new bank

### Option 1: Use the CSV wizard (no code needed)

Drop an unrecognized CSV into the import tab → the wizard opens → map columns → name the bank → save. A YAML config is created in `banks/` and future imports auto-detect.

### Option 2: Write a YAML config manually

Create a file in `banks/` following this pattern:

```yaml
name: "My Bank (Chequing)"
version: 1
last_verified: "2026-04"
account_label: "My Bank Chequing"
encoding: "utf-8-sig"

detection:
  header_contains:
    - "some_unique_header"

columns:
  date: "Date"
  description: "Description"
  debit: "Withdrawals"
  credit: "Deposits"

date_formats:
  - "%m/%d/%Y"
  - "%Y-%m-%d"
```

See existing configs in `banks/` for examples of single-amount vs. debit/credit, flexible column matching, memo fields, description fallbacks, etc.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/months` | List months with data |
| GET | `/api/summary?month=` | Monthly dashboard data |
| GET | `/api/year/<year>` | Year in review |
| GET | `/api/averages` | Monthly category averages |
| GET | `/api/recurring` | Recurring transaction detection |
| GET | `/api/transactions` | List/filter/search transactions |
| GET | `/api/accounts` | List distinct bank accounts |
| POST | `/api/add` | Add a manual transaction |
| PATCH | `/api/update/<id>` | Update a transaction |
| DELETE | `/api/delete/<id>` | Delete a transaction |
| PATCH | `/api/transactions/<id>/hide` | Hide a transaction |
| PATCH | `/api/transactions/<id>/unhide` | Unhide a transaction |
| POST | `/api/bulk-delete` | Delete multiple transactions |
| POST | `/api/bulk-categorize` | Categorize multiple transactions |
| POST | `/api/bulk-hide` | Hide multiple transactions |
| POST | `/api/import` | Import CSV files |
| POST | `/api/detect-csv` | Detect bank from CSV header |
| POST | `/api/save-bank-config` | Save custom bank config |
| POST | `/api/preview-parse` | Preview CSV parsing |
| GET | `/api/export` | Export transactions as CSV |
| GET | `/api/backup` | Download database backup |
| POST | `/api/restore` | Restore from backup |
| GET/POST | `/api/budgets` | Get/set budget limits |
| GET/POST | `/api/settings` | Get/set app settings |
| GET | `/api/categories` | List categories |
| POST | `/api/categories` | Add category |
| PATCH | `/api/categories/<id>` | Rename category |
| DELETE | `/api/categories/<id>` | Delete category |
| GET | `/api/learned` | List learned merchants |
| DELETE | `/api/learned/<keyword>` | Delete learned merchant |
| GET/POST | `/api/rules` | Get/create import rules |
| PATCH | `/api/rules/<id>` | Update rule |
| DELETE | `/api/rules/<id>` | Delete rule |
| POST | `/api/rules/reorder` | Reorder rule priorities |
| POST | `/api/rules/test` | Test rule against existing data |
| POST | `/api/rules/apply-all` | Apply all rules retroactively |
| GET | `/api/rule-templates` | List rule templates |
| POST | `/api/rule-templates/load` | Load a rule template |
| GET | `/api/accounts-list` | List accounts with balances |
| POST | `/api/accounts-list` | Add an account |
| PATCH | `/api/accounts-list/<id>` | Update an account |
| DELETE | `/api/accounts-list/<id>` | Delete an account |
| GET | `/api/net-worth` | Net worth over time |
| GET | `/api/schedules` | List scheduled transactions |
| POST | `/api/schedules` | Add a scheduled transaction |
| PATCH | `/api/schedules/<id>` | Update a scheduled transaction |
| DELETE | `/api/schedules/<id>` | Delete a scheduled transaction |
| POST | `/api/schedules/post-due` | Post all due scheduled transactions |
| POST | `/api/transfers` | Create a transfer between accounts |
| POST | `/api/undo` | Undo the last delete/edit |
| GET | `/api/undo/status` | Check if undo is available |
| POST | `/api/import-ofx` | Import OFX/QFX files |

---

## Tech Stack

- **Backend:** Python 3.9+ / Flask 3.0+
- **Database:** SQLite (zero config, single file, 8 migration versions)
- **Frontend:** Vanilla HTML/CSS/JS — no build step, no npm, no framework
- **Charts:** Chart.js 4.4.0 (loaded from CDN) — doughnut, bar, and line charts
- **PDF:** fpdf2 for PDF report generation
- **Bank configs:** YAML files — easy to add/modify
- **PWA:** Service worker + manifest for installability and offline support
- **Security:** CSRF protection, SHA-256 hashing, path traversal guards, input validation
- **Tests:** pytest — 499 tests, 14 files, covers every endpoint and feature
- **Total install size:** ~2 MB

---

## Contributing

Issues and PRs welcome. Please don't commit any real transaction data.

To run tests:
```bash
pip install -e ".[dev]"
pytest -v
```

---

## License

MIT
