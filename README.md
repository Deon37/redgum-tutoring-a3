# Redgum Tutoring Scheduling System

A web app to manage students, tutors, availability, and session bookings for Redgum Tutoring.

Built with Python 3.12, Flask 3.1.0, SQLite, and vanilla HTML/CSS/JS.

---

## Requirements

You need these installed before you start:

- **Python 3.12** (do not install 3.13): https://www.python.org/downloads/
- **Git**: https://git-scm.com/downloads
- Prefer GitHub Desktop? https://desktop.github.com

---

## Setup

1. Clone the repo
```
git clone https://github.com/Deon37/redgum-tutoring-a3.git
cd redgum-tutoring-a3
```

2. Install dependencies
```
pip install flask==3.1.0
```

3. Create the database
```
python init_db.py
```

4. Run the app
```
python app.py
```

5. Open http://localhost:5000 in your browser

---

## Tests

After installing the dependencies, run the tutor database and route tests:

```sh
python -m unittest discover -s tests -v
```

The tests use Python's built-in `unittest` and a temporary SQLite database built from `schema.sql`. They do not read or change your application's `redgum.db`.

`add_tutor()` and `update_tutor()` implement the contract covered by these tests:

- `add_tutor(name, subjects)` saves a new active tutor and commits the change.
- `update_tutor(tutor_id, name, subjects)` saves both supplied fields and commits the change, preserving the ID, active status, other tutors, sessions and availability.
- Subjects use the existing schema's text field, such as `Physics, Chemistry`.

The case study requires creating tutors and changing their names and subjects. Deactivation, booking options and availability window validation are separate work, as preserving availability here does not test the booking availability rule.

The route tests in `tests/test_tutor_routes.py` cover the implemented GET and POST `/tutors` routes. They use Flask's test client and require no additional dependencies.

The contract is:

- GET displays active tutor names and subjects, following the student-page pattern.
- POST saves a new active tutor and redirects to `/tutors` (302 or 303).
- A missing name or subjects field prevents creation and displays feedback containing `required`. The final response may be 200 or 400.

The tutor detail route tests cover the implemented `GET /tutors/<id>` and `POST /tutors/<id>` routes. Select a tutor's name in the list to edit their details:

- GET displays the requested tutor's name and subjects.
- POST updates only that tutor's name and subjects.
- Missing required fields display `required` feedback (200 or 400) without changes.

Deactivation and booking validation remain separate route work.

## Project Structure

| File / Folder | Purpose |
|---|---|
| `app.py` | All Flask routes |
| `database.py` | Database connection and query functions |
| `init_db.py` | Run once to create the database |
| `schema.sql` | Table definitions |
| `requirements.txt` | Python dependencies |
| `static/style.css` | All styling |
| `templates/` | HTML pages |

---

## Branching

Work on a feature branch, never commit directly to main or develop.

1. Check out develop and pull the latest
2. Create a branch named after what you are building (e.g. feature/student-list, feature/tutor-page)
3. Do your work and commit on that branch
4. Push and open a pull request into develop

---

## Notes

- The database file `redgum.db` is not committed. Run `python init_db.py` to create it.
- If the schema changes, delete `redgum.db` and run `python init_db.py` again.
