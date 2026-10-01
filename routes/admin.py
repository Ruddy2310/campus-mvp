from flask import Blueprint, render_template

from auth_utils import require_role
from db import query_one

bp = Blueprint("admin", __name__, url_prefix="/admin")
require_role(bp, "admin")


@bp.route("/dashboard")
def dashboard():
    counts = query_one(
        "SELECT "
        "  (SELECT COUNT(*) FROM users WHERE role = 'student') AS students, "
        "  (SELECT COUNT(*) FROM users WHERE role = 'faculty') AS faculty, "
        "  (SELECT COUNT(*) FROM subjects) AS subjects, "
        "  (SELECT COUNT(*) FROM leave_requests WHERE status = 'pending') AS pending_leaves"
    )
    return render_template("admin/dashboard.html", counts=counts)
