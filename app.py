from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from decimal import Decimal, InvalidOperation
import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# ==========================================
# MOHIT BANKING SYSTEM
# ==========================================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "mohit-banking-demo-key"
)

BANK_NAME = "MOHIT BANKING SYSTEM"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is missing."
        )

    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


# ==========================================
# CREATE DATABASE TABLES
# ==========================================

def init_database():

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # USERS TABLE
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    account_no VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(150) NOT NULL,
                    email VARCHAR(150),
                    phone VARCHAR(30),
                    account_type VARCHAR(50) NOT NULL,
                    password_hash TEXT NOT NULL,
                    balance NUMERIC(14,2) NOT NULL DEFAULT 0.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # TRANSACTIONS TABLE
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    transaction_id VARCHAR(100) UNIQUE NOT NULL,
                    account_no VARCHAR(50) NOT NULL,
                    sender_account VARCHAR(50),
                    receiver_account VARCHAR(50),
                    amount NUMERIC(14,2) NOT NULL,
                    transaction_type VARCHAR(50) NOT NULL,
                    title VARCHAR(200),
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # CREATE ADMIN ACCOUNT
            cur.execute(
                """
                SELECT id
                FROM users
                WHERE account_no = %s
                """,
                ("ADMIN001",)
            )

            admin = cur.fetchone()

            if admin is None:

                cur.execute(
                    """
                    INSERT INTO users
                    (
                        account_no,
                        name,
                        email,
                        phone,
                        account_type,
                        password_hash,
                        balance
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
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

        print("DATABASE INITIALIZED SUCCESSFULLY")

    except Exception as e:

        conn.rollback()

        print("DATABASE INITIALIZATION ERROR:", e)

        raise

    finally:

        conn.close()


# ==========================================
# INITIALIZE DATABASE
# ==========================================

if DATABASE_URL:

    try:
        init_database()

    except Exception as e:

        print("DATABASE STARTUP ERROR:", e)

else:

    print("WARNING: DATABASE_URL is not configured.")


# ==========================================
# BRANDING
# ==========================================

@app.context_processor
def inject_brand():

    return {
        "brand_name": BANK_NAME
    }


# ==========================================
# LOGIN REQUIRED
# ==========================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "account_no" not in session:

            flash(
                "Please login first.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        return function(*args, **kwargs)

    return wrapper


# ==========================================
# ADMIN REQUIRED
# ==========================================

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("is_admin"):

            flash(
                "Admin access required.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        return function(*args, **kwargs)

    return wrapper


# ==========================================
# GET USER
# ==========================================

def get_user(account_no):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM users
                WHERE account_no = %s
                """,
                (account_no,)
            )

            return cur.fetchone()

    finally:

        conn.close()


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():

    if session.get("account_no"):

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


# ==========================================
# LOGIN
# ==========================================

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

        user = get_user(account_no)

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session["account_no"] = user["account_no"]

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

    return render_template("login.html")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ==========================================
# REGISTER
# ==========================================

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

        # NAME VALIDATION
        if not name:

            flash(
                "Please enter your full name.",
                "error"
            )

            return render_template(
                "register.html"
            )

        # PASSWORD VALIDATION
        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "error"
            )

            return render_template(
                "register.html"
            )

        # CONFIRM PASSWORD
        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return render_template(
                "register.html"
            )

        # ACCOUNT TYPE
        if account_type not in [
            "Savings Account",
            "Current Account",
            "Savings",
            "Current"
        ]:

            account_type = "Savings Account"

        conn = get_connection()

        try:

            with conn.cursor() as cur:

                # GET LAST NUMERIC ACCOUNT
                cur.execute(
                    """
                    SELECT account_no
                    FROM users
                    WHERE account_no ~ '^[0-9]+$'
                    ORDER BY account_no::BIGINT DESC
                    LIMIT 1
                    """
                )

                last_account = cur.fetchone()

                if last_account:

                    new_account_no = (
                        int(last_account["account_no"]) + 1
                    )

                else:

                    new_account_no = 100001

                account_no = str(
                    new_account_no
                )

                # INSERT USER
                cur.execute(
                    """
                    INSERT INTO users
                    (
                        account_no,
                        name,
                        email,
                        phone,
                        account_type,
                        password_hash,
                        balance
                    )
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        account_no,
                        name,
                        email,
                        phone,
                        account_type,
                        generate_password_hash(
                            password
                        ),
                        Decimal("0.00")
                    )
                )

            conn.commit()

            return render_template(
                "register.html",
                created_account=account_no,
                created_name=name
            )

        except Exception as e:

            conn.rollback()

            print(
                "REGISTRATION ERROR:",
                repr(e)
            )

            flash(
                "Unable to create account. Please try again.",
                "error"
            )

        finally:

            conn.close()

    return render_template(
        "register.html"
    )


# ==========================================
# TRANSACTION FORMAT
# ==========================================

def format_transaction(row):

    transaction = dict(row)

    amount = Decimal(
        transaction["amount"]
    )

    transaction_type = (
        transaction["transaction_type"]
    )

    if transaction_type in [
        "DEPOSIT",
        "TRANSFER_RECEIVED"
    ]:

        transaction["amount"] = (
            f"+₹{amount:,.2f}"
        )

    else:

        transaction["amount"] = (
            f"-₹{amount:,.2f}"
        )

    transaction["type"] = transaction_type

    if transaction.get("created_at"):

        transaction["date"] = (
            transaction["created_at"]
            .strftime("%d %b %Y, %I:%M %p")
        )

    else:

        transaction["date"] = ""

    return transaction


# ==========================================
# DASHBOARD
# ==========================================

@app.route("/dashboard")
@login_required
def dashboard():

    account_no = session["account_no"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM users
                WHERE account_no = %s
                """,
                (account_no,)
            )

            user = cur.fetchone()

            if not user:

                session.clear()

                return redirect(
                    url_for("login")
                )

            cur.execute(
                """
                SELECT *
                FROM transactions
                WHERE account_no = %s
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (account_no,)
            )

            transactions = [
                format_transaction(row)
                for row in cur.fetchall()
            ]

        return render_template(
            "dashboard.html",
            user=user,
            balance=user["balance"],
            transactions=transactions
        )

    finally:

        conn.close()


# ==========================================
# DEPOSIT
# ==========================================

@app.route("/deposit", methods=["POST"])
@login_required
def deposit():

    try:

        amount = Decimal(
            request.form.get(
                "amount",
                "0"
            )
        )

    except InvalidOperation:

        amount = Decimal("0")

    if amount <= 0:

        flash(
            "Enter a valid amount.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT balance
                FROM users
                WHERE account_no = %s
                FOR UPDATE
                """,
                (session["account_no"],)
            )

            user = cur.fetchone()

            if not user:

                flash(
                    "Account not found.",
                    "error"
                )

                return redirect(
                    url_for("login")
                )

            new_balance = (
                Decimal(user["balance"])
                + amount
            )

            cur.execute(
                """
                UPDATE users
                SET balance = %s
                WHERE account_no = %s
                """,
                (
                    new_balance,
                    session["account_no"]
                )
            )

            cur.execute(
                """
                INSERT INTO transactions
                (
                    transaction_id,
                    account_no,
                    receiver_account,
                    amount,
                    transaction_type,
                    title,
                    description
                )
                VALUES
                (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    "TXN-" + uuid.uuid4().hex[:12].upper(),
                    session["account_no"],
                    session["account_no"],
                    amount,
                    "DEPOSIT",
                    "Cash Deposit",
                    "Amount deposited into account"
                )
            )

        conn.commit()

        flash(
            f"₹{amount:,.2f} deposited successfully.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "DEPOSIT ERROR:",
            repr(e)
        )

        flash(
            "Unable to process deposit.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for("dashboard")
    )


# ==========================================
# WITHDRAW
# ==========================================

@app.route("/withdraw", methods=["POST"])
@login_required
def withdraw():

    try:

        amount = Decimal(
            request.form.get(
                "amount",
                "0"
            )
        )

    except InvalidOperation:

        amount = Decimal("0")

    if amount <= 0:

        flash(
            "Enter a valid amount.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT balance
                FROM users
                WHERE account_no = %s
                FOR UPDATE
                """,
                (session["account_no"],)
            )

            user = cur.fetchone()

            if not user:

                flash(
                    "Account not found.",
                    "error"
                )

                return redirect(
                    url_for("login")
                )

            balance = Decimal(
                user["balance"]
            )

            if amount > balance:

                flash(
                    "Insufficient balance.",
                    "error"
                )

                return redirect(
                    url_for("dashboard")
                )

            new_balance = (
                balance - amount
            )

            cur.execute(
                """
                UPDATE users
                SET balance = %s
                WHERE account_no = %s
                """,
                (
                    new_balance,
                    session["account_no"]
                )
            )

            cur.execute(
                """
                INSERT INTO transactions
                (
                    transaction_id,
                    account_no,
                    sender_account,
                    amount,
                    transaction_type,
                    title,
                    description
                )
                VALUES
                (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    "TXN-" + uuid.uuid4().hex[:12].upper(),
                    session["account_no"],
                    session["account_no"],
                    amount,
                    "WITHDRAW",
                    "Cash Withdrawal",
                    "Amount withdrawn from account"
                )
            )

        conn.commit()

        flash(
            f"₹{amount:,.2f} withdrawn successfully.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "WITHDRAW ERROR:",
            repr(e)
        )

        flash(
            "Unable to process withdrawal.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for("dashboard")
    )


# ==========================================
# MONEY TRANSFER
# ==========================================

@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():

    if request.method == "GET":

        return render_template(
            "transfer.html"
        )

    sender_account = session["account_no"]

    receiver_account = request.form.get(
        "receiver_account",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    try:

        amount = Decimal(
            request.
