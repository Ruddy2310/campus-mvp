import pymysql
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from auth_utils import HOME_ENDPOINT
from db import query_one, transaction

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for(HOME_ENDPOINT[g.user["role"]]))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one(
            "SELECT id, role, password_hash FROM users WHERE email = %s", (email,)
        )
        if user and check_password_hash(user["password_hash"], password):
            session.clear()  # new session on login
            session["user_id"] = user["id"]
            return redirect(url_for(HOME_ENDPOINT[user["role"]]))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Student self-signup only. Faculty and admin accounts are created by an
    admin (or the seed script) so nobody can sign up as faculty."""
    if g.user:
        return redirect(url_for(HOME_ENDPOINT[g.user["role"]]))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        roll_no = request.form.get("roll_no", "").strip()
        class_name = request.form.get("class_name", "").strip()

        error = None
        if not (name and email and roll_no and class_name):
            error = "Fill in every field."
        elif "@" not in email or len(email) > 150:
            error = "Enter a valid email address."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif len(name) > 100 or len(roll_no) > 30 or len(class_name) > 50:
            error = "One of the fields is too long."

        if error is None:
            try:
                with transaction() as cur:
                    cur.execute(
                        "INSERT INTO users (name, email, password_hash, role) "
                        "VALUES (%s, %s, %s, 'student')",
                        (name, email, generate_password_hash(password)),
                    )
                    cur.execute(
                        "INSERT INTO students (user_id, roll_no, class_name) "
                        "VALUES (%s, %s, %s)",
                        (cur.lastrowid, roll_no, class_name),
                    )
            except pymysql.err.IntegrityError:
                error = "That email or roll number is already registered."
            else:
                flash("Account created. You can log in now.", "ok")
                return redirect(url_for("auth.login"))
        flash(error, "error")
    return render_template("signup.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
