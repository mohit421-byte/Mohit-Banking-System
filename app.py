from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from decimal import Decimal, InvalidOperation
import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor


# =========================================================
# MOHIT BANKING SYSTEM
# PostgreSQL + Flask
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "mohit-banking-demo-key"
)

BANK_NAME = "MOHIT BANKING SYSTEM"


# =========================================================
# DATABASE URL
# =========================================================

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
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
            "DATABASE_URL environment variable is not configured."
        )

    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


# =========================================================
# DATABASE SETUP
# =========================================================

def init_database():

    conn = get_connection()

    try:

        cur = conn.cursor()

        # -------------------------
        # USERS TABLE
        # -------------------------

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                account_no VARCHAR(30) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150),
                phone VARCHAR(30),
                account_type VARCHAR(30) NOT NULL DEFAULT 'Savings',
                password_hash TEXT NOT NULL,
                balance NUMERIC(14,2) NOT NULL DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # -------------------------
        # TRANSACTIONS TABLE
        # -------------------------

        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                transaction_id VARCHAR(100) UNIQUE NOT NULL,
                account_no VARCHAR(30) NOT NULL,
                sender_account VARCHAR(30),
                receiver_account VARCHAR(30),
                amount NUMERIC(14,2) NOT NULL,
                transaction_type VARCHAR(40) NOT NULL,
                title VARCHAR(150) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # -------------------------
        # ADMIN ACCOUNT
        # -------------------------

        cur.execute("""
            SELECT account_no
            FROM users
            WHERE account_no = %s
        """, ("ADMIN001",))

        admin = cur.fetchone()

        if not admin:

            cur.execute("""
                INSERT INTO users (
                    account_no,
                    name,
                    email,
                    phone,
                    account_type,
                    password_hash,
                    balance
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                "ADMIN001",
                "Mohit Banking Admin",
                "admin@mohitbanking.com",
                "",
                "Admin",
                generate_password_hash("admin123"),
                Decimal("0.00")
            ))

        conn.commit()

        cur.close()

    finally:
        conn.close()


# =========================================================
# BRANDING
# =========================================================

@app.context_processor
def inject_brand_name():

    return {
        "brand_name": BANK_NAME
    }


@app.after_request
def update_branding(response):

    content_type = response.headers.get(
        "Content-Type",
        ""
    )

    if "text/html" in content_type:

        try:

            html = response.get_data(
                as_text=True
            )

            html = html.replace(
                "Prince Banking",
                BANK_NAME
            )

            html = html.replace(
                "PRINCE BANKING",
                BANK_NAME
            )

            html = html.replace(
                "Prince - Mohit Banking",
                BANK_NAME
            )

            html = html.replace(
                "PRINCE MOHIT BANKING",
                BANK_NAME
            )

            response.set_data(html)

        except Exception:
            pass

    return response


# =========================================================
# LOGIN PROTECTION
# =========================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "account_no" not in session:

            return redirect(
                url_for("login")
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# ADMIN PROTECTION
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

        return function(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# GET USER
# =========================================================

def get_user(account_no):

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                account_no,
                name,
                email,
                phone,
                account_type,
                password_hash,
                balance,
                created_at
            FROM users
            WHERE account_no = %s
        """, (
            account_no,
        ))

        user = cur.fetchone()

        cur.close()

        return user

    finally:

        conn.close()


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

@app.route(
    "/login",
    methods=["GET", "POST"]
)
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

        user = get_user(account_no)

        if user:

            try:

                password_correct = check_password_hash(
                    user["password_hash"],
                    password
                )

            except Exception:

                password_correct = False

            if password_correct:

                session["account_no"] = user[
                    "account_no"
                ]

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

@app.route(
    "/register",
    methods=["GET", "POST"]
)
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
            "Savings"
        )

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # -------------------------
        # VALIDATION
        # -------------------------

        if not name:

            flash(
                "Please enter your name.",
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

        if account_type not in [
            "Savings",
            "Current"
        ]:

            account_type = "Savings"

        conn = get_connection()

        try:

            cur = conn.cursor()

            # -------------------------
            # GENERATE ACCOUNT NUMBER
            # -------------------------

            cur.execute("""
                SELECT account_no
                FROM users
                WHERE account_no ~ '^[0-9]+$'
                ORDER BY account_no::BIGINT DESC
                LIMIT 1
            """)

            last_account = cur.fetchone()

            if last_account:

                new_account = str(
                    int(
                        last_account["account_no"]
                    ) + 1
                )

            else:

                new_account = "100001"

            # -------------------------
            # CHECK ACCOUNT
            # -------------------------

            cur.execute("""
                SELECT account_no
                FROM users
                WHERE account_no = %s
            """, (
                new_account,
            ))

            while cur.fetchone():

                new_account = str(
                    int(new_account) + 1
                )

                cur.execute("""
                    SELECT account_no
                    FROM users
                    WHERE account_no = %s
                """, (
                    new_account,
                ))

            # -------------------------
            # CREATE USER
            # -------------------------

            cur.execute("""
                INSERT INTO users (
                    account_no,
                    name,
                    email,
                    phone,
                    account_type,
                    password_hash,
                    balance
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                new_account,
                name,
                email,
                phone,
                account_type,
                generate_password_hash(
                    password
                ),
                Decimal("0.00")
            ))

            conn.commit()

            return render_template(
                "register.html",
                created_account=new_account
            )

        except Exception as e:

            conn.rollback()

            print(
                "Registration Error:",
                e
            )

            flash(
                "Unable to create account. Please try again.",
                "error"
            )

            return render_template(
                "register.html"
            )

        finally:

            conn.close()

    return render_template(
        "register.html"
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    account_no = session[
        "account_no"
    ]

    conn = get_connection()

    try:

        cur = conn.cursor()

        # -------------------------
        # USER
        # -------------------------

        cur.execute("""
            SELECT
                id,
                account_no,
                name,
                email,
                phone,
                account_type,
                password_hash,
                balance,
                created_at
            FROM users
            WHERE account_no = %s
        """, (
            account_no,
        ))

        user = cur.fetchone()

        if not user:

            session.clear()

            return redirect(
                url_for("login")
            )

        # -------------------------
        # TRANSACTIONS
        # -------------------------

        cur.execute("""
            SELECT
                transaction_id,
                account_no,
                sender_account,
                receiver_account,
                amount,
                transaction_type,
                title,
                description,
                created_at
            FROM transactions
            WHERE account_no = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (
            account_no,
        ))

        rows = cur.fetchall()

        transactions = []

        for row in rows:

            created_at = row[
                "created_at"
            ]

            if created_at:

                date_text = created_at.strftime(
                    "%d %b %Y, %I:%M %p"
                )

            else:

                date_text = ""

            amount = Decimal(
                row["amount"]
            )

            if row["transaction_type"] in [
                "deposit",
                "TRANSFER_RECEIVED"
            ]:

                amount_text = (
                    f"+₹{amount:,.2f}"
                )

            else:

                amount_text = (
                    f"-₹{amount:,.2f}"
                )

            transactions.append({

                "title": row["title"],

                "amount": amount_text,

                "type": row[
                    "transaction_type"
                ],

                "date": date_text,

                "transaction_id":
                    row["transaction_id"],

                "description":
                    row["description"],

                "sender_account":
                    row["sender_account"],

                "receiver_account":
                    row["receiver_account"]

            })

        # Convert database row to normal dict
        user = dict(user)

        balance = float(
            user["balance"]
        )

        return render_template(
            "dashboard.html",
            user=user,
            balance=balance,
            transactions=transactions
        )

    finally:

        conn.close()


# =========================================================
# DEPOSIT
# =========================================================

@app.route(
    "/deposit",
    methods=["POST"]
)
@login_required
def deposit():

    try:

        amount = Decimal(
            request.form.get(
                "amount",
                "0"
            )
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError
    ):

        amount = Decimal("0")

    if amount <= 0:

        flash(
            "Enter a valid amount.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )

    amount = amount.quantize(
        Decimal("0.01")
    )

    account_no = session[
        "account_no"
    ]

    conn = get_connection()

    try:

        cur = conn.cursor()

        # Lock account row
        cur.execute("""
            SELECT balance
            FROM users
            WHERE account_no = %s
            FOR UPDATE
        """, (
            account_no,
        ))

        user = cur.fetchone()

        if not user:

            conn.rollback()

            flash(
                "Account not found.",
                "error"
            )

            return redirect(
                url_for("logout")
            )

        # Update balance
        cur.execute("""
            UPDATE users
            SET balance = balance + %s
            WHERE account_no = %s
        """, (
            amount,
            account_no
        ))

        transaction_id = (
            "TXN-" +
            uuid.uuid4().hex[:12].upper()
        )

        # Save transaction
        cur.execute("""
            INSERT INTO transactions (
                transaction_id,
                account_no,
                sender_account,
                receiver_account,
                amount,
                transaction_type,
                title,
                description
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            transaction_id,
            account_no,
            None,
            account_no,
            amount,
            "deposit",
            "Cash Deposit",
            "Cash deposited into account"
        ))

        conn.commit()

        flash(
            f"₹{amount:,.2f} deposited successfully.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "Deposit Error:",
            e
        )

        flash(
            "Deposit failed.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for("dashboard")
    )


# =========================================================
# WITHDRAW
# =========================================================

@app.route(
    "/withdraw",
    methods=["POST"]
)
@login_required
def withdraw():

    try:

        amount = Decimal(
            request.form.get(
                "amount",
                "0"
            )
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError
    ):

        amount = Decimal("0")

    if amount <= 0:

        flash(
            "Enter a valid amount.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )

    amount = amount.quantize(
        Decimal("0.01")
    )

    account_no = session[
        "account_no"
    ]

 
