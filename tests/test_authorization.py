"""Authorization tests. They need MySQL running with schema.sql loaded and
`python seed.py` already executed (they read the demo data, they do not change it).

Run:  pytest -v
"""
import pymysql
import pytest

from app import create_app
from config import Config
from db import query_one

TOKEN = "test-token"


@pytest.fixture(scope="module")
def app():
    application = create_app()
    application.config["TESTING"] = True
    try:
        with application.app_context():
            if not query_one("SELECT id FROM users WHERE email = 'priya.shah@campus.test'"):
                pytest.skip("Run `python seed.py` first.")
    except pymysql.err.OperationalError:
        pytest.skip("MySQL is not reachable; check your .env file.")
    return application


def user_id(app, email):
    with app.app_context():
        return query_one("SELECT id FROM users WHERE email = %s", (email,))["id"]


def scalar(app, sql, params=()):
    with app.app_context():
        return list(query_one(sql, params).values())[0]


def client_for(app, email):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id(app, email)
        sess["_csrf"] = TOKEN
    return client


PRIYA = "priya.shah@campus.test"   # teaches CS101, CS102
RAHUL = "rahul.mehta@campus.test"  # teaches MA101


def test_anonymous_is_redirected_to_login(app):
    response = app.test_client().get("/faculty/dashboard")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_student_cannot_open_faculty_or_admin_pages(app):
    client = client_for(app, "aarav@campus.test")
    assert client.get("/faculty/dashboard").status_code == 403
    assert client.get("/admin/dashboard").status_code == 403


def test_faculty_cannot_open_admin_page(app):
    assert client_for(app, PRIYA).get("/admin/dashboard").status_code == 403


def test_post_without_csrf_token_is_rejected(app):
    client = client_for(app, PRIYA)
    assert client.post("/faculty/notices/new", data={"title": "x", "body": "y"}).status_code == 400


def test_dashboard_shows_only_own_students(app):
    html = client_for(app, PRIYA).get("/faculty/students").get_data(as_text=True)
    assert "Aarav Patel" in html
    assert "Nikhil Rana" not in html  # Nikhil is only in MA101 (Rahul)


def test_assigned_student_count_is_scoped(app):
    # Priya: Aarav, Diya, Kabir, Meera (CS101 + CS102)  -> 4, not all 5 students
    expected = scalar(
        app,
        "SELECT COUNT(DISTINCT e.student_id) FROM enrollments e "
        "JOIN faculty_subjects fs ON fs.subject_id = e.subject_id WHERE fs.faculty_id = %s",
        (user_id(app, PRIYA),),
    )
    assert expected == 4
    html = client_for(app, PRIYA).get("/faculty/dashboard").get_data(as_text=True)
    assert 'class="figure">4<' in html


def test_cannot_mark_attendance_for_other_facultys_subject(app):
    ma101 = scalar(app, "SELECT id FROM subjects WHERE code = 'MA101'")
    client = client_for(app, PRIYA)
    assert client.get(f"/faculty/attendance/{ma101}").status_code == 404
    assert client.post(f"/faculty/attendance/{ma101}", data={"_csrf": TOKEN}).status_code == 404


def test_cannot_see_or_edit_other_facultys_draft(app):
    draft_id = scalar(app, "SELECT id FROM notices WHERE title LIKE 'MA101 extra class%%'")
    client = client_for(app, PRIYA)
    assert client.get(f"/faculty/notices/{draft_id}").status_code == 404
    assert client.get(f"/faculty/notices/{draft_id}/edit").status_code == 404
    assert client.post(f"/faculty/notices/{draft_id}/edit",
                       data={"_csrf": TOKEN, "title": "hacked", "body": "x"}).status_code == 404
    html = client.get("/faculty/notices").get_data(as_text=True)
    assert "MA101 extra class" not in html


def test_published_notice_is_readable_but_not_editable(app):
    pub_id = scalar(app, "SELECT id FROM notices WHERE status = 'published' LIMIT 1")
    client = client_for(app, PRIYA)
    assert client.get(f"/faculty/notices/{pub_id}").status_code == 200
    assert client.get(f"/faculty/notices/{pub_id}/edit").status_code == 403


def test_leave_requests_are_scoped_to_my_students(app):
    nikhil_leave = scalar(
        app, "SELECT lr.id FROM leave_requests lr JOIN users u ON u.id = lr.student_id "
             "WHERE u.email = 'nikhil@campus.test'")
    client = client_for(app, PRIYA)
    html = client.get("/faculty/leaves").get_data(as_text=True)
    assert "Aarav Patel" in html and "Kabir Desai" in html
    assert "Nikhil Rana" not in html
    response = client.post(f"/faculty/leaves/{nikhil_leave}/review",
                           data={"_csrf": TOKEN, "action": "approve"})
    assert response.status_code == 404
    assert scalar(app, "SELECT status FROM leave_requests WHERE id = %s", (nikhil_leave,)) == "pending"
