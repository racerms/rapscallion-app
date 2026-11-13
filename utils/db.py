import sqlite3
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "rapscallion.db"

def get_connection():
    # Make sure the data folder exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Chart of Accounts
    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            parent TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    # Transactions
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            account_id INTEGER,
            job_id INTEGER,
            invoice_number TEXT,
            fitid TEXT UNIQUE,
            source TEXT DEFAULT 'manual',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)

    # Invoices
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            customer_name TEXT,
            vehicle TEXT,
            invoice_date TEXT,
            due_date TEXT,
            total_amount REAL NOT NULL,
            amount_paid REAL DEFAULT 0,
            balance REAL,
            status TEXT DEFAULT 'Open',
            job_id INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)

    # Jobs / Programs
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            job_type TEXT,
            customer_name TEXT,
            car TEXT,
            start_date TEXT,
            end_date TEXT,
            quoted_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'Open',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Cars
    c.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            make_model TEXT,
            year INTEGER,
            vin TEXT,
            ownership TEXT,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Customers
    c.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # Seed default Chart of Accounts if empty
    c.execute("SELECT COUNT(*) FROM accounts")
    if c.fetchone()[0] == 0:
        seed_accounts(c)
        conn.commit()

    conn.close()

def seed_accounts(c):
    accounts = [
        # Income
        ("4000", "Race Car Sales", "Income", None),
        ("4100", "Arrive & Drive - Endurance", "Income", None),
        ("4110", "Arrive & Drive - Sprint", "Income", None),
        ("4200", "Race Car Rental / Track Days", "Income", None),
        ("4300", "Track Support (Customer Cars)", "Income", None),
        ("4400", "Driver Coaching", "Income", None),
        ("4500", "Drift School", "Income", None),
        ("4600", "Shop / Garage Services", "Income", None),
        ("4700", "Storage Income", "Income", None),
        ("4800", "Parts & Merchandise", "Income", None),
        ("4900", "Other Income", "Income", None),

        # COGS
        ("5000", "Race Car Purchase Cost", "COGS", None),
        ("5100", "Tires", "COGS", None),
        ("5200", "Fuel & Fluids", "COGS", None),
        ("5300", "Entry Fees & Track Costs", "COGS", None),
        ("5400", "Parts Used on Jobs", "COGS", None),
        ("5500", "Crew / Contract Labor", "COGS", None),
        ("5600", "Transport / Trailer", "COGS", None),
        ("5700", "Other Direct Costs", "COGS", None),

        # Expenses
        ("6000", "Rent / Facility", "Expense", None),
        ("6100", "Insurance", "Expense", None),
        ("6200", "Utilities", "Expense", None),
        ("6300", "Marketing & Advertising", "Expense", None),
        ("6400", "Office & Admin", "Expense", None),
        ("6500", "Travel", "Expense", None),
        ("6600", "Professional Fees", "Expense", None),
        ("6700", "Software & Subscriptions", "Expense", None),
        ("6800", "Repairs & Maintenance (Shop)", "Expense", None),
        ("6900", "Other Operating Expenses", "Expense", None),
    ]
    for code, name, typ, parent in accounts:
        c.execute(
            "INSERT OR IGNORE INTO accounts (code, name, type, parent) VALUES (?, ?, ?, ?)",
            (code, name, typ, parent)
        )

def get_accounts(account_type=None):
    conn = get_connection()
    if account_type:
        rows = conn.execute(
            "SELECT * FROM accounts WHERE type = ? AND active = 1 ORDER BY code",
            (account_type,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM accounts WHERE active = 1 ORDER BY type, code"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_account_map():
    accounts = get_accounts()
    return {a["id"]: a for a in accounts}
