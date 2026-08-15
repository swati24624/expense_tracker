"""
ml_utils.py

The project brief asks for "ML-based" categorization, prediction, anomaly
detection, etc. Rather than shipping a black-box model (which would need a
training set nobody has), everything here uses transparent statistics and
rule-based NLP - keyword scoring, moving averages, z-scores, and simple
date-interval clustering. It's honest, fast, needs no GPU, and every
decision it makes can be explained to the user in one sentence, which
matters a lot for a personal finance tool.
"""

import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------

def categorize_description(description, categories, txn_type="expense"):
    """
    Score the free-text description against each category's keyword list.
    Returns (category_name, confidence 0-1). Falls back to 'Other'/'Other Income'.
    """
    text = (description or "").lower()
    if not text.strip():
        return _fallback_category(txn_type), 0.0

    best_name, best_score = None, 0
    for cat in categories:
        if cat["type"] != txn_type:
            continue
        keywords = [k.strip() for k in (cat["keywords"] or "").split(",") if k.strip()]
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_name = cat["name"]

    if best_name and best_score > 0:
        confidence = min(1.0, 0.5 + 0.25 * best_score)
        return best_name, round(confidence, 2)

    return _fallback_category(txn_type), 0.0


def _fallback_category(txn_type):
    return "Other" if txn_type == "expense" else "Other Income"


# ---------------------------------------------------------------------------
# Natural-language entry parsing
# e.g. "spent 450 on groceries yesterday" / "got 20000 salary on 1 aug"
# ---------------------------------------------------------------------------

INCOME_WORDS = ("got", "received", "earned", "income", "salary", "credited", "deposit")
EXPENSE_WORDS = ("spent", "paid", "bought", "expense", "debit", "purchase")

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def parse_nlp_entry(text, categories, today=None):
    """
    Parse a free-text sentence into a transaction dict.
    Returns dict with keys: type, amount, category, description, date, confidence
    or None if no amount could be found.
    """
    today = today or datetime.now().date()
    original = text
    lower = text.lower()

    # amount - first number in the string (supports 1,200 / 1200.50 / 1.2k style not needed for MVP)
    amount_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)", lower)
    if not amount_match:
        return None
    amount = float(amount_match.group(1).replace(",", ""))

    # type
    txn_type = "expense"
    if any(w in lower for w in INCOME_WORDS):
        txn_type = "income"
    elif any(w in lower for w in EXPENSE_WORDS):
        txn_type = "expense"

    # date
    date = today
    if "yesterday" in lower:
        date = today - timedelta(days=1)
    elif "today" in lower:
        date = today
    else:
        date_match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+)", lower)
        if date_match:
            day = int(date_match.group(1))
            month_word = date_match.group(2)[:9]
            month = None
            for key, val in MONTHS.items():
                if month_word.startswith(key):
                    month = val
                    break
            if month:
                try:
                    date = datetime(today.year, month, day).date()
                except ValueError:
                    date = today

    # strip the amount and filler words to build a cleaner description
    desc = lower
    desc = re.sub(r"\d+(?:,\d{3})*(?:\.\d+)?", "", desc)
    for w in INCOME_WORDS + EXPENSE_WORDS + ("on", "for", "yesterday", "today", "rs", "rs.", "inr", "₹"):
        desc = re.sub(rf"\b{re.escape(w)}\b", "", desc)
    desc = re.sub(r"\s+", " ", desc).strip() or original

    category, confidence = categorize_description(desc, categories, txn_type)

    return {
        "type": txn_type,
        "amount": amount,
        "category": category,
        "description": desc.capitalize(),
        "date": date.isoformat(),
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Forecasting - simple weighted moving average + linear trend over monthly totals
# ---------------------------------------------------------------------------

def forecast_next_month(monthly_totals):
    """
    monthly_totals: list of floats, oldest -> newest (e.g. last 6 months of expenses)
    Returns predicted next value using a trend-adjusted weighted average.
    """
    if not monthly_totals:
        return 0.0
    if len(monthly_totals) == 1:
        return round(monthly_totals[0], 2)

    weights = list(range(1, len(monthly_totals) + 1))
    weighted_avg = sum(v * w for v, w in zip(monthly_totals, weights)) / sum(weights)

    # simple linear trend (slope between first and last, dampened)
    n = len(monthly_totals)
    x_mean = (n - 1) / 2
    y_mean = sum(monthly_totals) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(monthly_totals))
    den = sum((i - x_mean) ** 2 for i in range(n)) or 1
    slope = num / den

    prediction = weighted_avg + slope * 0.5
    return round(max(0, prediction), 2)


# ---------------------------------------------------------------------------
# Anomaly detection - z-score against the user's own category history
# ---------------------------------------------------------------------------

def detect_anomalies(transactions, z_threshold=2.0):
    """
    transactions: list of sqlite3.Row / dicts with 'amount', 'category', 'date', 'id', 'description'
    Flags a transaction as anomalous if it deviates z_threshold std-devs from
    the mean of its own category (needs >= 4 points in that category to judge).
    """
    by_category = defaultdict(list)
    for t in transactions:
        by_category[t["category"]].append(t)

    anomalies = []
    for category, txns in by_category.items():
        amounts = [t["amount"] for t in txns]
        if len(amounts) < 4:
            continue
        mean = statistics.mean(amounts)
        stdev = statistics.pstdev(amounts) or 1
        for t in txns:
            z = (t["amount"] - mean) / stdev
            if z >= z_threshold:
                anomalies.append({
                    "id": t["id"],
                    "date": t["date"],
                    "category": category,
                    "amount": t["amount"],
                    "description": t["description"],
                    "typical_amount": round(mean, 2),
                    "z_score": round(z, 2),
                })
    anomalies.sort(key=lambda a: -a["z_score"])
    return anomalies


# ---------------------------------------------------------------------------
# Recurring transaction detection
# Groups by (category, rounded amount), looks for roughly-monthly spacing
# ---------------------------------------------------------------------------

def detect_recurring(transactions, min_occurrences=3):
    groups = defaultdict(list)
    for t in transactions:
        if t["type"] != "expense":
            continue
        bucket = round(t["amount"] / 10) * 10  # tolerate small variation
        key = (t["category"], bucket)
        groups[key].append(t)

    recurring = []
    for (category, bucket), txns in groups.items():
        if len(txns) < min_occurrences:
            continue
        dates = sorted(datetime.fromisoformat(t["date"]).date() for t in txns)
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        if not gaps:
            continue
        avg_gap = sum(gaps) / len(gaps)
        # "monthly-ish" cadence: 24-38 days between occurrences
        if 24 <= avg_gap <= 38:
            last = dates[-1]
            next_expected = last + timedelta(days=round(avg_gap))
            recurring.append({
                "category": category,
                "amount": round(statistics.mean(t["amount"] for t in txns), 2),
                "occurrences": len(txns),
                "avg_interval_days": round(avg_gap),
                "last_date": last.isoformat(),
                "next_expected": next_expected.isoformat(),
            })
    recurring.sort(key=lambda r: r["next_expected"])
    return recurring


# ---------------------------------------------------------------------------
# Spending / saving score (0-100)
# ---------------------------------------------------------------------------

def compute_score(total_income, total_expense, budget_amount, over_budget_categories):
    if total_income <= 0:
        return 50  # not enough data to judge

    savings_rate = max(0.0, (total_income - total_expense) / total_income)
    score = savings_rate * 70  # up to 70 points for saving well

    if budget_amount and budget_amount > 0:
        budget_adherence = max(0.0, 1 - max(0, total_expense - budget_amount) / budget_amount)
        score += budget_adherence * 20
    else:
        score += 10  # neutral if no budget set

    score -= min(10, over_budget_categories * 2)  # small penalty per blown category budget
    score = max(0, min(100, score))
    return round(score)


# ---------------------------------------------------------------------------
# Insights - human-readable sentences generated from the numbers above
# ---------------------------------------------------------------------------

def generate_insights(current_month_total, prev_month_total, category_totals, budget_amount, total_expense):
    insights = []

    if prev_month_total and prev_month_total > 0:
        change = (current_month_total - prev_month_total) / prev_month_total * 100
        if change > 15:
            insights.append(f"You're spending {round(change)}% more than last month. Worth a look before it becomes a habit.")
        elif change < -15:
            insights.append(f"Nice - spending is down {round(abs(change))}% compared to last month.")

    if category_totals:
        top_cat, top_amt = max(category_totals.items(), key=lambda kv: kv[1])
        if total_expense > 0:
            share = top_amt / total_expense * 100
            if share > 35:
                insights.append(f"{top_cat} makes up {round(share)}% of your spending this month - your single biggest category.")

    if budget_amount and total_expense:
        remaining = budget_amount - total_expense
        if remaining < 0:
            insights.append(f"You've gone ₹{abs(round(remaining)):,} over your monthly budget.")
        elif remaining < budget_amount * 0.1:
            insights.append("You're close to your monthly budget limit - less than 10% left.")

    if not insights:
        insights.append("Your spending looks steady - no unusual patterns this month.")

    return insights
