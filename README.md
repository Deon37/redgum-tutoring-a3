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
