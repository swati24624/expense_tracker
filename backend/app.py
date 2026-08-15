"""
app.py - Expense Tracker backend

A plain Flask REST API (no ORM, no build step) that serves the static
frontend and exposes JSON endpoints the frontend's fetch() calls talk to.
Run with: python app.py
"""

import csv
import io
import os
from calendar import monthrange
from collections import defaultdict
from datetime import datetime, date

from flask import Flask, request, jsonify, send_from_directory, send_file

import db
import ml_utils

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

# CORS only matters if you serve the frontend from a different origin than
# the API (e.g. a separate dev server). Since Flask serves both here, it's
# optional - but enabled automatically if flask-cors is installed.
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    pass

db.init_db()


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def row_to_dict(row):
    return dict(row) if row else None


def get_all_categories():
    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM categories ORDER BY type, name").fetchall()
    conn.close()
    return rows


def month_bounds(year, month):
    start = date(year, month, 1).isoformat()
    end_day = monthrange(year, month)[1]
    end = date(year, month, end_day).isoformat()
    return start, end


def get_month_year_from_request():
    today = datetime.now()
    month = int(request.args.get("month", today.month))
    year = int(request.args.get("year", today.year))
    return month, year


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@app.get("/api/categories")
def list_categories():
    rows = get_all_categories()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/categories")
def create_category():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    ctype = data.get("type", "expense")
    keywords = data.get("keywords", "")
    if not name:
        return jsonify({"error": "Category name is required"}), 400

    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO categories (name, type, keywords) VALUES (?,?,?)",
            (name, ctype, keywords),
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400
    conn.close()
    return jsonify({"message": "Category created"}), 201


# ---------------------------------------------------------------------------
# Transactions - CRUD
# ---------------------------------------------------------------------------

@app.get("/api/transactions")
def list_transactions():
    conn = db.get_connection()
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []

    if request.args.get("type"):
        query += " AND type = ?"
        params.append(request.args["type"])
    if request.args.get("category"):
        query += " AND category = ?"
        params.append(request.args["category"])
    if request.args.get("start"):
        query += " AND date >= ?"
        params.append(request.args["start"])
    if request.args.get("end"):
        query += " AND date <= ?"
        params.append(request.args["end"])
    if request.args.get("search"):
        query += " AND (description LIKE ? OR category LIKE ?)"
        term = f"%{request.args['search']}%"
        params.extend([term, term])

    query += " ORDER BY date DESC, id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/transactions")
def create_transaction():
    data = request.get_json(force=True)
    txn_type = data.get("type")
    amount = data.get("amount")
    description = data.get("description", "")
    txn_date = data.get("date") or date.today().isoformat()
    category = data.get("category")
    auto = 0

    if txn_type not in ("income", "expense"):
        return jsonify({"error": "type must be 'income' or 'expense'"}), 400
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a positive number"}), 400

    if not category:
        categories = get_all_categories()
        category, _ = ml_utils.categorize_description(description, categories, txn_type)
        auto = 1

    conn = db.get_connection()
    cur = conn.execute(
        "INSERT INTO transactions (type, amount, category, description, date, auto_categorized) "
        "VALUES (?,?,?,?,?,?)",
        (txn_type, amount, category, description, txn_date, auto),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM transactions WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@app.put("/api/transactions/<int:txn_id>")
def update_transaction(txn_id):
    data = request.get_json(force=True)
    conn = db.get_connection()
    existing = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Transaction not found"}), 404

    fields = {}
    for key in ("type", "amount", "category", "description", "date"):
        if key in data:
            fields[key] = data[key]

    if "amount" in fields:
        try:
            fields["amount"] = float(fields["amount"])
        except (TypeError, ValueError):
            conn.close()
            return jsonify({"error": "amount must be a number"}), 400

    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values()) + [txn_id]
        conn.execute(f"UPDATE transactions SET {set_clause} WHERE id = ?", params)
        conn.commit()

    row = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row))


@app.delete("/api/transactions/<int:txn_id>")
def delete_transaction(txn_id):
    conn = db.get_connection()
    conn.execute("DELETE FROM transactions WHERE id=?", (txn_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})


# ---------------------------------------------------------------------------
# NLP quick-entry
# ---------------------------------------------------------------------------

@app.post("/api/nlp-entry")
def nlp_entry():
    data = request.get_json(force=True)
    text = data.get("text", "")
    categories = get_all_categories()
    parsed = ml_utils.parse_nlp_entry(text, categories)
    if not parsed:
        return jsonify({"error": "Couldn't find an amount in that sentence. Try e.g. 'spent 450 on groceries yesterday'."}), 400

    if data.get("save"):
        conn = db.get_connection()
        cur = conn.execute(
            "INSERT INTO transactions (type, amount, category, description, date, auto_categorized) "
            "VALUES (?,?,?,?,?,1)",
            (parsed["type"], parsed["amount"], parsed["category"], parsed["description"], parsed["date"]),
        )
        conn.commit()
        parsed["id"] = cur.lastrowid
        conn.close()

    return jsonify(parsed)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard")
def dashboard():
    month, year = get_month_year_from_request()
    start, end = month_bounds(year, month)

    conn = db.get_connection()
    rows = conn.execute(
        "SELECT type, amount FROM transactions WHERE date BETWEEN ? AND ?", (start, end)
    ).fetchall()
    conn.close()

    income = sum(r["amount"] for r in rows if r["type"] == "income")
    expense = sum(r["amount"] for r in rows if r["type"] == "expense")
    balance = income - expense
    savings_rate = round((balance / income * 100), 1) if income > 0 else 0

    return jsonify({
        "income": round(income, 2),
        "expense": round(expense, 2),
        "balance": round(balance, 2),
        "savings_rate": savings_rate,
        "month": month,
        "year": year,
        "transaction_count": len(rows),
    })


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@app.get("/api/analytics/trends")
def trends():
    months_back = int(request.args.get("months", 6))
    today = datetime.now()
    conn = db.get_connection()

    results = []
    y, m = today.year, today.month
    buckets = []
    for _ in range(months_back):
        buckets.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    buckets.reverse()

    for (yr, mo) in buckets:
        start, end = month_bounds(yr, mo)
        rows = conn.execute(
            "SELECT type, amount FROM transactions WHERE date BETWEEN ? AND ?", (start, end)
        ).fetchall()
        income = sum(r["amount"] for r in rows if r["type"] == "income")
        expense = sum(r["amount"] for r in rows if r["type"] == "expense")
        results.append({
            "label": date(yr, mo, 1).strftime("%b %Y"),
            "year": yr, "month": mo,
            "income": round(income, 2),
            "expense": round(expense, 2),
            "balance": round(income - expense, 2),
        })
    conn.close()
    return jsonify(results)


@app.get("/api/analytics/category-breakdown")
def category_breakdown():
    month, year = get_month_year_from_request()
    txn_type = request.args.get("type", "expense")
    start, end = month_bounds(year, month)

    conn = db.get_connection()
    rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM transactions "
        "WHERE date BETWEEN ? AND ? AND type = ? GROUP BY category ORDER BY total DESC",
        (start, end, txn_type),
    ).fetchall()
    conn.close()
    return jsonify([{"category": r["category"], "total": round(r["total"], 2)} for r in rows])


@app.get("/api/analytics/calendar")
def calendar_view():
    month, year = get_month_year_from_request()
    start, end = month_bounds(year, month)

    conn = db.get_connection()
    rows = conn.execute(
        "SELECT date, type, SUM(amount) as total FROM transactions "
        "WHERE date BETWEEN ? AND ? GROUP BY date, type", (start, end)
    ).fetchall()
    conn.close()

    by_day = defaultdict(lambda: {"income": 0, "expense": 0})
    for r in rows:
        by_day[r["date"]][r["type"]] = round(r["total"], 2)

    return jsonify(by_day)


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

@app.get("/api/budgets")
def list_budgets():
    month, year = get_month_year_from_request()
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT * FROM budgets WHERE month=? AND year=?", (month, year)
    ).fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/budgets")
def set_budget():
    data = request.get_json(force=True)
    category = data.get("category")  # None/omitted = overall budget
    amount = data.get("amount")
    month, year = int(data.get("month")), int(data.get("year"))

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a number"}), 400

    conn = db.get_connection()
    conn.execute(
        "INSERT INTO budgets (category, amount, month, year) VALUES (?,?,?,?) "
        "ON CONFLICT(category, month, year) DO UPDATE SET amount = excluded.amount",
        (category, amount, month, year),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Budget saved"}), 201


@app.delete("/api/budgets/<int:budget_id>")
def delete_budget(budget_id):
    conn = db.get_connection()
    conn.execute("DELETE FROM budgets WHERE id=?", (budget_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})


@app.get("/api/budgets/status")
def budget_status():
    """ Budget vs actual for the month, per category + overall. """
    month, year = get_month_year_from_request()
    start, end = month_bounds(year, month)

    conn = db.get_connection()
    budgets = conn.execute("SELECT * FROM budgets WHERE month=? AND year=?", (month, year)).fetchall()
    spend_rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM transactions "
        "WHERE date BETWEEN ? AND ? AND type='expense' GROUP BY category", (start, end)
    ).fetchall()
    conn.close()

    spend_by_cat = {r["category"]: r["total"] for r in spend_rows}
    total_spend = sum(spend_by_cat.values())

    status = []
    for b in budgets:
        spent = total_spend if b["category"] is None else spend_by_cat.get(b["category"], 0)
        status.append({
            "id": b["id"],
            "category": b["category"] or "Overall",
            "budget": b["amount"],
            "spent": round(spent, 2),
            "remaining": round(b["amount"] - spent, 2),
            "percent_used": round((spent / b["amount"] * 100), 1) if b["amount"] > 0 else 0,
            "over_budget": spent > b["amount"],
        })
    return jsonify(status)


# ---------------------------------------------------------------------------
# Predictions / ML-ish features
# ---------------------------------------------------------------------------

@app.get("/api/predictions/forecast")
def forecast():
    conn = db.get_connection()
    today = datetime.now()
    y, m = today.year, today.month
    months = []
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    months.reverse()

    monthly_expense, monthly_income = [], []
    for (yr, mo) in months:
        start, end = month_bounds(yr, mo)
        rows = conn.execute(
            "SELECT type, amount FROM transactions WHERE date BETWEEN ? AND ?", (start, end)
        ).fetchall()
        monthly_expense.append(sum(r["amount"] for r in rows if r["type"] == "expense"))
        monthly_income.append(sum(r["amount"] for r in rows if r["type"] == "income"))
    conn.close()

    predicted_expense = ml_utils.forecast_next_month(monthly_expense)
    predicted_income = ml_utils.forecast_next_month(monthly_income)

    return jsonify({
        "predicted_next_month_expense": predicted_expense,
        "predicted_next_month_income": predicted_income,
        "predicted_next_month_balance": round(predicted_income - predicted_expense, 2),
        "history_months_used": len([v for v in monthly_expense if v > 0]) or len(monthly_expense),
    })


@app.get("/api/predictions/anomalies")
def anomalies():
    months_back = int(request.args.get("months", 3))
    today = datetime.now()
    y, m = today.year, today.month
    m -= months_back
    while m <= 0:
        m += 12
        y -= 1
    start, _ = month_bounds(y, m)

    conn = db.get_connection()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE type='expense' AND date >= ? ORDER BY date", (start,)
    ).fetchall()
    conn.close()
    return jsonify(ml_utils.detect_anomalies(rows))


@app.get("/api/predictions/recurring")
def recurring():
    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM transactions WHERE type='expense' ORDER BY date").fetchall()
    conn.close()
    return jsonify(ml_utils.detect_recurring(rows))


@app.get("/api/insights")
def insights():
    month, year = get_month_year_from_request()
    prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
    start, end = month_bounds(year, month)
    prev_start, prev_end = month_bounds(prev_year, prev_month)

    conn = db.get_connection()
    cur_rows = conn.execute(
        "SELECT type, category, amount FROM transactions WHERE date BETWEEN ? AND ?", (start, end)
    ).fetchall()
    prev_rows = conn.execute(
        "SELECT amount FROM transactions WHERE date BETWEEN ? AND ? AND type='expense'", (prev_start, prev_end)
    ).fetchall()
    budget_row = conn.execute(
        "SELECT amount FROM budgets WHERE category IS NULL AND month=? AND year=?", (month, year)
    ).fetchone()
    conn.close()

    current_total = sum(r["amount"] for r in cur_rows if r["type"] == "expense")
    prev_total = sum(r["amount"] for r in prev_rows)
    category_totals = defaultdict(float)
    for r in cur_rows:
        if r["type"] == "expense":
            category_totals[r["category"]] += r["amount"]

    result = ml_utils.generate_insights(
        current_total, prev_total, category_totals,
        budget_row["amount"] if budget_row else None,
        current_total,
    )
    return jsonify(result)


@app.get("/api/score")
def score():
    month, year = get_month_year_from_request()
    start, end = month_bounds(year, month)
    conn = db.get_connection()
    rows = conn.execute("SELECT type, amount FROM transactions WHERE date BETWEEN ? AND ?", (start, end)).fetchall()
    budget_row = conn.execute(
        "SELECT amount FROM budgets WHERE category IS NULL AND month=? AND year=?", (month, year)
    ).fetchone()
    status_rows = conn.execute("SELECT * FROM budgets WHERE month=? AND year=?", (month, year)).fetchall()
    conn.close()

    income = sum(r["amount"] for r in rows if r["type"] == "income")
    expense = sum(r["amount"] for r in rows if r["type"] == "expense")

    over_count = 0
    for b in status_rows:
        # reuse the budget_status logic lightly
        pass

    s = ml_utils.compute_score(income, expense, budget_row["amount"] if budget_row else None, over_count)
    return jsonify({"score": s, "month": month, "year": year})


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.get("/api/alerts")
def alerts():
    month, year = get_month_year_from_request()
    alert_list = []

    with app.test_request_context(f"/api/budgets/status?month={month}&year={year}"):
        budget_statuses = budget_status().json
    for b in budget_statuses:
        if b["over_budget"]:
            alert_list.append({
                "type": "budget",
                "level": "danger",
                "message": f"You've exceeded your {b['category']} budget by ₹{abs(b['remaining']):,.0f}.",
            })
        elif b["percent_used"] >= 90:
            alert_list.append({
                "type": "budget",
                "level": "warning",
                "message": f"{b['category']} budget is {b['percent_used']}% used.",
            })

    with app.test_request_context("/api/predictions/anomalies?months=3"):
        anomaly_list = anomalies().json
    for a in anomaly_list[:5]:
        alert_list.append({
            "type": "anomaly",
            "level": "warning",
            "message": f"Unusual {a['category']} expense of ₹{a['amount']:,.0f} on {a['date']} "
                       f"(typically ₹{a['typical_amount']:,.0f}).",
        })

    with app.test_request_context("/api/predictions/recurring"):
        recurring_list = recurring().json
    today = date.today()
    for r in recurring_list:
        next_expected = datetime.fromisoformat(r["next_expected"]).date()
        days_away = (next_expected - today).days
        if 0 <= days_away <= 3:
            alert_list.append({
                "type": "recurring",
                "level": "info",
                "message": f"{r['category']} payment of ~₹{r['amount']:,.0f} is expected around {r['next_expected']}.",
            })

    return jsonify(alert_list)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@app.post("/api/import")
def import_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    content = file.read().decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))

    categories = get_all_categories()
    conn = db.get_connection()
    inserted, skipped = 0, 0

    for row in reader:
        try:
            keys = {k.lower().strip(): v for k, v in row.items()}
            txn_date = keys.get("date") or date.today().isoformat()
            amount = float(str(keys.get("amount", "0")).replace(",", ""))
            txn_type = (keys.get("type") or ("income" if amount > 0 else "expense")).lower().strip()
            if txn_type not in ("income", "expense"):
                txn_type = "expense"
            amount = abs(amount)
            description = keys.get("description", "") or keys.get("narration", "")
            category = keys.get("category")
            if not category:
                category, _ = ml_utils.categorize_description(description, categories, txn_type)

            conn.execute(
                "INSERT INTO transactions (type, amount, category, description, date, auto_categorized) "
                "VALUES (?,?,?,?,?,?)",
                (txn_type, amount, category, description, txn_date, 0 if keys.get("category") else 1),
            )
            inserted += 1
        except Exception:
            skipped += 1
            continue

    conn.commit()
    conn.close()
    return jsonify({"inserted": inserted, "skipped": skipped})


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@app.get("/api/export/csv")
def export_csv():
    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM transactions ORDER BY date DESC").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Type", "Category", "Amount", "Description"])
    for r in rows:
        writer.writerow([r["date"], r["type"], r["category"], r["amount"], r["description"]])

    mem = io.BytesIO(output.getvalue().encode("utf-8"))
    return send_file(mem, mimetype="text/csv", as_attachment=True,
                      download_name="transactions.csv")


@app.get("/api/export/pdf")
def export_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm

    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM transactions ORDER BY date DESC").fetchall()
    conn.close()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Expense Tracker Report", styles["Title"]), Spacer(1, 12)]

    income = sum(r["amount"] for r in rows if r["type"] == "income")
    expense = sum(r["amount"] for r in rows if r["type"] == "expense")
    elements.append(Paragraph(f"Total Income: ₹{income:,.2f} | Total Expense: ₹{expense:,.2f} | "
                               f"Balance: ₹{income - expense:,.2f}", styles["Normal"]))
    elements.append(Spacer(1, 16))

    data = [["Date", "Type", "Category", "Amount", "Description"]]
    for r in rows:
        data.append([r["date"], r["type"], r["category"], f"{r['amount']:.2f}", (r["description"] or "")[:40]])

    table = Table(data, colWidths=[2.2 * cm, 2 * cm, 3 * cm, 2.5 * cm, 6 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16302B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F3EF")]),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name="expense_report.pdf")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
