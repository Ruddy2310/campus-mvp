"""Faculty routes.

AUTHORIZATION RULE: every query below is filtered by the logged-in faculty
member's id (g.user["id"], taken from the server-side session). Subjects,
students and leave requests are reached ONLY through the faculty_subjects ->
enrollments relationship. Nothing is fetched broadly and hidden in the template.
"""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from auth_utils import require_role
from db import execute, query_all, query_one, transaction

bp = Blueprint("faculty", __name__, url_prefix="/faculty")
require_role(bp, "faculty")


# ---------- helpers: each one enforces ownership / assignment ----------

def get_my_subject_or_404(subject_id):
    subject = query_one(
        "SELECT s.id, s.code, s.name FROM subjects s "
        "JOIN faculty_subjects fs ON fs.subject_id = s.id "
        "WHERE s.id = %s AND fs.faculty_id = %s",
        (subject_id, g.user["id"]),
    )
    if subject is None:
        abort(404)  # 404 (not 403) so we do not reveal that the subject exists
    return subject


def relevant_leaves(leave_id=None, limit=None):
    """Pending leave requests of students enrolled in MY subjects."""
    sql = (
        "SELECT DISTINCT lr.id, lr.from_date, lr.to_date, lr.reason, lr.created_at, "
        "       u.name AS student_name, st.roll_no "
        "FROM leave_requests lr "
        "JOIN users u ON u.id = lr.student_id "
        "JOIN students st ON st.user_id = lr.student_id "
        "JOIN enrollments e ON e.student_id = lr.student_id "
        "JOIN faculty_subjects fs ON fs.subject_id = e.subject_id AND fs.faculty_id = %s "
        "WHERE lr.status = 'pending' "
    )
    params = [g.user["id"]]
    if leave_id is not None:
        sql += "AND lr.id = %s "
        params.append(leave_id)
    sql += "ORDER BY lr.created_at, lr.id "
    if limit:
        sql += "LIMIT %s"
        params.append(limit)
    return query_all(sql, params)


def get_visible_notice_or_404(notice_id):
    """Published notices, plus my own drafts. Other people's drafts do not exist."""
    notice = query_one(
        "SELECT n.id, n.title, n.body, n.status, n.created_by, n.created_at, "
        "       n.published_at, u.name AS author "
        "FROM notices n JOIN users u ON u.id = n.created_by "
        "WHERE n.id = %s AND (n.status = 'published' OR n.created_by = %s)",
        (notice_id, g.user["id"]),
    )
    if notice is None:
        abort(404)
    return notice


def get_editable_notice_or_404(notice_id):
    notice = get_visible_notice_or_404(notice_id)
    if notice["created_by"] != g.user["id"] or notice["status"] != "draft":
        abort(403)  # published notices are read-only; others' notices are not mine
    return notice


# ---------- dashboard ----------

@bp.route("/dashboard")
def dashboard():
    fid = g.user["id"]
    profile = query_one("SELECT department FROM faculty WHERE user_id = %s", (fid,))

    student_count = query_one(
        "SELECT COUNT(DISTINCT e.student_id) AS n "
        "FROM enrollments e JOIN faculty_subjects fs ON fs.subject_id = e.subject_id "
        "WHERE fs.faculty_id = %s",
        (fid,),
    )["n"]

    attendance_today = query_all(
        "SELECT s.id AS subject_id, s.code, s.name, sess.id AS session_id, "
        "       COALESCE(SUM(r.status = 'present'), 0) AS present, "
        "       COALESCE(SUM(r.status = 'absent'), 0)  AS absent "
        "FROM faculty_subjects fs "
        "JOIN subjects s ON s.id = fs.subject_id "
        "LEFT JOIN attendance_sessions sess "
        "       ON sess.subject_id = s.id AND sess.session_date = CURDATE() "
        "LEFT JOIN attendance_records r ON r.session_id = sess.id "
        "WHERE fs.faculty_id = %s "
        "GROUP BY s.id, s.code, s.name, sess.id ORDER BY s.code",
        (fid,),
    )

    pending_leaves = relevant_leaves()

    published = query_all(
        "SELECT n.id, n.title, n.published_at, u.name AS author "
        "FROM notices n JOIN users u ON u.id = n.created_by "
        "WHERE n.status = 'published' ORDER BY n.published_at DESC, n.id DESC LIMIT 5"
    )
    my_drafts = query_all(
        "SELECT id, title, created_at FROM notices "
        "WHERE status = 'draft' AND created_by = %s ORDER BY created_at DESC, id DESC",
        (fid,),
    )

    return render_template(
        "faculty/dashboard.html",
        profile=profile,
        student_count=student_count,
        attendance_today=attendance_today,
        pending_leaves=pending_leaves[:5],
        pending_leave_total=len(pending_leaves),
        published=published,
        my_drafts=my_drafts,
    )


# ---------- assigned students ----------

@bp.route("/students")
def students():
    rows = query_all(
        "SELECT st.user_id, u.name, st.roll_no, st.class_name, "
        "       GROUP_CONCAT(DISTINCT s.code ORDER BY s.code SEPARATOR ', ') AS subject_codes "
        "FROM faculty_subjects fs "
        "JOIN enrollments e ON e.subject_id = fs.subject_id "
        "JOIN students st ON st.user_id = e.student_id "
        "JOIN users u ON u.id = st.user_id "
        "JOIN subjects s ON s.id = fs.subject_id "
        "WHERE fs.faculty_id = %s "
        "GROUP BY st.user_id, u.name, st.roll_no, st.class_name "
        "ORDER BY st.roll_no",
        (g.user["id"],),
    )
    return render_template("faculty/students.html", students=rows)


# ---------- attendance ----------

@bp.route("/attendance")
def attendance_index():
    subjects = query_all(
        "SELECT s.id, s.code, s.name FROM subjects s "
        "JOIN faculty_subjects fs ON fs.subject_id = s.id "
        "WHERE fs.faculty_id = %s ORDER BY s.code",
        (g.user["id"],),
    )
    return render_template("faculty/attendance_index.html", subjects=subjects)


@bp.route("/attendance/<int:subject_id>", methods=["GET", "POST"])
def attendance(subject_id):
    subject = get_my_subject_or_404(subject_id)  # checked on GET *and* POST
    roster = query_all(
        "SELECT u.id, u.name, st.roll_no FROM enrollments e "
        "JOIN users u ON u.id = e.student_id "
        "JOIN students st ON st.user_id = u.id "
        "WHERE e.subject_id = %s ORDER BY st.roll_no",
        (subject_id,),
    )

    if request.method == "POST":
        marks = {}
        for student in roster:  # only enrolled students; injected ids are ignored
            value = request.form.get(f"status_{student['id']}")
            if value not in ("present", "absent"):
                abort(400, "Mark every student as present or absent.")
            marks[student["id"]] = value

        with transaction() as cur:
            cur.execute(
                "INSERT INTO attendance_sessions (subject_id, session_date, marked_by) "
                "VALUES (%s, CURDATE(), %s) "
                "ON DUPLICATE KEY UPDATE marked_by = VALUES(marked_by)",
                (subject_id, g.user["id"]),
            )
            cur.execute(
                "SELECT id FROM attendance_sessions "
                "WHERE subject_id = %s AND session_date = CURDATE()",
                (subject_id,),
            )
            session_id = cur.fetchone()["id"]
            for student_id, value in marks.items():
                cur.execute(
                    "INSERT INTO attendance_records (session_id, student_id, status) "
                    "VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE status = VALUES(status)",
                    (session_id, student_id, value),
                )
        flash(f"Attendance saved for {subject['code']}.", "ok")
        return redirect(url_for("faculty.dashboard"))

    existing = query_all(
        "SELECT r.student_id, r.status FROM attendance_records r "
        "JOIN attendance_sessions sess ON sess.id = r.session_id "
        "WHERE sess.subject_id = %s AND sess.session_date = CURDATE()",
        (subject_id,),
    )
    current = {row["student_id"]: row["status"] for row in existing}
    today = query_one("SELECT CURDATE() AS d")["d"]
    return render_template(
        "faculty/attendance.html",
        subject=subject, roster=roster, current=current, today=today,
    )


# ---------- leave requests ----------

@bp.route("/leaves")
def leaves():
    return render_template("faculty/leaves.html", leaves=relevant_leaves())


@bp.route("/leaves/<int:leave_id>/review", methods=["POST"])
def review_leave(leave_id):
    if not relevant_leaves(leave_id=leave_id):
        abort(404)  # not pending, or not a student of mine
    action = request.form.get("action")
    if action not in ("approve", "reject"):
        abort(400)
    new_status = "approved" if action == "approve" else "rejected"
    changed, _ = execute(
        "UPDATE leave_requests SET status = %s, reviewed_by = %s, reviewed_at = NOW() "
        "WHERE id = %s AND status = 'pending'",
        (new_status, g.user["id"], leave_id),
    )
    flash("Leave request " + new_status + "." if changed else "Already reviewed.", "ok")
    return redirect(url_for("faculty.leaves"))


# ---------- notices ----------

@bp.route("/notices")
def notices():
    published = query_all(
        "SELECT n.id, n.title, n.published_at, u.name AS author "
        "FROM notices n JOIN users u ON u.id = n.created_by "
        "WHERE n.status = 'published' ORDER BY n.published_at DESC, n.id DESC"
    )
    my_drafts = query_all(
        "SELECT id, title, created_at FROM notices "
        "WHERE status = 'draft' AND created_by = %s ORDER BY created_at DESC, id DESC",
        (g.user["id"],),
    )
    return render_template("faculty/notices.html", published=published, my_drafts=my_drafts)


@bp.route("/notices/<int:notice_id>")
def notice_detail(notice_id):
    return render_template("faculty/notice_detail.html", notice=get_visible_notice_or_404(notice_id))


def _read_notice_form():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    if not title or not body:
        return None, None, "Title and body are required."
    if len(title) > 200:
        return None, None, "Title must be 200 characters or fewer."
    return title, body, None


@bp.route("/notices/new", methods=["GET", "POST"])
def notice_new():
    if request.method == "POST":
        title, body, error = _read_notice_form()
        if error:
            flash(error, "error")
            return render_template("faculty/notice_form.html", notice=None, form=request.form)
        publish = request.form.get("action") == "publish"
        execute(
            "INSERT INTO notices (title, body, status, created_by, published_at) "
            "VALUES (%s, %s, %s, %s, " + ("NOW()" if publish else "NULL") + ")",
            (title, body, "published" if publish else "draft", g.user["id"]),
        )
        flash("Notice published." if publish else "Draft saved.", "ok")
        return redirect(url_for("faculty.notices"))
    return render_template("faculty/notice_form.html", notice=None, form={})


@bp.route("/notices/<int:notice_id>/edit", methods=["GET", "POST"])
def notice_edit(notice_id):
    notice = get_editable_notice_or_404(notice_id)  # owner AND still a draft
    if request.method == "POST":
        title, body, error = _read_notice_form()
        if error:
            flash(error, "error")
            return render_template("faculty/notice_form.html", notice=notice, form=request.form)
        publish = request.form.get("action") == "publish"
        execute(
            "UPDATE notices SET title = %s, body = %s, status = %s, published_at = "
            + ("NOW()" if publish else "NULL")
            + " WHERE id = %s AND created_by = %s AND status = 'draft'",
            (title, body, "published" if publish else "draft", notice_id, g.user["id"]),
        )
        flash("Notice published." if publish else "Draft saved.", "ok")
        return redirect(url_for("faculty.notices"))
    return render_template("faculty/notice_form.html", notice=notice, form=notice)
