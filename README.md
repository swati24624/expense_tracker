A full-stack personal expense tracker: vanilla HTML/CSS/JS frontend, Flask + SQLite backend, no build step, no framework lock-in.

## Run it

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000** — Flask serves the frontend and the API from the same origin, so there's nothing else to start.

The database (`expense_tracker.db`) is created automatically on first run, pre-seeded with a sensible set of categories.

## Project structure

```
expense-tracker/
├── backend/
│   ├── app.py           # Flask routes (all REST endpoints)
│   ├── db.py             # SQLite connection + schema + seed categories
│   ├── ml_utils.py        # Categorization, NLP parsing, forecasting, anomaly & recurring detection, insights, score
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── css/style.css
    └── js/
        ├── api.js         # fetch() wrapper for every endpoint
        ├── charts.js       # Chart.js instances
        ├── calendar.js     # calendar grid rendering
        └── app.js          # views, forms, state, wiring
```

## Features

| Area | What it does |
|---|---|
| Transactions | Add / edit / delete income & expense entries, search & filter |
| Categories | Manual selection, or auto-filled by keyword-scoring against your description |
| Dashboard | Income, expense, balance, savings rate for the selected month |
| Analytics | 6-month trend line, category breakdown (donut + bar) |
| Budget | Overall and per-category monthly limits, with progress bars |
| Forecasting | Next month's predicted income/expense from a trend-adjusted weighted average of recent months |
| Anomaly detection | Flags expenses that are a statistical outlier (z-score) within their own category |
| Recurring detection | Groups same-category/same-amount expenses and checks for a ~monthly cadence |
| Insights | Plain-language notes generated from the numbers (spend vs last month, biggest category, budget proximity) |
| Alerts | Budget overruns, unusual expenses, upcoming recurring payments |
| Import | CSV upload (`date, type, category, amount, description` — category/type optional, auto-filled if missing) |
| Export | CSV and a formatted PDF report |
| NLP quick-add | Type a sentence like *"spent 450 on groceries yesterday"* in the top bar — it's parsed into a full transaction |
| Money score | 0–100 blend of savings rate + budget adherence |
| Calendar | Day-by-day income/expense grid for the month |

## A note on the "ML" features

Categorization, forecasting, anomaly detection, and recurring detection are implemented with transparent statistics — keyword scoring, weighted moving averages with a linear trend term, z-scores against a category's own history, and date-interval clustering — rather than a trained model. That was a deliberate choice: a real ML model needs a labeled dataset nobody has for a fresh tracker, while these methods work from day one, run instantly with no dependencies, and every result can be explained in a sentence ("this is 2.3 standard deviations above your usual Food spend"). If you later want to swap in a real trained classifier (e.g. scikit-learn on your own accumulated data), `ml_utils.py` is the only file you'd need to touch — the API contract (`category, confidence`) stays the same.

## Extending

- Swap SQLite for Postgres by changing `db.py` — the rest of the app just calls `db.get_connection()`.
- Add authentication by wrapping the routes in `app.py` with a session/JWT check; the schema doesn't currently have a `user_id` column, so add one if you need multi-user support.
- The frontend has no framework and no bundler on purpose — open `frontend/js/app.js` and it's all there.
