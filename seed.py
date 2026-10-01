"""Fill the database with demo data.

Usage:  python seed.py
Run schema.sql first. Safe to run once; it refuses to run on a non-empty database.
All demo accounts use the password:  Password@123
"""
import pymysql
from werkzeug.security import generate_password_hash

from config import Config

PASSWORD = "Password@123"

FACULTY = [
    ("Priya Shah", "priya.shah@campus.test", "Computer Science"),
    ("Rahul Mehta", "rahul.mehta@campus.test", "Mathematics"),
]
SUBJECTS = [
    ("CS101", "Programming Fundamentals"),
    ("CS102", "Database Systems"),
    ("MA101", "Discrete Mathematics"),
]
FACULTY_SUBJECTS = {"priya.shah@campus.test": ["CS101", "CS102"],
                    "rahul.mehta@campus.test": ["MA101"]}
STUDENTS = [  # name, email, roll_no, class, subjects
    ("Aarav Patel", "aarav@campus.test", "CS-001", "SY-A", ["CS101", "CS102"]),
    ("Diya Joshi", "diya@campus.test", "CS-002", "SY-A", ["CS101"]),
    ("Kabir Desai", "kabir@campus.test", "CS-003", "SY-A", ["CS101", "CS102", "MA101"]),
    ("Meera Trivedi", "meera@campus.test", "CS-004", "SY-B", ["CS102", "MA101"]),
    ("Nikhil Rana", "nikhil@campus.test", "CS-005", "SY-B", ["MA101"]),
]


def main():
    conn = pymysql.connect(
        host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
        password=Config.DB_PASSWORD, database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
    )
    pw = generate_password_hash(PASSWORD)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM users")
        if cur.fetchone()["n"]:
            print("Database already has users. Nothing was changed.")
            return

        def add_user(name, email, role):
            cur.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (%s,%s,%s,%s)",
                (name, email, pw, role),
            )
            return cur.lastrowid

        ids = {}
        ids["admin@campus.test"] = add_user("Campus Admin", "admin@campus.test", "admin")

        for name, email, dept in FACULTY:
            ids[email] = add_user(name, email, "faculty")
            cur.execute("INSERT INTO faculty (user_id, department) VALUES (%s,%s)", (ids[email], dept))

        subject_ids = {}
        for code, name in SUBJECTS:
            cur.execute("INSERT INTO subjects (code, name) VALUES (%s,%s)", (code, name))
            subject_ids[code] = cur.lastrowid

        for email, codes in FACULTY_SUBJECTS.items():
            for code in codes:
                cur.execute("INSERT INTO faculty_subjects (faculty_id, subject_id) VALUES (%s,%s)",
                            (ids[email], subject_ids[code]))

        for name, email, roll, cls, codes in STUDENTS:
            ids[email] = add_user(name, email, "student")
            cur.execute("INSERT INTO students (user_id, roll_no, class_name) VALUES (%s,%s,%s)",
                        (ids[email], roll, cls))
            for code in codes:
                cur.execute("INSERT INTO enrollments (student_id, subject_id) VALUES (%s,%s)",
                            (ids[email], subject_ids[code]))

        # Leave requests: Aarav -> Priya only; Kabir -> both; Nikhil -> Rahul only
        for email, start, end, reason in [
            ("aarav@campus.test", "2026-10-06", "2026-10-07", "Family function"),
            ("kabir@campus.test", "2026-10-08", "2026-10-08", "Medical appointment"),
            ("nikhil@campus.test", "2026-10-09", "2026-10-10", "Sports tournament"),
        ]:
            cur.execute(
                "INSERT INTO leave_requests (student_id, from_date, to_date, reason) "
                "VALUES (%s,%s,%s,%s)", (ids[email], start, end, reason))

        # Notices: one published by admin, one draft for each faculty member
        cur.execute("INSERT INTO notices (title, body, status, created_by, published_at) "
                    "VALUES (%s,%s,'published',%s,NOW())",
                    ("Mid-semester exams", "Mid-semester exams start on 20 October. Timetable follows.",
                     ids["admin@campus.test"]))
        cur.execute("INSERT INTO notices (title, body, status, created_by) VALUES (%s,%s,'draft',%s)",
                    ("CS101 lab schedule (draft)", "Lab batches will be announced soon.",
                     ids["priya.shah@campus.test"]))
        cur.execute("INSERT INTO notices (title, body, status, created_by) VALUES (%s,%s,'draft',%s)",
                    ("MA101 extra class (draft)", "Extra class on Saturday at 10 am.",
                     ids["rahul.mehta@campus.test"]))
    conn.commit()
    conn.close()
    print("Demo data created. Log in with any demo email and password:", PASSWORD)


if __name__ == "__main__":
    main()
