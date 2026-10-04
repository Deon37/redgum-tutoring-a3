import sqlite3
from datetime import datetime, timedelta
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


def get_tutors():
    db = get_db()
    return db.execute(
        'SELECT * FROM tutors WHERE active = 1 ORDER BY name'
    ).fetchall()


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


def _to_day_name(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%A')


def _session_end(start_time, length_mins):
    dt = datetime.strptime(start_time, '%H:%M') + timedelta(minutes=int(length_mins))
    return dt.strftime('%H:%M')


def check_availability(tutor_id, date, start_time, length_mins):
    day = _to_day_name(date)
    end_time = _session_end(start_time, length_mins)
    db = get_db()
    windows = db.execute(
        'SELECT * FROM availability WHERE tutor_id = ? AND day_of_week = ?',
        (tutor_id, day)
    ).fetchall()
    if not windows:
        tutor = get_tutor(tutor_id)
        return False, f'{tutor["name"]} is not available on {day}s.'
    for w in windows:
        if w['start_time'] <= start_time and w['end_time'] >= end_time:
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
