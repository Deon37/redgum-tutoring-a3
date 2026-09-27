"""HTTP contract for listing and creating tutors."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from app import app
import database


class TutorRouteTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.db_path = Path(temporary_directory.name) / 'test.db'
        database_path = patch.object(database, 'DATABASE', str(self.db_path))
        database_path.start()
        self.addCleanup(database_path.stop)
        config = patch.dict(app.config, TESTING=True, SECRET_KEY='test-only-key')
        config.start()
        self.addCleanup(config.stop)
        self.client = app.test_client()
        schema = Path(__file__).resolve().parents[1] / 'schema.sql'
        with app.app_context():
            database.get_db().executescript(schema.read_text(encoding='utf-8'))

    def seed_tutor(self, name='Tomás Ferreira', subjects='Physics, Chemistry', active=1):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                'INSERT INTO tutors (name, subjects, active) VALUES (?, ?, ?)',
                (name, subjects, active),
            )
            connection.commit()

    def tutors(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute('SELECT * FROM tutors ORDER BY id')]

    def test_get_lists_tutor_names_and_subjects(self):
        self.seed_tutor()
        self.seed_tutor('Helen Vasquez', 'Senior Mathematics')

        response = self.client.get('/tutors')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for tutor in self.tutors():
            self.assertIn(tutor['name'], page)
            self.assertIn(tutor['subjects'], page)

    def test_post_saves_tutor_and_redirects_to_list(self):
        response = self.client.post('/tutors', data={
            'name': 'Helen Vasquez', 'subjects': 'Senior Mathematics',
        })

        self.assertIn(response.status_code, (302, 303))
        self.assertEqual(urlsplit(response.headers['Location']).path, '/tutors')
        tutors = self.tutors()
        self.assertEqual(len(tutors), 1)
        self.assertEqual(tutors[0]['name'], 'Helen Vasquez')
        self.assertEqual(tutors[0]['subjects'], 'Senior Mathematics')
        self.assertEqual(tutors[0]['active'], 1)

    def test_post_rejects_missing_required_fields(self):
        for field in ('name', 'subjects'):
            with self.subTest(field=field):
                data = {'name': 'Helen Vasquez', 'subjects': 'Maths'}
                del data[field]

                response = self.client.post('/tutors', data=data, follow_redirects=True)

                self.assertIn(response.status_code, (200, 400))
                self.assertRegex(response.get_data(as_text=True), r'(?i)required')
                self.assertEqual(self.tutors(), [])


if __name__ == '__main__':
    unittest.main()
