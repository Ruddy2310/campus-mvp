from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from auth_utils import require_role
from db import execute, query_all, query_one

bp = Blueprint("student", __name__, url_prefix="/student")
require_role(bp, "student")


@bp.route("/dashboard")
def dashboard():
    sid = g.user["id"]
    profile = query_one(
        "SELECT roll_no, class_name FROM students WHERE user_id = %s", (sid,)
    )
    subjects = query_all(
        "SELECT s.code, s.name FROM enrollments e JOIN subjects s ON s.id = e.subject_id "
        "WHERE e.student_id = %s ORDER BY s.code",
        (sid,),
    )
    leaves = query_all(
        "SELECT from_date, to_date, reason, status FROM leave_requests "
        "WHERE student_id = %s ORDER BY created_at DESC, id DESC",
        (sid,),
    )
    notices = query_all(
        "SELECT id, title, published_at FROM notices WHERE status = 'published' "
        "ORDER BY published_at DESC, id DESC LIMIT 5"
    )
    return render_template(
        "student/dashboard.html",
        profile=profile, subjects=subjects, leaves=leaves, notices=notices,
    )


@bp.route("/leave", methods=["POST"])
def apply_leave():
    reason = request.form.get("reason", "").strip()
    try:
        start = datetime.strptime(request.form.get("from_date", ""), "%Y-%m-%d").date()
        end = datetime.strptime(request.form.get("to_date", ""), "%Y-%m-%d").date()
    except ValueError:
        flash("Enter valid dates.", "error")
        return redirect(url_for("student.dashboard"))
    if end < start:
        flash("The end date cannot be before the start date.", "error")
    elif not reason or len(reason) > 500:
        flash("Give a reason (up to 500 characters).", "error")
    else:
        execute(
            "INSERT INTO leave_requests (student_id, from_date, to_date, reason) "
            "VALUES (%s, %s, %s, %s)",
            (g.user["id"], start, end, reason),
        )
        flash("Leave request sent.", "ok")
    return redirect(url_for("student.dashboard"))
