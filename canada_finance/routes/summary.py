from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from canada_finance.models.database import get_db

summary_bp = Blueprint("summary", __name__)


@summary_bp.route("/api/months")
def api_months():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT substr(date,1,7) as m FROM transactions WHERE hidden=0 ORDER BY m DESC"
    ).fetchall()
    return jsonify([r["m"] for r in rows])


@summary_bp.route("/api/summary")
def api_summary():
    month = request.args.get("month", "")
    db = get_db()
    like = f"{month}%"
    income = db.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Income' AND hidden=0 AND date LIKE ?",
        (like,),
    ).fetchone()["t"]
    expenses = db.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND hidden=0 AND date LIKE ?",
        (like,),
    ).fetchone()["t"]
    by_cat = db.execute(
        """SELECT category, SUM(amount) as total FROM transactions
           WHERE type='Expense' AND hidden=0 AND date LIKE ? GROUP BY category ORDER BY total DESC""",
        (like,),
    ).fetchall()
    income_by_cat = db.execute(
        """SELECT category, SUM(amount) as total FROM transactions
           WHERE type='Income' AND hidden=0 AND date LIKE ? GROUP BY category ORDER BY total DESC""",
        (like,),
    ).fetchall()
    # Previous month for comparison
    if month:
        y, m = int(month[:4]), int(month[5:7])
        pm = date(y, m, 1) - timedelta(days=1)
        prev_like = f"{pm.year}-{pm.month:02d}%"
        prev_exp = db.execute(
            "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND hidden=0 AND date LIKE ?",
            (prev_like,),
        ).fetchone()["t"]
        prev_by_cat = db.execute(
            """SELECT category, SUM(amount) as total FROM transactions
               WHERE type='Expense' AND hidden=0 AND date LIKE ? GROUP BY category""",
            (prev_like,),
        ).fetchall()
        prev_cat_map = {r["category"]: r["total"] for r in prev_by_cat}
    else:
        prev_exp = 0
        prev_cat_map = {}
    # Budgets
    budgets = {
        r["category"]: r["monthly_limit"]
        for r in db.execute("SELECT category, monthly_limit FROM budgets").fetchall()
    }
    by_cat_out = []
    for r in by_cat:
        cat = r["category"]
        by_cat_out.append({
            "category": cat,
            "total": r["total"],
            "prev_total": prev_cat_map.get(cat, 0),
            "budget": budgets.get(cat),
        })
    return jsonify({
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
        "prev_expenses": prev_exp,
        "savings_rate": round((income - expenses) / income * 100, 1) if income > 0 else 0,
        "by_category": by_cat_out,
        "income_by_category": [{"category": r["category"], "total": r["total"]} for r in income_by_cat],
    })


@summary_bp.route("/api/year/<int:year>")
def api_year(year):
    db = get_db()
    months_data = []
    for m in range(1, 13):
        like = f"{year}-{m:02d}%"
        inc = db.execute(
            "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Income' AND hidden=0 AND date LIKE ?",
            (like,),
        ).fetchone()["t"]
        exp = db.execute(
            "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND hidden=0 AND date LIKE ?",
            (like,),
        ).fetchone()["t"]
        months_data.append({"month": f"{year}-{m:02d}", "income": inc, "expenses": exp, "net": inc - exp})
    top_cats = db.execute(
        """SELECT category, SUM(amount) as total FROM transactions
        WHERE type='Expense' AND hidden=0 AND date LIKE ? GROUP BY category ORDER BY total DESC LIMIT 5""",
        (f"{year}%",),
    ).fetchall()
    return jsonify({
        "months": months_data,
        "top_categories": [{"category": r["category"], "total": r["total"]} for r in top_cats],
        "total_income": sum(m["income"] for m in months_data),
        "total_expenses": sum(m["expenses"] for m in months_data),
    })


@summary_bp.route("/api/averages")
def api_averages():
    """Monthly average spend per category based on last 6 months."""
    db = get_db()
    months_with_data = db.execute("""
        SELECT DISTINCT substr(date,1,7) as m FROM transactions
        WHERE type='Expense' AND hidden=0 ORDER BY m DESC LIMIT 6
    """).fetchall()
    n = len(months_with_data)
    if n == 0:
        return jsonify([])
    placeholders = ",".join("?" * n)
    rows = db.execute(
        f"""SELECT category,
               ROUND(SUM(amount)/{n}, 2) as avg_monthly,
               COUNT(DISTINCT substr(date,1,7)) as months_seen
        FROM transactions WHERE type='Expense' AND hidden=0
        AND substr(date,1,7) IN ({placeholders})
        GROUP BY category ORDER BY avg_monthly DESC""",
        [r["m"] for r in months_with_data],
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@summary_bp.route("/api/recurring")
def api_recurring():
    """Detect recurring transactions — same merchant appearing in 3+ distinct months."""
    db = get_db()
    min_months = request.args.get("min_months", 3, type=int)
    rows = db.execute("""
        SELECT name,
               category,
               type,
               COUNT(DISTINCT substr(date,1,7)) as months_seen,
               ROUND(AVG(amount), 2) as avg_amount,
               ROUND(MIN(amount), 2) as min_amount,
               ROUND(MAX(amount), 2) as max_amount,
               COUNT(*) as total_charges,
               MAX(date) as last_seen,
               MIN(date) as first_seen
        FROM transactions
        WHERE hidden=0
        GROUP BY LOWER(TRIM(name))
        HAVING months_seen >= ?
        ORDER BY months_seen DESC, avg_amount DESC
    """, (min_months,)).fetchall()
    recurring = []
    for r in rows:
        entry = dict(r)
        entry["price_changed"] = round(r["max_amount"] - r["min_amount"], 2) > 0.01
        recurring.append(entry)
    total_monthly = sum(
        r["avg_amount"] for r in recurring if r["type"] == "Expense"
    )
    return jsonify({
        "recurring": recurring,
        "total_monthly_committed": round(total_monthly, 2),
        "count": len(recurring),
    })
