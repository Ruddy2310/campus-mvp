# Campus MVP: Faculty Dashboard

A web application for managing day-to-day academic work at a college. This first version (MVP) focuses on the **Faculty Dashboard**: a faculty member sees only *their own* classes, students, attendance, leave requests and notices.

Built as a final-year project with **Flask + MySQL**.

> **Core idea:** the faculty dashboard shows *"my assigned academic work + campus-published information"*, not *"all university data"*.

---

## Features (current phase)

| Area | What works |
|---|---|
| Authentication | Login, logout, student signup, password hashing, CSRF protection |
| Roles | `admin`, `faculty`, `student`, enforced on the server for every route |
| Faculty dashboard | Name and department, assigned-student count, today's attendance per subject, pending leave requests, recent published notices, own drafts |
| Attendance | Mark and edit today's attendance for assigned subjects only |
| Assigned students | List of students enrolled in the faculty member's subjects |
| Leave requests | Approve or reject pending requests of assigned students only |
| Notices | Create, edit, publish own drafts; read published notices |
| Student side (minimal) | See subjects and notices, apply for leave, track leave status |
| Admin side (minimal) | Overview counts (full admin tools are planned) |

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS (no framework), Jinja2 templates |
| Backend | Python 3.10+, Flask |
| Database | MySQL 8 (PyMySQL driver, plain SQL) |
| Auth | Flask sessions, Werkzeug password hashing |
| Tests | pytest |
| Version control | Git and GitHub |

## Project structure

```
campus-mvp/
├── app.py              # app factory, CSRF check, error pages
├── config.py           # settings read from .env
├── db.py               # MySQL helpers (query_all, query_one, execute, transaction)
├── auth_utils.py       # loads the current user, role guard for blueprints
├── routes/
│   ├── auth.py         # login, signup, logout
│   ├── faculty.py      # faculty dashboard and all faculty actions
│   ├── student.py      # student dashboard, leave application
│   └── admin.py        # admin overview
├── templates/          # Jinja2 pages (faculty/, student/, admin/)
├── static/style.css
├── schema.sql          # database tables
├── seed.py             # demo data
├── tests/test_authorization.py
├── requirements.txt
└── .env.example
```

## Getting started

**Requirements:** Python 3.10+, MySQL 8, Git.

```bash
# 1. Get the code
git clone <your-repo-url>
cd campus-mvp

# 2. Virtual environment and dependencies
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Settings
cp .env.example .env              # then edit .env: set DB_PASSWORD and a long random SECRET_KEY

# 4. Create the database and tables
mysql -u root -p < schema.sql

# 5. Add demo data
python seed.py

# 6. Run
python app.py                     # open http://127.0.0.1:5000
```

### Demo accounts

Every account uses the password `Password@123`.

| Role | Email | Teaches / notes |
|---|---|---|
| Admin | admin@campus.test | |
| Faculty | priya.shah@campus.test | CS101, CS102 |
| Faculty | rahul.mehta@campus.test | MA101 |
| Student | aarav@campus.test | CS101, CS102 |
| Student | kabir@campus.test | CS101, CS102, MA101 (taught by both faculty) |
| Student | nikhil@campus.test | MA101 only |

Try this: log in as Priya. You see Aarav and Kabir's leave requests but not Nikhil's. Log in as Rahul and you see Kabir's and Nikhil's.

## Database design

```
users ──┬── students ──┬── enrollments ──── subjects ──── faculty_subjects ──── faculty ── users
        │              ├── attendance_records ── attendance_sessions ── subjects
        │              └── leave_requests
        └── notices (created_by)
```

The whole faculty permission model rests on **two link tables**:

* `faculty_subjects(faculty_id, subject_id)`: which faculty member teaches which subject
* `enrollments(student_id, subject_id)`: which student is enrolled in which subject

A student is "assigned" to a faculty member when both tables share a `subject_id`.

## How authorization works

Rules from the spec, and where they are enforced:

| Rule | Enforced by |
|---|---|
| Only faculty can open `/faculty/*` | `require_role(bp, "faculty")` runs before every route in the blueprint (`auth_utils.py`) |
| The role is trusted from the database, not the cookie | `load_current_user()` reloads the user on every request |
| Faculty ID never comes from the browser | All queries use `g.user["id"]` from the server-side session |
| Count only my students | SQL joins `faculty_subjects` to `enrollments`, filtered by my ID |
| Attendance only for my subjects | `get_my_subject_or_404()` runs on both GET and POST |
| Leave requests only for my students | `relevant_leaves()` joins through enrollments and my subjects; the review route reuses it |
| Never see another faculty member's drafts | `get_visible_notice_or_404()` only returns published notices or my own drafts |
| Published notices are read-only | `get_editable_notice_or_404()` requires owner **and** `status = 'draft'` |

Data is filtered **in SQL**, never fetched broadly and hidden in the template.

Extra security measures: parameterized queries (no SQL injection), Jinja auto-escaping (no XSS), CSRF token on every POST, hashed passwords, a fresh session at login, and faculty/admin accounts that cannot be created by public signup.

### Design decisions and assumptions

These points were not fixed by the spec, so they are documented here and easy to change:

1. **Relevant leave request** = pending request from a student enrolled in at least one of my subjects.
2. **First review is final.** If a student is in two faculty members' classes, whoever reviews first decides; the request then disappears for the other.
3. **Faculty can publish their own drafts** (the Publish button). Change this if only admins should publish.
4. **404 for other people's data, 403 for role/permission errors.** Returning 404 for another faculty member's subject or draft avoids revealing that it exists.
5. **One attendance session per subject per day.** Saving again the same day edits it. The dashboard status is either *Marked* or *Not marked*.
6. **Faculty and admin accounts are created by an admin or the seed script**, never by public signup.

## Running the tests

The tests check the permission boundaries: Faculty A tries to reach Faculty B's subject, students, leave requests and drafts. They need MySQL running and the seed data loaded.

```bash
pytest -v
```

## Roadmap

- [x] **Phase 1:** schema, login/signup, role guards, project setup
- [x] **Phase 2:** faculty dashboard, notices
- [x] **Phase 3:** attendance, assigned students, leave review
- [ ] **Phase 4:** admin tools (create faculty, subjects, assignments, enrollments), student attendance view, login rate limiting, deployment notes, screenshots and ER diagram

## Limitations (known)

* No login attempt rate limiting yet.
* No password reset.
* Admin screens only show counts; accounts and assignments are set up through `seed.py` or SQL for now.
* Attendance covers "today" only; there is no history view yet.

## License

Educational project. Add the license of your choice.
