
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from decimal import Decimal, InvalidOperation
from datetime import datetime
import psycopg2
import os
import uuid


# =========================================================
# MOHIT BANKING SYSTEM
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "mohit-banking-demo-key"
)

BANK_NAME = "MOHIT BANKING SYSTEM"

# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )


def get_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL is not configured")

    return psycopg2.connect(DATABASE_URL)


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_database():
    conn = get_connection()
    cur = conn.cursor()

    # USERS TABLE
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id SERIAL PRIMARY KEY, "
        "account_no VARCHAR(30) UNIQUE NOT NULL, "
        "name VARCHAR(100) NOT NULL, "
        "email VARCHAR(150) NOT NULL, "
        "phone VARCHAR(30), "
        "account_type VARCHAR(30) NOT NULL DEFAULT 'Savings Account', "
        "password_hash TEXT NOT NULL, "
        "balance NUMERIC(14,2) NOT NULL DEFAULT 0, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    )

    # TRANSACTIONS TABLE
    cur.execute(
        "CREATE TABLE IF NOT EXISTS transactions ("
        "id SERIAL PRIMARY KEY, "
        "transaction_id VARCHAR(60) UNIQUE NOT NULL, "
        "account_no VARCHAR(30) NOT NULL, "
        "sender_account VARCHAR(30), "
        "receiver_account VARCHAR(30), "
        "amount NUMERIC(14,2) NOT NULL, "
        "transaction_type VARCHAR(40) NOT NULL, "
        "title VARCHAR(150), "
        "description TEXT, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    )

    # ADMIN ACCOUNT
    cur.execute(
        "SELECT id FROM users WHERE account_no = %s",
        ("ADMIN001",)
    )

    admin = cur.fetchone()

    if not admin:
        cur.execute(
            "INSERT INTO users "
            "(account_no, name, email, phone, account_type, password_hash, balance) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                "ADMIN001",
                "Mohit Banking Admin",
                "admin@mohitbanking.com",
                "",
                "Admin",
                generate_password_hash("admin123"),
                0
            )
        )

    conn.commit()
    cur.close()
    conn.close()


# =========================================================
# BRANDING
# =========================================================

@app.context_processor
def inject_brand():
    return {
        "brand_name": BANK_NAME
    }


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):

        if "account_no" not in session:
            flash("Please login first.", "error")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# =========================================================
# ADMIN REQUIRED
# =========================================================

def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):

        if "account_no" not in session:
            return redirect(url_for("login"))

        if not session.get("is_admin"):
            flash("Admin access required.", "error")
            return redirect(url_for("dashboard"))

        return function(*args, **kwargs)

    return wrapper


# =========================================================
# GET USER
# =========================================================

def get_user(account_no):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, account_no, name, email, phone, account_type, "
        "password_hash, balance, created_at "
        "FROM users WHERE account_no = %s",
        (account_no,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "account_no": row[1],
        "name": row[2],
        "email": row[3],
        "phone": row[4],
        "account_type": row[5],
        "password_hash": row[6],
        "balance": float(row[7]),
        "created_at": row[8]
    }


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "account_no" in session:

        if session.get("is_admin"):
            return redirect(url_for("admin"))

        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        account_no = request.form.get(
            "account_no",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not account_no or not password:
            flash("Please enter account number and password.", "error")
            return render_template("login.html")

        user = get_user(account_no)

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session["account_no"] = user["account_no"]
            session["is_admin"] = (
                user["account_type"] == "Admin"
            )

            flash("Login successful.", "success")

            if session["is_admin"]:
                return redirect(url_for("admin"))

            return redirect(url_for("dashboard"))

        flash("Invalid account number or password.", "error")

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("login"))


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        account_type = request.form.get(
            "account_type",
            "Savings Account"
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # BASIC VALIDATION
        if not name or not email or not password:
            flash(
                "Please fill all required fields.",
                "error"
            )
            return render_template("register.html")

        if len(password) < 6:
            flash(
                "Password must contain at least 6 characters.",
                "error"
            )
            return render_template("register.html")

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "error"
            )
            return render_template("register.html")

        if account_type not in [
            "Savings Account",
            "Current Account"
        ]:
            account_type = "Savings Account"

        conn = None

        try:

            conn = get_connection()
            cur = conn.cursor()

            # CHECK EMAIL
            cur.execute(
                "SELECT id FROM users WHERE LOWER(email) = LOWER(%s)",
                (email,)
            )

            if cur.fetchone():
                flash(
                    "An account with this email already exists.",
                    "error"
                )

                cur.close()
                conn.close()

                return render_template("register.html")

            # GENERATE ACCOUNT NUMBER
            cur.execute(
                "SELECT account_no FROM users "
                "WHERE account_no ~ '^[0-9]+$' "
                "ORDER BY account_no::BIGINT DESC "
                "LIMIT 1"
            )

            last_account = cur.fetchone()

            if last_account:
                new_account = int(last_account[0]) + 1
            else:
                new_account = 100001

            account_no = str(new_account)

            # INSERT USER
            cur.execute(
                "INSERT INTO users "
                "(account_no, name, email, phone, account_type, password_hash, balance) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    account_no,
                    name,
                    email,
                    phone,
                    account_type,
                    generate_password_hash(password),
                    0
                )
            )

            conn.commit()

            cur.close()
            conn.close()

            flash(
                "Account created successfully. "
                "Your Account Number is " + account_no,
                "success"
            )

            return render_template(
                "register.html",
                created_account=account_no
            )

        except Exception as error:

            if conn:
                conn.rollback()
                conn.close()

            print("REGISTRATION ERROR:", error)

            flash(
                "Unable to create account. Please try again.",
                "error"
            )

    return render_template("register.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    account_no = session["account_no"]

    user = get_user(account_no)

    if not user:
        session.clear()
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT transaction_id, amount, transaction_type, "
        "title, description, sender_account, receiver_account, created_at "
        "FROM transactions "
        "WHERE account_no = %s "
        "ORDER BY created_at DESC "
        "LIMIT 10",
        (account_no,)
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    transactions = []

    for row in rows:

        transactions.append({
            "transaction_id": row[0],
            "amount": float(row[1]),
            "type": row[2],
            "title": row[3],
            "description": row[4],
            "sender_account": row[5],
            "receiver_account": row[6],
            "date": row[7].strftime("%d %b %Y %I:%M %p")
            if row[7] else ""
        })

    return render_template(
        "dashboard.html",
        user=user,
        balance=user["balance"],
        transactions=transactions
    )


# =========================================================
# DEPOSIT
# =========================================================

@app.route("/deposit", methods=["POST"])
@login_required
def deposit():

    account_no = session["account_no"]

    amount_text = request.form.get(
        "amount",
        ""
    ).strip()

    try:
        amount = Decimal(amount_text)

    except (InvalidOperation, ValueError):
        flash("Please enter a valid amount.", "error")
        return redirect(url_for("dashboard"))

    if amount <= 0:
        flash("Amount must be greater than zero.", "error")
        return redirect(url_for("dashboard"))

    conn = None

    try:

        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT balance FROM users "
            "WHERE account_no = %s FOR UPDATE",
            (account_no,)
        )

        row = cur.fetchone()

        if not row:
            raise Exception("User account not found")

        new_balance = Decimal(row[0]) + amount

        cur.execute(
            "UPDATE users SET balance = %s "
            "WHERE account_no = %s",
            (
                new_balance,
                account_no
            )
        )

        transaction_id = "TXN-" + uuid.uuid4().hex[:12].upper()

        cur.execute(
            "INSERT INTO transactions "
            "(transaction_id, account_no, sender_account, "
            "receiver_account, amount, transaction_type, "
            "title, description) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                transaction_id,
                account_no,
                None,
                account_no,
                amount,
                "DEPOSIT",
                "Cash Deposit",
                "Money deposited into account"
            )
        )

        conn.commit()

        cur.close()
        conn.close()

        flash(
            "₹" + format(amount, ",.2f") +
            " deposited successfully.",
            "success"
        )

    except Exception as error:

        if conn:
            conn.rollback()
            conn.close()

        print("DEPOSIT ERROR:", error)

        flash(
            "Unable to process deposit.",
            "error"
        )

    return redirect(url_for("dashboard"))


# =========================================================
# WITHDRAW
# =========================================================

@app.route("/withdraw", methods=["POST"])
@login_required
def withdraw():

    account_no = session["account_no"]

    amount_text = request.form.get(
        "amount",
        ""
    ).strip()

    try:
        amount = Decimal(amount_text)

    except (InvalidOperation, ValueError):
        flash("Please enter a valid amount.", "error")
        return redirect(url_for("dashboard"))

    if amount <= 0:
        flash("Amount must be greater than zero.", "error")
        return redirect(url_for("dashboard"))

    conn = None

    try:

        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT balance FROM users "
            "WHERE account_no = %s FOR UPDATE",
            (account_no,)
        )

        row = cur.fetchone()

        if not row:
            raise Exception("User account not found")

        balance = Decimal(row[0])

        if amount > balance:
            flash(
                "Insufficient balance.",
                "error"
            )

            cur.close()
            conn.close()

            return redirect(url_for("dashboard"))

        new_balance = balance - amount

        cur.execute(
            "UPDATE users SET balance = %s "
            "WHERE account_no = %s",
            (
                new_balance,
                account_no
            )
        )

        transaction_id = "TXN-" + uuid.uuid4().hex[:12].upper()

        cur.execute(
            "INSERT INTO transactions "
            "(transaction_id, account_no, sender_account, "
            "receiver_account, amount, transaction_type, "
            "title, description) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                transaction_id,
                account_no,
                account_no,
                None,
                amount,
                "WITHDRAW",
                "Cash Withdrawal",
                "Money withdrawn from account"
            )
        )

        conn.commit()

        cur.close()
        conn.close()

        flash(
            "₹" + format(amount, ",.2f") +
            " withdrawn successfully.",
            "success"
        )

    except Exception as error:

        if conn:
            conn.rollback()
            conn.close()

        print("WITHDRAW ERROR:", error)

        flash(
            "Unable to process withdrawal.",
            "error"
        )

    return redirect(url_for("dashboard"))


# =========================================================
# MONEY TRANSFER
# =========================================================

@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():

    if request.method == "GET":
        return render_template("transfer.html")

    sender_account = session["account_no"]

    receiver_account = request.form.get(
        "receiver_account",
        ""
    ).strip()

    amount_text = request.form.get(
        "amount",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    # VALIDATE RECEIVER
    if not receiver_account:
        flash(
            "Please enter receiver account number.",
            "error"
        )
        return redirect(url_for("transfer"))

    # SAME ACCOUNT
    if receiver_account == sender_account:
        flash(
            "You cannot transfer money to your own account.",
            "error"
        )
        return redirect(url_for("transfer"))

    # AMOUNT
    try:

        amount = Decimal(amount_text)

    except (InvalidOperation, ValueError):

        flash(
            "Please enter a valid amount.",
            "error"
        )

        return redirect(url_for("transfer"))

    if amount <= 0:

        flash(
            "Transfer amount must be greater than zero.",
            "error"
        )

        return redirect(url_for("transfer"))

    conn = None

    try:

        conn = get_connection()
        cur = conn.cursor()

        # LOCK BOTH ACCOUNTS
        cur.execute(
            "SELECT account_no, name, balance, account_type "
            "FROM users "
            "WHERE account_no IN (%s, %s) "
            "ORDER BY account_no "
            "FOR UPDATE",
            (
                sender_account,
                receiver_account
            )
        )

        users = cur.fetchall()

        sender = None
        receiver = None

        for row in users:

            if row[0] == sender_account:
                sender = row

            if row[0] == receiver_account:
                receiver = row

        # RECEIVER NOT FOUND
        if receiver is None:

            cur.close()
            conn.close()

            flash(
                "Receiver account not found.",
                "error"
            )

            return redirect(url_for("transfer"))

        # ADMIN TRANSFER BLOCK
        if receiver[3] == "Admin":

            cur.close()
            conn.close()

            flash(
                "Money cannot be transferred to the admin account.",
                "error"
            )

            return redirect(url_for("transfer"))

        # SENDER NOT FOUND
        if sender is None:

            cur.close()
            conn.close()

            flash(
                "Sender account not found.",
                "error"
            )

            return redirect(url_for("transfer"))

        sender_balance = Decimal(sender[2])

        # BALANCE CHECK
        if amount > sender_balance:

            cur.close()
            conn.close()

            flash(
                "Insufficient balance.",
                "error"
            )

            return redirect(url_for("transfer"))

        # NEW BALANCES
        sender_new_balance = sender_balance - amount
        receiver_new_balance = Decimal(receiver[2]) + amount

        # UPDATE SENDER
        cur.execute(
            "UPDATE users SET balance = %s "
            "WHERE account_no = %s",
            (
                sender_new_balance,
                sender_account
            )
        )

        # UPDATE RECEIVER
        cur.execute(
            "UPDATE users SET balance = %s "
            "WHERE account_no = %s",
            (
                receiver_new_balance,
                receiver_account
            )
        )

        # TRANSACTION ID
        transaction_id = (
            "TXN-" +
            uuid.uuid4().hex[:12].upper()
        )

        # SENDER TRANSACTION
        cur.execute(
            "INSERT INTO transactions "
            "(transaction_id, account_no, sender_account, "
            "receiver_account, amount, transaction_type, "
            "title, description) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                transaction_id,
                sender_account,
                sender_account,
                receiver_account,
                amount,
                "TRANSFER_SENT",
                "Money Transfer",
                description or "Money transferred"
            )
        )

        # RECEIVER TRANSACTION
        receiver_transaction_id = (
            "TXN-" +
            uuid.uuid4().hex[:12].upper()
        )

        cur.execute(
            "INSERT INTO transactions "
            "(transaction_id, account_no, sender_account, "
            "receiver_account, amount, transaction_type, "
            "title, description) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                receiver_transaction_id,
                receiver_account,
                sender_account,
                receiver_account,
                amount,
                "TRANSFER_RECEIVED",
                "Money Received",
                description or "Money received"
            )
        )

        conn.commit()

        cur.close()
        conn.close()

        flash(
            "₹" + format(amount, ",.2f") +
            " transferred successfully to account " +
            receiver_account + ".",
            "success"
        )

        return redirect(url_for("dashboard"))

    except Exception as error:

        if conn:
            conn.rollback()
            conn.close()

        print("TRANSFER ERROR:", error)

        flash(
            "Unable to complete money transfer.",
            "error"
        )

        return redirect(url_for("transfer"))


# =========================================================
# ADMIN PANEL
# =========================================================

@app.route("/admin")
@admin_required
def admin():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT account_no, name, email, phone, "
        "account_type, balance, created_at "
        "FROM users "
        "WHERE account_type != 'Admin' "
        "ORDER BY created_at DESC"
    )

    rows = cur.fetchall()

    users = []

    for row in rows:

        users.append({
            "account_no": row[0],
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "account_type": row[4],
            "balance": float(row[5]),
            "created_at": row[6]
        })

    cur.execute(
        "SELECT COUNT(*) FROM users "
        "WHERE account_type != 'Admin'"
    )

    total_users = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(balance), 0) "
        "FROM users WHERE account_type != 'Admin'"
    )

    total_balance = float(
        cur.fetchone()[0]
    )

    cur.execute(
        "SELECT COUNT(*) FROM transactions"
    )

    total_transactions = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        "admin.html",
        users=users,
        total_users=total_users,
        total_balance=total_balance,
        total_transactions=total_transactions
    )


# =========================================================
# DELETE USER
# =========================================================

@app.route("/admin/delete/<account_no>", methods=["POST"])
@admin_required
def delete_user(account_no):

    if account_no == "ADMIN001":

        flash(
            "Admin account cannot be deleted.",
            "error"
        )

        return redirect(url_for("admin"))

    conn = None

    try:

        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "DELETE FROM transactions "
            "WHERE account_no = %s "
            "OR sender_account = %s "
            "OR receiver_account = %s",
            (
                account_no,
                account_no,
                account_no
            )
        )

        cur.execute(
            "DELETE FROM users "
            "WHERE account_no = %s",
            (account_no,)
        )

        conn.commit()

        cur.close()
        conn.close()

        flash(
            "Account deleted successfully.",
            "success"
        )

    except Exception as error:

        if conn:
            conn.rollback()
            conn.close()

        print("DELETE ERROR:", error)

        flash(
            "Unable to delete account.",
            "error"
        )

    return redirect(url_for("admin"))


# =========================================================
# DATABASE STARTUP
# =========================================================

try:

    if DATABASE_URL:
        init_database()
        print("Database initialized successfully.")

    else:
        print("WARNING: DATABASE_URL is not configured.")

except Exception as error:

    print("DATABASE INITIALIZATION ERROR:", error)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
