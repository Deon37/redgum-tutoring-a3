import sqlite3
from datetime import date, datetime, timedelta
from flask import g

DATABASE = 'redgum.db'


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def get_students():
    db = get_db()
    return db.execute(
        'SELECT * FROM students WHERE active = 1 ORDER BY name'
    ).fetchall()


def add_student(name, year_level, contact_name, contact_phone):
    db = get_db()
    db.execute(
        'INSERT INTO students (name, year_level, contact_name, contact_phone) VALUES (?, ?, ?, ?)',
        (name, year_level, contact_name, contact_phone)
    )
    db.commit()


def get_student(student_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM students WHERE id = ?', (student_id,)
    ).fetchone()


def update_student(student_id, name, year_level, contact_name, contact_phone):
    db = get_db()
    with db:
        cursor = db.execute(
            'UPDATE students SET name = ?, year_level = ?, contact_name = ?, contact_phone = ? WHERE id = ?',
            (name, year_level, contact_name, contact_phone, student_id)
        )
        if cursor.rowcount == 0:
            raise ValueError(f'Student {student_id} was not found.')


def deactivate_student(student_id):
    db = get_db()
    db.execute('UPDATE students SET active = 0 WHERE id = ?', (student_id,))
    db.commit()


def search_students(query):
    db = get_db()
    return db.execute(
        'SELECT * FROM students WHERE active = 1 AND name LIKE ? ORDER BY name',
        (f'%{query}%',)
    ).fetchall()


def get_tutors(subject='', date=None, start_time=None, length_mins=None):
    """List active tutors, optionally matching a subject and complete session slot."""
    db = get_db()
    tutors = db.execute(
        'SELECT * FROM tutors WHERE active = 1 ORDER BY name'
    ).fetchall()
    if subject:
        tutors = [tutor for tutor in tutors if tutor_teaches_subject(tutor, subject)]
    if date and start_time and length_mins:
        tutors = [tutor for tutor in tutors
                  if check_availability(tutor['id'], date, start_time, length_mins)[0]]
    return tutors


def tutor_teaches_subject(tutor, subject):
    return subject.strip().casefold() in {
        entry.strip().casefold() for entry in tutor['subjects'].split(',') if entry.strip()
    }


def get_tutor(tutor_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM tutors WHERE id = ?', (tutor_id,)
    ).fetchone()


def _validate_tutor_details(name, subjects):
    for field, value in (('name', name), ('subjects', subjects)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'Tutor {field} is required.')


def add_tutor(name, subjects):
    _validate_tutor_details(name, subjects)
    db = get_db()
    with db:
        db.execute(
            'INSERT INTO tutors (name, subjects) VALUES (?, ?)',
            (name, subjects)
        )


def update_tutor(tutor_id, name, subjects):
    _validate_tutor_details(name, subjects)
    db = get_db()
    with db:
        cursor = db.execute(
            'UPDATE tutors SET name = ?, subjects = ? WHERE id = ?',
            (name, subjects, tutor_id)
        )
        if cursor.rowcount == 0:
            raise ValueError(f'Tutor {tutor_id} was not found.')


def deactivate_tutor(tutor_id):
    db = get_db()
    db.execute('UPDATE tutors SET active = 0 WHERE id = ?', (tutor_id,))
    db.commit()


def get_availability(tutor_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM availability WHERE tutor_id = ? ORDER BY day_of_week, start_time',
        (tutor_id,)
    ).fetchall()


def add_availability(tutor_id, day_of_week, start_time, end_time):
    db = get_db()
    db.execute(
        'INSERT INTO availability (tutor_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)',
        (tutor_id, day_of_week, start_time, end_time)
    )
    db.commit()


def delete_availability(availability_id):
    db = get_db()
    db.execute('DELETE FROM availability WHERE id = ?', (availability_id,))
    db.commit()


def get_blackouts(tutor_id):
    return get_db().execute(
        'SELECT * FROM blackouts WHERE tutor_id = ? ORDER BY start_date, end_date, id',
        (tutor_id,),
    ).fetchall()


def add_blackout(tutor_id, start_date, end_date):
    for field, value in (('start date', start_date), ('end date', end_date)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'Blackout {field} is required.')
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError(f'Blackout {field} must be a valid date (YYYY-MM-DD).') from None
        if parsed.isoformat() != value:
            raise ValueError(f'Blackout {field} must be a valid date (YYYY-MM-DD).')
    if end_date < start_date:
        raise ValueError('Blackout end date must be on or after the start date.')
    if get_tutor(tutor_id) is None:
        raise ValueError('Tutor not found.')
    db = get_db()
    with db:
        db.execute(
            'INSERT INTO blackouts (tutor_id, start_date, end_date) VALUES (?, ?, ?)',
            (tutor_id, start_date, end_date),
        )


def _to_day_name(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%A')


def _session_end(start_time, length_mins):
    dt = datetime.strptime(start_time, '%H:%M') + timedelta(minutes=int(length_mins))
    return dt.strftime('%H:%M')


def get_session(session_id):
    db = get_db()
    return db.execute(
        '''SELECT s.id, s.student_id, s.tutor_id, s.date, s.start_time, s.length_mins, s.status, s.notes,
                  st.name AS student_name, t.name AS tutor_name
           FROM sessions s
           JOIN students st ON st.id = s.student_id
           JOIN tutors t ON t.id = s.tutor_id
           WHERE s.id = ?''',
        (session_id,)
    ).fetchone()


def update_session_notes(session_id, notes):
    """Save notes without changing the session's booking details or status."""
    if not isinstance(notes, str):
        raise ValueError('Session notes must be text.')
    db = get_db()
    with db:
        cursor = db.execute('UPDATE sessions SET notes = ? WHERE id = ?', (notes, session_id))
        if cursor.rowcount == 0:
            raise ValueError('Session not found.')


def get_student_upcoming_sessions(student_id):
    return get_db().execute(
        '''SELECT s.id, s.date, s.start_time, s.length_mins, s.status, s.notes,
                  t.name AS tutor_name
           FROM sessions s
           JOIN tutors t ON t.id = s.tutor_id
           WHERE s.student_id = ?
           AND s.date >= date('now')
           AND s.status = 'booked'
           ORDER BY s.date, s.start_time, s.id''',
        (student_id,),
    ).fetchall()


def get_student_past_sessions(student_id):
    return get_db().execute(
        '''SELECT s.id, s.date, s.start_time, s.length_mins, s.status, s.notes,
                  t.name AS tutor_name
           FROM sessions s
           JOIN tutors t ON t.id = s.tutor_id
           WHERE s.student_id = ?
           AND NOT (s.date >= date('now') AND s.status = 'booked')
           ORDER BY s.date DESC, s.start_time DESC, s.id DESC''',
        (student_id,),
    ).fetchall()


def cancel_session(session_id):
    db = get_db()
    db.execute('UPDATE sessions SET status = ? WHERE id = ?', ('cancelled', session_id))
    db.commit()


_VALID_STATUSES = ('booked', 'attended', 'no-show', 'cancelled', 'cancelled-late')


def update_session_status(session_id, status):
    if status not in _VALID_STATUSES:
        raise ValueError(f'Invalid status: {status}')
    db = get_db()
    with db:
        cursor = db.execute('UPDATE sessions SET status = ? WHERE id = ?', (status, session_id))
        if cursor.rowcount == 0:
            raise ValueError('Session not found.')


def update_session(session_id, date, start_time, length_mins):
    db = get_db()
    db.execute(
        'UPDATE sessions SET date = ?, start_time = ?, length_mins = ? WHERE id = ?',
        (date, start_time, length_mins, session_id)
    )
    db.commit()


def check_availability(tutor_id, date, start_time, length_mins):
    booking_date = datetime.strptime(date, '%Y-%m-%d')
    day = booking_date.strftime('%A')
    end_time = _session_end(start_time, length_mins)
    db = get_db()
    blackout = db.execute(
        'SELECT start_date, end_date FROM blackouts '
        'WHERE tutor_id = ? AND start_date <= ? AND end_date >= ? '
        'ORDER BY start_date, id LIMIT 1',
        (tutor_id, booking_date.date().isoformat(), booking_date.date().isoformat()),
    ).fetchone()
    if blackout is not None:
        tutor = get_tutor(tutor_id)
        return False, (f'{tutor["name"]} is away during a blackout from '
                       f'{blackout["start_date"]} to {blackout["end_date"]}.')
    existing = db.execute(
        '''SELECT start_time, length_mins FROM sessions
           WHERE tutor_id = ? AND date = ? AND status = 'booked' ''',
        (tutor_id, booking_date.date().isoformat()),
    ).fetchall()
    for s in existing:
        if s['start_time'] < end_time and _session_end(s['start_time'], s['length_mins']) > start_time:
            tutor = get_tutor(tutor_id)
            return False, f'{tutor["name"]} already has a session booked at that time.'

    windows = db.execute(
        'SELECT * FROM availability WHERE tutor_id = ? AND day_of_week = ?',
        (tutor_id, day)
    ).fetchall()
    if not windows:
        tutor = get_tutor(tutor_id)
        return False, f'{tutor["name"]} is not available on {day}s.'
    for w in windows:
        if w['start_time'] <= start_time < end_time <= w['end_time']:
            return True, None
    tutor = get_tutor(tutor_id)
    for w in windows:
        if end_time > w['end_time'] and start_time >= w['start_time']:
            return False, f'{tutor["name"]} is not available past {w["end_time"]} on {day}s.'
        if start_time < w['start_time']:
            return False, f'{tutor["name"]} is not available before {w["start_time"]} on {day}s.'
    return False, f'{tutor["name"]} is not available at that time on {day}s.'


def book_session(student_id, tutor_id, date, start_time, length_mins):
    db = get_db()
    db.execute(
        'INSERT INTO sessions (student_id, tutor_id, date, start_time, length_mins) VALUES (?, ?, ?, ?, ?)',
        (student_id, tutor_id, date, start_time, length_mins)
    )
    db.commit()


def get_sessions():
    db = get_db()
    return db.execute(
        '''SELECT s.id, st.name AS student_name, t.name AS tutor_name,
                  s.date, s.start_time, s.length_mins, s.status
           FROM sessions s
           JOIN students st ON st.id = s.student_id
           JOIN tutors t ON t.id = s.tutor_id
           ORDER BY s.date DESC, s.start_time DESC'''
    ).fetchall()


def get_tutor_upcoming_sessions(tutor_id):
    return get_db().execute(
        '''SELECT s.id, s.date, s.start_time, s.length_mins, s.status,
                  st.name AS student_name, st.year_level
           FROM sessions s
           JOIN students st ON st.id = s.student_id
           WHERE s.tutor_id = ?
           AND s.date >= date('now')
           AND s.status = 'booked'
           ORDER BY s.date, s.start_time, s.id''',
        (tutor_id,),
    ).fetchall()


def get_sessions_by_date(date):
    return get_db().execute(
        '''SELECT s.id, st.name AS student_name, t.name AS tutor_name,
                  s.date, s.start_time, s.length_mins, s.status
           FROM sessions s
           JOIN students st ON st.id = s.student_id
           JOIN tutors t ON t.id = s.tutor_id
           WHERE s.date = ?
           ORDER BY s.start_time, s.id''',
        (date,),
    ).fetchall()


def get_week_sessions(start_date, end_date):
    """Return all tutors' sessions within the inclusive schedule date range."""
    return get_db().execute(
        '''SELECT s.id, st.name AS student_name, t.name AS tutor_name,
                  s.date, s.start_time, s.length_mins, s.status
           FROM sessions s
           JOIN students st ON st.id = s.student_id
           JOIN tutors t ON t.id = s.tutor_id
           WHERE s.date BETWEEN ? AND ?
           ORDER BY s.date, s.start_time, s.id''',
        (start_date, end_date),
    ).fetchall()
