import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from flask import Flask

import database

class TutorDatabaseTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.db_path = Path(temporary_directory.name) / 'test.db'
        database_path = patch.object(database, 'DATABASE', str(self.db_path))
        database_path.start()
        self.addCleanup(database_path.stop)

        app = Flask(__name__)
        database.init_app(app)
        context = app.app_context()
        context.push()
        self.addCleanup(context.pop)
        schema = Path(__file__).resolve().parents[1] / 'schema.sql'
        database.get_db().executescript(schema.read_text(encoding='utf-8'))

    def rows(self, table):
        # A separate connection checks committed, persistent data.
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(
                f'SELECT * FROM {table} ORDER BY id'
            )]

    def seed_tutor(self, name='Tomás Ferreira', subjects='Physics, Chemistry', active=1):
        # Seed directly so update tests do not depend on add_tutor working.
        db = database.get_db()
        cursor = db.execute(
            'INSERT INTO tutors (name, subjects, active) VALUES (?, ?, ?)',
            (name, subjects, active),
        )
        db.commit()
        return cursor.lastrowid

    def test_add_saves_name_subjects_and_defaults_to_active(self):
        database.add_tutor('Tomás Ferreira', 'Physics, Chemistry, Maths Methods')

        tutors = self.rows('tutors')
        self.assertEqual(len(tutors), 1)
        self.assertEqual(tutors[0]['name'], 'Tomás Ferreira')
        self.assertEqual(tutors[0]['subjects'], 'Physics, Chemistry, Maths Methods')
        self.assertEqual(tutors[0]['active'], 1)
        self.assertIsInstance(tutors[0]['id'], int)

    def test_add_preserves_existing_tutors(self):
        self.seed_tutor()
        existing = self.rows('tutors')[0]

        database.add_tutor('Helen Vasquez', 'Senior Mathematics')

        tutors = self.rows('tutors')
        self.assertEqual(len(tutors), 2)
        self.assertEqual(tutors[0], existing)
        self.assertNotEqual(tutors[0]['id'], tutors[1]['id'])

    def test_add_safely_stores_apostrophes_and_sql_like_text(self):
        name = "Sam O'Brien"
        subjects = "Physics'); DROP TABLE tutors; --"

        database.add_tutor(name, subjects)

        tutors = self.rows('tutors')
        self.assertEqual(len(tutors), 1)
        self.assertEqual((tutors[0]['name'], tutors[0]['subjects']), (name, subjects))

    def test_add_rejects_missing_required_details_without_saving(self):
        for field in ('name', 'subjects'):
            for invalid in (None, '', ' \t\n '):
                with self.subTest(field=field, value=invalid):
                    values = {'name': 'Helen Vasquez', 'subjects': 'Maths'}
                    values[field] = invalid
                    before = self.rows('tutors')
                    with self.assertRaisesRegex(ValueError, field):
                        database.add_tutor(**values)
                    self.assertEqual(self.rows('tutors'), before)

    def test_update_can_change_name_subjects_or_both(self):
        for name, subjects in (
            ('Tom Ferreira', 'Physics, Chemistry'),
            ('Tomás Ferreira', 'Maths Methods'),
            ("Tom O'Brien", "Maths'); DROP TABLE tutors; --"),
        ):
            with self.subTest(name=name, subjects=subjects):
                tutor_id = self.seed_tutor()
                database.update_tutor(tutor_id, name, subjects)

                tutor = next(row for row in self.rows('tutors') if row['id'] == tutor_id)
                self.assertEqual(tutor, {
                    'id': tutor_id, 'name': name, 'subjects': subjects, 'active': 1,
                })

    def test_update_does_not_change_another_tutor(self):
        tutor_id = self.seed_tutor()
        self.seed_tutor('Helen Vasquez', 'Maths')
        other = self.rows('tutors')[1]

        database.update_tutor(tutor_id, 'Tom Ferreira', 'Physics')

        self.assertEqual(len(self.rows('tutors')), 2)
        self.assertEqual(self.rows('tutors')[1], other)

    def test_update_does_not_reactivate_an_inactive_tutor(self):
        tutor_id = self.seed_tutor(active=0)

        database.update_tutor(tutor_id, 'Tom Ferreira', 'Physics')

        self.assertEqual(self.rows('tutors')[0]['active'], 0)

    def test_update_preserves_sessions_and_availability(self):
        tutor_id = self.seed_tutor()
        db = database.get_db()
        student_id = db.execute(
            'INSERT INTO students (name, year_level, contact_name, contact_phone) '
            'VALUES (?, ?, ?, ?)', ('Example Student', 11, 'Example Parent', '0400000000')
        ).lastrowid
        db.execute(
            'INSERT INTO sessions (student_id, tutor_id, date, start_time, length_mins, status) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (student_id, tutor_id, '2026-08-11', '15:30', 60, 'attended'),
        )
        db.execute(
            'INSERT INTO availability (tutor_id, day_of_week, start_time, end_time) '
            'VALUES (?, ?, ?, ?)', (tutor_id, 'Tuesday', '15:30', '19:00'),
        )
        db.commit()
        sessions = self.rows('sessions')
        availability = self.rows('availability')

        database.update_tutor(tutor_id, 'Tom Ferreira', 'Physics')

        self.assertEqual(self.rows('sessions'), sessions)
        self.assertEqual(self.rows('availability'), availability)

    def test_update_rejects_missing_details_without_changing_record(self):
        tutor_id = self.seed_tutor()
        before = self.rows('tutors')
        for field in ('name', 'subjects'):
            for invalid in (None, '', ' \t\n '):
                with self.subTest(field=field, value=invalid):
                    values = {'name': 'Changed Name', 'subjects': 'Changed Subject'}
                    values[field] = invalid
                    with self.assertRaisesRegex(ValueError, field):
                        database.update_tutor(tutor_id, **values)
                    self.assertEqual(self.rows('tutors'), before)

    def test_update_unknown_id_reports_error_without_changing_tutors(self):
        tutor_id = self.seed_tutor()
        before = self.rows('tutors')

        with self.assertRaisesRegex(ValueError, '(?i)tutor'):
            database.update_tutor(tutor_id + 1, 'Missing Tutor', 'Maths')

        self.assertEqual(self.rows('tutors'), before)


if __name__ == '__main__':
    unittest.main()
