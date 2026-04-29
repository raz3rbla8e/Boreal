# 🍁 CanadaFinance

A free, private, self-hosted personal finance dashboard for Canadians. Runs locally on your laptop — your bank data never leaves your computer.

## Features

- **Import bank CSVs** — drag and drop, auto-detects your bank format
- **Unknown CSV wizard** — if your bank isn't recognized, a step-by-step wizard maps columns and saves the config for future imports
- **Auto-categorization** — 300+ merchant rules built in, gets smarter as you use it
- **Monthly dashboard** — income, expenses, net saved, savings rate
- **Month-over-month comparison** — see if you're spending more or less than last month
- **Budget targets** — set spending limits per category with visual progress bars
- **Monthly averages** — see your average spend per category over the last 6 months
- **Year in review** — full annual breakdown with monthly bars and top 5 categories
- **Open search** — search "costco" and get both Costco Gas and Wholesale across all months
- **Edit & learn** — fix a category once, it remembers forever (learned merchants)
- **Retro-fix** — when you fix a category, the app automatically re-categorizes similar UNCATEGORIZED transactions
- **Manual entries** — add cash, e-transfers, or any transaction not in a CSV
- **Import rules** — create rules to auto-hide, label, or force-show transactions at import time
- **Rule templates** — one-click presets (Default, Freelancer, Student, Self-Employed, Carpool)
- **Hide/unhide transactions** — hide internal transfers or noise; view and restore hidden items
- **Custom categories** — add, rename, or delete categories with emoji icons
- **Export CSV** — export any month or all time
- **Dark/light mode** — toggle in the sidebar
- **Zero cost** — no subscriptions, no cloud, no ads, no tracking

---

## Supported Banks

| Bank | Account Type | CSV Available | Notes |
|------|-------------|---------------|-------|
| **Tangerine** | Chequing | ✅ | E-transfers, memo field included |
| **Tangerine** | Credit Card | ✅ | All purchases and refunds |
| **Wealthsimple** | Chequing | ✅ | Auto-detects account type from CSV |
| **RBC** | Chequing | ✅ | Debit/Credit columns |
| **TD** | Chequing | ✅ | EasyWeb → Download Transactions → CSV |
| **CIBC** | Chequing | ✅ | Account Activity → Export |
| **Scotiabank** | Chequing | ✅ | Single amount column |
| **BMO** | Chequing | ✅ | Withdrawals/Deposits columns |
| **National Bank** | Chequing | ✅ | Bilingual (EN/FR) supported |
| **Any other bank** | Any | ✅ | Use the CSV wizard to map columns — config is saved automatically |

> **Credit cards at most banks** (TD, RBC, CIBC, BMO) are only available as PDFs — not CSVs. Tangerine is the main exception. If your bank only gives you PDFs, try a free converter like [DocuClipper](https://docuclipper.com) to get a CSV first.

---

## Setup

**Requirements:** Python 3.9+

```bash
# 1. Clone or download this repo
git clone https://github.com/raz3rbla8e/Canada_finanace
cd Canada_finanace

# 2. Install
pip install -r requirements.txt

# 3. Run
python app.py

# 4. Open in browser
# http://localhost:5000
```

That's it. A `finance.db` file is created automatically on first run.

**Alternative installs:**
- `pip install .` — full package install (adds the `canada-finance` CLI command)
- `pip install -e .` — editable/dev mode (changes take effect immediately)

**Docker:**
```bash
docker build -t canada-finance .
docker run -p 5000:5000 -v finance_data:/app canada-finance
```

**Running tests:**
```bash
pip install -e ".[dev]"
pytest
```

**Environment variables** (optional — see `.env.example`):
- `SECRET_KEY` — custom session secret (auto-generated if not set)
- `DB_PATH` — custom database file path (defaults to `finance.db`)

---

## Usage

### Importing transactions

1. Log into your bank's online banking
2. Download your transactions as CSV (usually under "Account Activity" → "Export" or "Download")
3. Open **http://localhost:5000** → **Import CSV** tab
4. Drag and drop one or more CSV files
5. Done — duplicates are automatically skipped

**You can import the same file multiple times safely.** The app uses a hash of date + name + amount + account to deduplicate — it will never double-count.

**Unknown banks?** If the CSV format isn't recognized, a wizard opens automatically. You map the date, description, and amount columns, name the bank, preview the parsed data, and save. Future imports from that bank are auto-detected.

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

### Manual transactions

Click **Add Transaction** in the sidebar for:
- Cash purchases
- E-transfers (e.g. car payment to family)
- Any expense not captured by a bank CSV

### Setting budgets

Go to **Settings → Monthly Budgets** → pick a category and set your limit. Progress bars appear on the dashboard showing how close you are (green → amber → red).

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

---

## Data & Privacy

- All data is stored in `finance.db` — a local SQLite file on your machine
- Nothing is sent to any server, ever
- The only external request is loading Google Fonts and Chart.js from CDNs (for the UI)
- To back up your data: copy `finance.db` somewhere safe
- To start fresh: delete `finance.db` and restart the app

---

## File Structure

```
canadafinance/
├── app.py                          ← Entry point
├── pyproject.toml                  ← Package config (dependencies)
├── banks/                          ← YAML bank configs (auto-detect CSV formats)
│   ├── tangerine_debit.yaml
│   ├── tangerine_credit.yaml
│   ├── wealthsimple.yaml
│   ├── td_chequing.yaml
│   ├── rbc_chequing.yaml
│   ├── cibc_chequing.yaml
│   ├── scotiabank.yaml
│   ├── bmo_chequing.yaml
│   └── national_bank.yaml
├── rules/templates/                ← Rule template presets
│   ├── default.yaml
│   ├── freelancer.yaml
│   ├── student.yaml
│   ├── self_employed.yaml
│   └── carpool_commuter.yaml
├── canada_finance/                 ← App package
│   ├── __init__.py                 ← Flask app factory
│   ├── config.py                   ← Paths and config
│   ├── models/database.py          ← SQLite schema, helpers
│   ├── routes/                     ← API endpoints
│   │   ├── main.py                 ← Homepage
│   │   ├── transactions.py         ← CRUD, search, hide/unhide
│   │   ├── import_export.py        ← CSV import, export, bank wizard
│   │   ├── summary.py              ← Dashboard, year review, averages
│   │   ├── settings.py             ← Budgets, categories, learned, settings
│   │   └── rules.py                ← Import rules, templates
│   ├── services/                   ← Business logic
│   │   ├── categorization.py       ← 300+ keyword → category rules
│   │   ├── csv_parser.py           ← YAML-driven CSV parsing
│   │   ├── helpers.py              ← Date parsing, number parsing
│   │   └── rules_engine.py         ← Rule evaluation and application
│   ├── templates/index.html        ← Single-page frontend
│   └── static/
│       ├── css/style.css
│       └── js/app.js
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

## Tech Stack

- **Backend:** Python + Flask (single dependency besides PyYAML)
- **Database:** SQLite (zero config, single file)
- **Frontend:** Vanilla HTML/CSS/JS — no build step, no npm, no framework
- **Charts:** Chart.js (loaded from CDN)
- **Bank configs:** YAML files — easy to add/modify
- **Total install size:** ~2 MB (Flask + PyYAML + app code)

---

## Contributing

Issues and PRs welcome. Please don't commit any real transaction data.

---

## License

MIT
