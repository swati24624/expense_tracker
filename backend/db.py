"""
db.py
Small sqlite3 wrapper. No ORM on purpose - keeps the project easy to read
and easy to run with nothing but the standard library + Flask.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "expense_tracker.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


DEFAULT_CATEGORIES = [
    # name, type, keywords (comma separated, used by the rule-based categorizer)
    ("Food & Dining", "expense", "restaurant,cafe,coffee,lunch,dinner,breakfast,food,swiggy,zomato,pizza,burger,snack,grocery,groceries,supermarket"),
    ("Transport", "expense", "uber,ola,cab,taxi,fuel,petrol,diesel,bus,train,metro,flight,parking,toll"),
    ("Shopping", "expense", "amazon,flipkart,myntra,mall,shopping,clothes,shoes,electronics,gadget"),
    ("Bills & Utilities", "expense", "electricity,water bill,recharge,internet,wifi,mobile bill,gas bill,dth,broadband"),
    ("Rent & Housing", "expense", "rent,maintenance,housing,emi,mortgage"),
    ("Health", "expense", "medicine,doctor,hospital,pharmacy,clinic,health,gym,fitness"),
    ("Entertainment", "expense", "movie,netflix,spotify,concert,game,entertainment,subscription,prime"),
    ("Education", "expense", "book,course,tuition,fees,school,college,udemy,exam"),
    ("Travel", "expense", "hotel,trip,travel,vacation,booking,airbnb"),
    ("Other", "expense", ""),
    ("Salary", "income", "salary,payroll,wages"),
    ("Freelance", "income", "freelance,client,project payment,invoice"),
    ("Investment", "income", "dividend,interest,mutual fund,stocks,returns"),
    ("Gift", "income", "gift,bonus,cashback"),
    ("Other Income", "income", ""),
]


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income','expense')),
            keywords TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('income','expense')),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            date TEXT NOT NULL,
            auto_categorized INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,               -- NULL means "overall monthly budget"
            amount REAL NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            UNIQUE(category, month, year)
        )
    """)

    cur.execute("SELECT COUNT(*) as c FROM categories")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO categories (name, type, keywords) VALUES (?,?,?)",
            DEFAULT_CATEGORIES,
        )

    conn.commit()
    conn.close()
