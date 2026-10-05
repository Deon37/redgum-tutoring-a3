# Redgum Tutoring Scheduling System

A web app to manage students, tutors, availability, and session bookings for Redgum Tutoring.

Built with Python 3.12, Flask 3.1.0, SQLite, and server-rendered HTML/CSS.

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

2. Create a virtual environment and install the pinned dependencies (Windows PowerShell)
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Configure the application
```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Open `.env` and paste the generated value after `SECRET_KEY=`. Keep this key private and use a different key on each machine. Copy the example only on first setup so you do not overwrite existing settings.

| Setting | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs Flask session cookies used for feedback messages | Required; startup stops with instructions if missing or blank |
| `FLASK_DEBUG` | Enables Flask's debugger and automatic reload for local development | `false` |

The app reads `.env` from the repository root using [python-dotenv](https://pypi.org/project/python-dotenv/). Existing environment variables take precedence over the file. Debug accepts `true`/`false`, `1`/`0`, `yes`/`no` or `on`/`off`; invalid values stop startup. Enable debugging only for local development. The Flask development server is for local demonstration, not public hosting.

`.env` and local variants such as `.env.local` are ignored by Git. Only `.env` is loaded automatically; `.env.example` is the versioned template and contains no actual key.

4. Create the database and load the demo records
```powershell
.\.venv\Scripts\python.exe init_db.py
```

Run this from the repository root. The setup script replaces any existing `redgum.db` with demo data, so back up any records you want to keep before running it again.

For an existing database, run `init_db.py --upgrade` instead to add the blackout table without resetting records.

5. Run the app
```powershell
.\.venv\Scripts\python.exe app.py
```

6. Open http://localhost:5000 in your browser

On macOS/Linux, create the environment with `python3.12 -m venv .venv`, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`, and copy the example with `cp .env.example .env`.

---

## Tests

After installing the dependencies, run the automated tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests use Python's built-in `unittest` and temporary SQLite databases built from `schema.sql`. They do not change your application's `redgum.db`. Test settings are supplied separately, so a private `.env` file is not required to run the suite.

Configuration tests check missing keys, debug parsing and environment precedence.

`add_tutor()` and `update_tutor()` implement the contract covered by these tests:

- `add_tutor(name, subjects)` saves a new active tutor and commits the change.
- `update_tutor(tutor_id, name, subjects)` saves both supplied fields and commits the change, preserving the ID, active status, other tutors, sessions and availability.
- Subjects use the existing schema's text field, such as `Physics, Chemistry`.

These database tests cover tutor creation and editing; preserving availability records does not test booking validation.

The route tests in `tests/test_tutor_routes.py` cover the implemented GET and POST `/tutors` routes. They use Flask's test client and require no additional dependencies.

The contract is:

- GET displays active tutor names and subjects, following the student-page pattern.
- POST saves a new active tutor and redirects to `/tutors` (302 or 303).
- A missing name or subjects field prevents creation and displays feedback containing `required`. The final response may be 200 or 400.

The tutor detail route tests cover the implemented `GET /tutors/<id>` and `POST /tutors/<id>` routes. Select a tutor's name in the list to edit their details:

- GET displays the requested tutor's name and subjects.
- POST updates only that tutor's name and subjects.
- Missing required fields display `required` feedback (200 or 400) without changes.

Tutor deactivation and booking validation are implemented; these tutor route tests focus on creation and editing.

### Weekly schedule tests

`tests/test_weekly_schedule.py` covers the Tuesday-to-Saturday overview, booking
details for all tutors, selected-week filtering, chronological order and empty
weeks. Open **Schedule** to view the current week in Ipswich time, select a
Tuesday, or use Previous/Next Week. `GET /schedule?week_start=YYYY-MM-DD` accepts
a Tuesday date and displays ISO dates, `HH:MM` times and booking table rows.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_weekly_schedule.py -v
```

### Tutor blackout tests

`tests/test_tutor_blackouts.py` covers saving tutor-specific periods, date
validation, booking refusal, unaffected dates/tutors and refusal of session moves.
Open **Tutors > tutor name > Availability > Blackout Periods** to record inclusive
whole-day start/end dates. Blackouts override weekly availability for bookings
and session moves. Existing bookings remain unchanged. The route is
`GET/POST /tutors/<id>/blackouts`.

For an existing database, run this from the repository root to add the table
while preserving records:

```powershell
.\.venv\Scripts\python.exe init_db.py --upgrade
```

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_tutor_blackouts.py -v
```

### Subject filter tests

`tests/test_subject_filter.py` covers qualified tutor choices, availability,
blackouts, empty results and booking validation. In **Sessions**, enter a subject
and select **Find Tutors**; optionally supply date, start time and length together
(60 or 90 minutes) to filter by availability.
`GET /sessions?subject=Physics` matches whole comma-separated subjects, ignoring
case and surrounding spaces; add `date`, `start_time` and `length_mins` to filter
by availability. The booking form carries `subject` in POST, which rejects
unqualified/inactive tutors. A subject is optional. Availability checks use weekly
windows and blackouts; they do not check existing bookings for time conflicts.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_subject_filter.py -v
```

### Session notes tests

`tests/test_session_notes.py` covers editable notes, persistent saves/updates,
preserved booking details, student learning history and invalid requests.
Open a session through **Sessions > Edit**, then use **Session Notes > Save Notes**.
Use **View Student Progress** to read notes from all tutors, with session dates
and statuses. Saving notes preserves booking details and line breaks. The route
is `POST /sessions/<id>/notes`; a missing field returns 400 and an unknown session
returns 404. The existing schema already has `notes`, so no additional migration is needed.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_session_notes.py -v
```

All 46 tests pass, including the four session-notes tests.

## Project Structure

| File / Folder | Purpose |
|---|---|
| `app.py` | All Flask routes |
| `config.py` | Loads and validates the secret key and debug setting |
| `.env.example` | Safe configuration template to copy on first setup |
| `database.py` | Database connection and query functions |
| `init_db.py` | Creates demo data; `--upgrade` adds missing tables without resetting records |
| `schema.sql` | Table definitions |
| `seed.sql` | Demo records loaded during database setup |
| `requirements.txt` | Python dependencies |
| `tests/` | Configuration, tutor database/routes, weekly schedule, blackout, subject-filter and session-notes tests |
| `static/style.css` | All styling |
| `templates/` | HTML pages |

---

## Branching

Work on a feature branch for features.

1. Check out develop and pull the latest
2. Create a branch named after what you are building (e.g. feature/student-list, feature/tutor-page)
3. Do your work and commit on that branch
4. Push and open a pull request into main for final changes

---

## Notes

- The database file `redgum.db` is not committed. Run the app and setup commands from the repository root.
- If the schema changes, back up any records you need before running `init_db.py` again; it replaces the database with demo data.
