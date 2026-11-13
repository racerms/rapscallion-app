"""
Rapscallion Motorsports - Business App
Dark mode, QFX import, Invoice tracking, Jobs, Dashboard
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from pathlib import Path
import sys

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from utils.db import init_db, get_connection, get_accounts, get_account_map
from utils.qfx_parser import parse_qfx

# -----------------------------------------------------------------------------
# Page Config & Dark Theme
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Rapscallion Motorsports",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom dark CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    h1, h2, h3, h4 {
        color: #f0f6fc !important;
    }
    .positive { color: #3fb950 !important; }
    .negative { color: #f85149 !important; }
    div[data-testid="stMetricValue"] {
        color: #58a6ff;
    }
    .stButton > button {
        background-color: #238636;
        color: white;
        border: none;
        border-radius: 6px;
    }
    .stButton > button:hover {
        background-color: #2ea043;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Initialize
# -----------------------------------------------------------------------------
init_db()

# -----------------------------------------------------------------------------
# Sidebar Navigation
# -----------------------------------------------------------------------------
st.sidebar.title("🏎️ Rapscallion")
st.sidebar.caption("Motorsports Business App")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Transactions",
        "Invoices",
        "Jobs / Programs",
        "Cars",
        "Reports",
        "Settings"
    ],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.caption("Dark mode • QFX import • ShopMonkey invoices")

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------
def money(val):
    if val is None:
        return "$0.00"
    return f"${val:,.2f}"

def get_summary():
    conn = get_connection()
    income = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE a.type = 'Income' AND amount > 0
    """).fetchone()[0] or 0

    cogs = conn.execute("""
        SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE a.type = 'COGS'
    """).fetchone()[0] or 0

    expenses = conn.execute("""
        SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE a.type = 'Expense'
    """).fetchone()[0] or 0

    uncat = conn.execute("""
        SELECT COUNT(*) FROM transactions WHERE account_id IS NULL
    """).fetchone()[0] or 0

    open_bal = conn.execute("""
        SELECT COALESCE(SUM(balance), 0) FROM invoices WHERE status != 'Paid'
    """).fetchone()[0] or 0

    open_jobs = conn.execute("""
        SELECT COUNT(*) FROM jobs WHERE status != 'Closed'
    """).fetchone()[0] or 0

    conn.close()

    gross = income - cogs
    net = gross - expenses
    return {
        "income": income,
        "cogs": cogs,
        "gross": gross,
        "expenses": expenses,
        "net": net,
        "uncategorized": uncat,
        "open_invoice_balance": open_bal,
        "open_jobs": open_jobs
    }

# -----------------------------------------------------------------------------
# DASHBOARD
# -----------------------------------------------------------------------------
if page == "Dashboard":
    st.title("Dashboard")
    st.caption("Rapscallion Motorsports • Overview")

    s = get_summary()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Income", money(s["income"]))
    with col2:
        st.metric("COGS", money(s["cogs"]))
    with col3:
        st.metric("Gross Margin", money(s["gross"]))
    with col4:
        st.metric("Expenses", money(s["expenses"]))
    with col5:
        st.metric("Net", money(s["net"]))

    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(f"**{s['uncategorized']}** uncategorized transactions")
    with c2:
        st.warning(f"**{money(s['open_invoice_balance'])}** open invoice balance")
    with c3:
        st.success(f"**{s['open_jobs']}** open jobs / programs")

    st.markdown("### Recent Transactions")
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.date, t.description, t.amount, a.name as account, t.invoice_number, t.source
        FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id
        ORDER BY t.date DESC, t.id DESC
        LIMIT 15
    """).fetchall()
    conn.close()

    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        df["amount"] = df["amount"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.write("No transactions yet. Import a QFX file or add manually.")

# -----------------------------------------------------------------------------
# TRANSACTIONS
# -----------------------------------------------------------------------------
elif page == "Transactions":
    st.title("Transactions")
    st.caption("Bank transactions • QFX import from Chase • Categorize & link")

    tab1, tab2, tab3 = st.tabs(["All Transactions", "Import QFX", "Add Manual"])

    with tab1:
        conn = get_connection()
        rows = conn.execute("""
            SELECT t.id, t.date, t.description, t.amount, a.name as account,
                   t.invoice_number, t.job_id, t.source, t.fitid
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.id
            ORDER BY t.date DESC, t.id DESC
            LIMIT 500
        """).fetchall()
        conn.close()

        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("#### Categorize a Transaction")
            txn_ids = [r["id"] for r in rows if r["account"] is None]
            if txn_ids:
                selected_id = st.selectbox("Uncategorized transaction ID", txn_ids)
                accounts = get_accounts()
                acc_options = {f"{a['code']} - {a['name']}": a["id"] for a in accounts}
                chosen = st.selectbox("Account", list(acc_options.keys()))
                inv_num = st.text_input("Invoice # (optional)")
                if st.button("Save Category"):
                    conn = get_connection()
                    conn.execute(
                        "UPDATE transactions SET account_id = ?, invoice_number = ? WHERE id = ?",
                        (acc_options[chosen], inv_num or None, selected_id)
                    )
                    conn.commit()
                    conn.close()
                    st.success("Updated!")
                    st.rerun()
            else:
                st.write("All visible transactions are categorized.")
        else:
            st.info("No transactions yet.")

    with tab2:
        st.subheader("Import Chase QFX / OFX")
        st.write("Download a QFX file from Chase and upload it here.")
        uploaded = st.file_uploader("Choose QFX or OFX file", type=["qfx", "ofx", "QFX", "OFX"])

        if uploaded is not None:
            try:
                file_bytes = uploaded.read()
                txns = parse_qfx(file_bytes)
                st.success(f"Parsed {len(txns)} transactions")

                if txns:
                    preview = pd.DataFrame(txns[:30])
                    st.dataframe(preview, use_container_width=True, hide_index=True)

                    if st.button("Import these transactions", type="primary"):
                        conn = get_connection()
                        imported = 0
                        skipped = 0
                        for t in txns:
                            try:
                                conn.execute("""
                                    INSERT INTO transactions
                                    (date, description, amount, fitid, source)
                                    VALUES (?, ?, ?, ?, 'qfx')
                                """, (t["date"], t["description"], t["amount"], t["fitid"]))
                                imported += 1
                            except Exception:
                                skipped += 1
                        conn.commit()
                        conn.close()
                        st.success(f"Imported {imported} new transactions. Skipped {skipped} duplicates.")
                        st.rerun()
            except Exception as e:
                st.error(f"Failed to parse file: {e}")

    with tab3:
        st.subheader("Add Manual Transaction")
        with st.form("manual_txn"):
            d = st.date_input("Date", value=date.today())
            desc = st.text_input("Description")
            amount = st.number_input("Amount (positive = money in, negative = money out)", value=0.0, step=0.01, format="%.2f")
            accounts = get_accounts()
            acc_options = {"(Uncategorized)": None}
            acc_options.update({f"{a['code']} - {a['name']}": a["id"] for a in accounts})
            acc_label = st.selectbox("Account", list(acc_options.keys()))
            inv = st.text_input("Invoice # (optional)")
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add Transaction")
            if submitted and desc:
                conn = get_connection()
                conn.execute("""
                    INSERT INTO transactions (date, description, amount, account_id, invoice_number, notes, source)
                    VALUES (?, ?, ?, ?, ?, ?, 'manual')
                """, (d.isoformat(), desc, amount, acc_options[acc_label], inv or None, notes))
                conn.commit()
                conn.close()
                st.success("Transaction added")
                st.rerun()

# -----------------------------------------------------------------------------
# INVOICES
# -----------------------------------------------------------------------------
elif page == "Invoices":
    st.title("Invoices")
    st.caption("Track ShopMonkey invoices by invoice number • Link payments")

    tab1, tab2 = st.tabs(["Invoice List", "Add / Import Invoice"])

    with tab1:
        conn = get_connection()
        rows = conn.execute("""
            SELECT id, invoice_number, customer_name, vehicle, invoice_date,
                   total_amount, amount_paid, balance, status, notes
            FROM invoices
            ORDER BY invoice_date DESC, id DESC
        """).fetchall()
        conn.close()

        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("#### Record Payment against Invoice")
            inv_nums = [r["invoice_number"] for r in rows if r["status"] != "Paid"]
            if inv_nums:
                sel_inv = st.selectbox("Invoice #", inv_nums)
                pay_amt = st.number_input("Payment amount", min_value=0.01, step=0.01)
                if st.button("Apply Payment"):
                    conn = get_connection()
                    inv = conn.execute(
                        "SELECT total_amount, amount_paid FROM invoices WHERE invoice_number = ?",
                        (sel_inv,)
                    ).fetchone()
                    new_paid = (inv["amount_paid"] or 0) + pay_amt
                    new_bal = inv["total_amount"] - new_paid
                    status = "Paid" if new_bal <= 0.01 else "Partial"
                    conn.execute("""
                        UPDATE invoices SET amount_paid = ?, balance = ?, status = ?
                        WHERE invoice_number = ?
                    """, (new_paid, max(0, new_bal), status, sel_inv))
                    conn.commit()
                    conn.close()
                    st.success("Payment applied")
                    st.rerun()
        else:
            st.info("No invoices yet. Add one from ShopMonkey.")

    with tab2:
        st.subheader("Add Invoice from ShopMonkey")
        with st.form("add_invoice"):
            inv_num = st.text_input("Invoice Number *", placeholder="e.g. INV-1042")
            customer = st.text_input("Customer Name")
            vehicle = st.text_input("Vehicle")
            inv_date = st.date_input("Invoice Date", value=date.today())
            total = st.number_input("Total Amount *", min_value=0.0, step=0.01, format="%.2f")
            paid = st.number_input("Amount Already Paid", min_value=0.0, step=0.01, format="%.2f", value=0.0)
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Save Invoice")
            if submitted and inv_num and total > 0:
                balance = total - paid
                status = "Paid" if balance <= 0.01 else ("Partial" if paid > 0 else "Open")
                conn = get_connection()
                try:
                    conn.execute("""
                        INSERT INTO invoices
                        (invoice_number, customer_name, vehicle, invoice_date, total_amount, amount_paid, balance, status, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (inv_num, customer, vehicle, inv_date.isoformat(), total, paid, balance, status, notes))
                    conn.commit()
                    st.success(f"Invoice {inv_num} saved")
                except Exception as e:
                    st.error(f"Could not save (duplicate invoice #?): {e}")
                finally:
                    conn.close()
                st.rerun()

# -----------------------------------------------------------------------------
# JOBS / PROGRAMS
# -----------------------------------------------------------------------------
elif page == "Jobs / Programs":
    st.title("Jobs / Programs")
    st.caption("Arrive & Drive • Track Support • Coaching • Shop work • Storage")

    tab1, tab2 = st.tabs(["Job List", "New Job"])

    with tab1:
        conn = get_connection()
        rows = conn.execute("""
            SELECT id, name, job_type, customer_name, car, start_date, end_date,
                   quoted_amount, status, notes
            FROM jobs
            ORDER BY start_date DESC, id DESC
        """).fetchall()
        conn.close()

        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No jobs yet.")

    with tab2:
        with st.form("new_job"):
            name = st.text_input("Job / Program Name *", placeholder="e.g. COTA Endurance - March")
            job_type = st.selectbox("Type", [
                "ArriveDrive-Endurance", "ArriveDrive-Sprint", "TrackSupport",
                "Coaching", "DriftSchool", "Shop", "Storage", "CarSale", "Other"
            ])
            customer = st.text_input("Customer / Driver")
            car = st.text_input("Car / Platform")
            start = st.date_input("Start Date", value=date.today())
            end = st.date_input("End Date", value=date.today())
            quoted = st.number_input("Quoted Amount", min_value=0.0, step=100.0)
            notes = st.text_area("Notes")
            if st.form_submit_button("Create Job") and name:
                conn = get_connection()
                conn.execute("""
                    INSERT INTO jobs (name, job_type, customer_name, car, start_date, end_date, quoted_amount, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, job_type, customer, car, start.isoformat(), end.isoformat(), quoted, notes))
                conn.commit()
                conn.close()
                st.success("Job created")
                st.rerun()

# -----------------------------------------------------------------------------
# CARS
# -----------------------------------------------------------------------------
elif page == "Cars":
    st.title("Cars")
    st.caption("Owned program cars • Customer storage • Cars for sale")

    tab1, tab2 = st.tabs(["Car List", "Add Car"])

    with tab1:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM cars ORDER BY ownership, name").fetchall()
        conn.close()
        if rows:
            st.dataframe(pd.DataFrame([dict(r) for r in rows]), use_container_width=True, hide_index=True)
        else:
            st.info("No cars yet.")

    with tab2:
        with st.form("add_car"):
            name = st.text_input("Name / Nickname *", placeholder="e.g. Rush #23")
            make_model = st.text_input("Make / Model")
            year = st.number_input("Year", min_value=1990, max_value=2030, value=2022)
            vin = st.text_input("VIN (optional)")
            ownership = st.selectbox("Ownership", ["Owned", "CustomerStorage", "ForSale"])
            notes = st.text_area("Notes")
            if st.form_submit_button("Add Car") and name:
                conn = get_connection()
                conn.execute("""
                    INSERT INTO cars (name, make_model, year, vin, ownership, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, make_model, year, vin, ownership, notes))
                conn.commit()
                conn.close()
                st.success("Car added")
                st.rerun()

# -----------------------------------------------------------------------------
# REPORTS
# -----------------------------------------------------------------------------
elif page == "Reports":
    st.title("Reports")
    st.caption("P&L style summary and exports")

    s = get_summary()
    st.subheader("Profit & Loss Snapshot")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Income**  \n{money(s['income'])}")
        st.write(f"**COGS**  \n{money(s['cogs'])}")
        st.write(f"**Gross Margin**  \n{money(s['gross'])}")
    with col2:
        st.write(f"**Operating Expenses**  \n{money(s['expenses'])}")
        st.write(f"**Net**  \n{money(s['net'])}")

    st.markdown("---")
    st.subheader("Income by Account")
    conn = get_connection()
    income_rows = conn.execute("""
        SELECT a.code, a.name, SUM(t.amount) as total
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE a.type = 'Income'
        GROUP BY a.id
        ORDER BY total DESC
    """).fetchall()
    if income_rows:
        st.dataframe(pd.DataFrame([dict(r) for r in income_rows]), use_container_width=True, hide_index=True)
    else:
        st.write("No income categorized yet.")

    st.subheader("Open Invoices")
    open_inv = conn.execute("""
        SELECT invoice_number, customer_name, total_amount, amount_paid, balance, status
        FROM invoices WHERE status != 'Paid'
        ORDER BY invoice_date
    """).fetchall()
    conn.close()
    if open_inv:
        st.dataframe(pd.DataFrame([dict(r) for r in open_inv]), use_container_width=True, hide_index=True)
    else:
        st.write("No open invoices.")

# -----------------------------------------------------------------------------
# SETTINGS
# -----------------------------------------------------------------------------
elif page == "Settings":
    st.title("Settings")
    st.caption("Chart of Accounts and configuration")

    st.subheader("Chart of Accounts")
    accounts = get_accounts()
    if accounts:
        df = pd.DataFrame(accounts)[["code", "name", "type"]]
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.write("**App Info**")
    st.write("- Dark mode enabled")
    st.write("- QFX/OFX import supported (Chase and most banks)")
    st.write("- Invoice tracking by number (ShopMonkey compatible)")
    st.write("- Data stored locally in SQLite")
