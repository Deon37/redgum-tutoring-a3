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
