from flask import abort, g, redirect, session, url_for

from db import query_one

HOME_ENDPOINT = {
    "admin": "admin.dashboard",
    "faculty": "faculty.dashboard",
    "student": "student.dashboard",
}


def load_current_user():
    """Runs before every request. The role always comes from the database,
    never from the cookie, so a changed role takes effect immediately."""
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        g.user = query_one(
            "SELECT id, name, email, role FROM users WHERE id = %s", (user_id,)
        )
        if g.user is None:
            session.clear()


def require_role(blueprint, role):
    """Guards EVERY route of a blueprint, so no route can be forgotten."""

    @blueprint.before_request
    def _guard():
        if g.user is None:
            return redirect(url_for("auth.login"))
        if g.user["role"] != role:
            abort(403)
