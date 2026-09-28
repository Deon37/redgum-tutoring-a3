import sqlite3
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
