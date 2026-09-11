from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from decimal import Decimal, InvalidOperation
from datetime import datetime
import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# =========================================================
# MOHIT BANKING SYSTEM
# =========================================================

BANK_NAME = "MOHIT BANKING SYSTEM"

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "mohit-banking-demo-key"
)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

def init_database():

    conn = get_connection()

    try:
        cur = conn.cursor()

        # USERS TABLE
        cur.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "id SERIAL PRIMARY KEY,"
            "account_no VARCHAR(30) UNIQUE NOT NULL,"
            "name VARCHAR(120) NOT NULL,"
            "email VARCHAR(160),"
            "phone VARCHAR(30),"
            "account_type VARCHAR(40) NOT NULL DEFAULT 'Savings Account',"
            "password_hash TEXT NOT NULL,"
            "balance NUMERIC(14,2) NOT NULL DEFAULT 0,"
            "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )

        # TRANSACTIONS TABLE
        cur.execute(
            "CREATE TABLE IF NOT EXISTS transactions ("
            "id SERIAL PRIMARY KEY,"
            "transaction_id VARCHAR(80) UNIQUE NOT NULL,"
            "account_no VARCHAR(30) NOT NULL,"
            "sender_account VARCHAR(30),"
            "receiver_account VARCHAR(30),"
            "amount NUMERIC(14,2) NOT NULL,"
            "transaction_type VARCHAR(50) NOT NULL,"
            "title VARCHAR(120),"
            "description TEXT,"
            "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )

        # CREATE ADMIN
        cur.execute(
            "SELECT id FROM users "
            "WHERE account_no = %s",
            ("ADMIN001",)
        )

        admin_exists = cur.fetchone()

        if admin_exists is None:

            cur.execute(
                "INSERT INTO users "
                "(account_no,name,email,phone,account_type,"
                "password_hash,balance) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    "ADMIN001",
                    "Mohit Banking Admin",
                    "admin@mohitbanking.com",
                    "",
                    "Admin",
                    generate_password_hash("admin123"),
                    Decimal("0.00")
                )
            )

        conn.commit()
        cur.close()

    finally:
        conn.close()


# =========================================================
# DATABASE CHECK
# =========================================================

def database_ready():

    try:
        init_database()
        return True

    except Exception:

        app.logger.exception(
            "DATABASE INITIALIZATION ERROR"
        )

        return False


# =========================================================
# BRAND NAME
# =========================================================

@app.context_processor
def inject_brand_name():

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

            return redirect(
                url_for("login")
            )

        return function(*args, **kwargs)

    return wrapper


# =========================================================
# ADMIN REQUIRED
# =========================================================

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if session.get("is_admin") is not True:

            flash(
                "Admin access required.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        return function(*args, **kwargs)

    return wrapper


# =========================================================
# GET USER
# =========================================================

def get_user(account_no):

    conn = get_connection()

    try:

        cur = conn.cursor(
            cursor_factory=RealDictCursor
        )

        cur.execute(
            "SELECT id,account_no,name,email,phone,"
            "account_type,balance,created_at "
            "FROM users WHERE account_no = %s",
            (account_no,)
        )

        return cur.fetchone()

    finally:

        conn.close()


# =========================================================
# TRANSACTION ID
# =========================================================

def make_transaction_id():

    return (
        "TXN-"
        + datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )
        + "-"
        + uuid.uuid4().hex[:6].upper()
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "account_no" in session:

        if session.get("is_admin"):

            return redirect(
                url_for("admin")
            )

        return redirect(
            url_for("dashboard")
        )

    return redirect(
        url_for("login")
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        account_no = request.form.get(
            "account_no",
            ""
        ).strip().upper()

        password = request.form.get(
            "password",
            ""
        )

        if not account_no or not password:

            flash(
                "Enter account number and password.",
                "error"
            )

            return render_template(
                "login.html"
            )

        try:

            if not database_ready():

                flash(
                    "Database is not connected.",
                    "error"
                )

                return render_template(
                    "login.html"
                )

            conn = get_connection()

            cur = conn.cursor(
                cursor_factory=RealDictCursor
            )

            cur.execute(
                "SELECT * FROM users "
                "WHERE account_no = %s",
                (account_no,)
            )

            user = cur.fetchone()

            cur.close()
            conn.close()

            if user and check_password_hash(
                user["password_hash"],
                password
            ):

                session.clear()

                session["account_no"] = (
                    user["account_no"]
                )

                session["is_admin"] = (
                    user["account_type"] == "Admin"
                )

                if session["is_admin"]:

                    return redirect(
                        url_for("admin")
                    )

                return redirect(
                    url_for("dashboard")
                )

            flash(
                "Invalid account number or password.",
                "error"
            )

        except Exception:

            app.logger.exception(
                "LOGIN ERROR"
            )

            flash(
                "Unable to login. Please try again.",
                "error"
            )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

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
        if not name or not email or not phone:

            flash(
                "Please fill all required fields.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if account_type not in (
            "Savings Account",
            "Current Account"
        ):

            account_type = "Savings Account"

        conn = None

        try:

            # MAKE SURE TABLES EXIST
            if not database_ready():

                flash(
                    "Database is not connected. "
                    "Check DATABASE_URL on Render.",
                    "error"
                )

                return render_template(
                    "register.html"
                )

            conn = get_connection()

            cur = conn.cursor()

            # GET LAST NUMERIC ACCOUNT NUMBER
            cur.execute(
                "SELECT COALESCE("
                "MAX(CASE "
                "WHEN account_no ~ '^[0-9]+$' "
                "THEN CAST(account_no AS BIGINT) "
                "ELSE 100000 END),"
                "100000) "
                "FROM users"
            )

            last_number = cur.fetchone()[0]

            account_no = str(
                int(last_number) + 1
            )

            password_hash = generate_password_hash(
                password
            )

            # INSERT NEW USER
            cur.execute(
                "INSERT INTO users "
                "(account_no,name,email,phone,"
                "account_type,password_hash,balance) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    account_no,
                    name,
                    email,
                    phone,
                    account_type,
                    password_hash,
                    Decimal("0.00")
                )
            )

            conn.commit()

            cur.close()
            conn.close()

            flash(
                "Account created successfully! "
                "Your Account Number is "
                + account_no,
                "success"
            )

            return redirect(
                url_for("login")
            )

        except Exception:

            app.logger.exception(
                "REGISTRATION ERROR"
            )

            if conn:

                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass

            flash(
                "Unable to create account. "
                "Please try again.",
                "error"
            )

    return render_template(
        "register.html"
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    try:

        account_no = session["account_no"]

        user = get_user(
            account_no
        )

        if user is None:

            session.clear()

            flash(
                "Account not found.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        conn = get_connection()

        cur = conn.cursor(
            cursor_factory=RealDictCursor
        )

        cur.execute(
            "SELECT transaction_id,amount,"
            "transaction_type,title,description,"
            "sender_account,receiver_account,"
            "created_at "
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

            transaction_type = (
                row["transaction_type"]
            )

            if transaction_type == "DEPOSIT":

                display_type = "deposit"

                title = (
                    row["title"]
                    or "Deposit"
                )

            elif transaction_type == "WITHDRAW":

                display_type = "withdraw"

                title = (
                    row["title"]
                    or "Withdrawal"
                )

            elif transaction_type == "TRANSFER_SENT":

                display_type = "transfer"

                title = (
                    row["title"]
                    or "Money Sent"
                )

            else:

                display_type = "transfer_received"

                title = (
                    row["title"]
                    or "Money Received"
                )

            transactions.append(
                {
                    "transaction_id":
                        row["transaction_id"],

                    "amount":
                        float(row["amount"]),

                    "type":
                        display_type,

                    "title":
                        title,

                    "description":
                        row["description"] or "",

                    "sender_account":
                        row["sender_account"] or "",

                    "receiver_account":
                        row["receiver_account"] or "",

                    "date":
                        row["created_at"].strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if row["created_at"]
                        else ""
                }
            )

        return render_template(
            "dashboard.html",
            user=user,
            balance=float(
                user["balance"] or 0
            ),
            transactions=transactions
        )

    except Exception:

        app.logger.exception(
            "DASHBOARD ERROR"
        )

        flash(
            "Unable to load dashboard.",
            "error"
        )

        return redirect(
            url_for("login")
        )


# =========================================================
# DEPOSIT
# =========================================================

@app.route("/deposit", methods=["POST"])
@login_required
def deposit():

    conn = None

    try:

        amount = Decimal(
            request.form.get(
                "amount",
                "0"
            ).strip()
        )

        if amount <= 0:

            flash(
                "Enter a valid amount.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            "SELECT balance FROM users "
            "WHERE account_no = %s "
            "FOR UPDATE",
            (session["account_no"],)
        )

        row = cur.fetchone()

        if row is None:

            raise ValueError(
                "Account not found"
            )

        new_balance = (
            row[0] + amount
        )

        cur.execute(
            "UPDATE users SET balance = %s "
            "WHERE account_no = %s",
            (
                new_balance,
                session["account_no"]
            )
        )

        cur.execute(
            "INSERT INTO transactions "
            "(transaction_id,account_no,amount,"
            "transaction_type,title,description) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (
                make_transaction_id(),
                session["account_no"],
                amount,
                "DEPOSIT",
                "Cash Deposit",
                "Money deposited"
            )
        )

        conn.commit()

        cur.close()
        conn.close()

        flash(
            "Money deposited successfully.",
            "success"
        )

    except (InvalidOperation, ValueError):

        if conn:

            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

        flash(
            "Enter a valid amount.",
            "error"
        )

    except Exception:

        app.logger.exception(
            "DEPOSIT ERROR"
        )

        if conn:

            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

        flash(
            "Deposit failed.",
            "error"
        )

    return redirect(
        url_for("dashboard")
    )


# =========================================================
# WITHDRAW
# =========================================================

@app.route("/withdraw", methods=["POST"])
@login_required
def withdraw():

    conn = None

    try:

        amount = Decimal(
            request.form.get(
                "amount",
                "0"
            ).strip()
        )

        if amount <= 0:

            flash(
                "Enter a valid amount.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            "SELECT balance FROM users "
            "WHERE account_no = %s "
            "FOR UPDATE",
            (session["account_no"],)
        )

        row = cur.fetchone()

        if row is None:

            raise ValueError(
                "Account not found"
            )

        if row[0] < amount:

            conn.rollback()
            cur.close()
            conn.close()

            flash(
                "Insufficient balance.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        new_balance = (
            row[0] - amount
        )

        cur.execute(
            "UPDATE users SET balance = %s "
            "WHERE account_no
