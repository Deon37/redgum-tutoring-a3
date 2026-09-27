"""HTTP contract for listing, creating, viewing and updating tutors."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from app import app
import database


class TutorPageParser(HTMLParser):
    """Read form controls and links without depending on HTML formatting."""

    def __init__(self, html):
        super().__init__()
        self.links = []
        self.forms = []
        self.current_form = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self.links.append(attrs.get('href'))
        elif tag == 'form':
            self.current_form = {'attrs': attrs, 'inputs': {}, 'submit': False}
            self.forms.append(self.current_form)
        elif self.current_form is not None:
            if tag == 'input' and attrs.get('name'):
                self.current_form['inputs'][attrs['name']] = attrs
            if (tag == 'button' and attrs.get('type', 'submit') == 'submit') or (
                tag == 'input' and attrs.get('type') == 'submit'
            ):
                self.current_form['submit'] = True

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current_form = None


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
            cursor = connection.execute(
                'INSERT INTO tutors (name, subjects, active) VALUES (?, ?, ?)',
                (name, subjects, active),
            )
            connection.commit()
            return cursor.lastrowid

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

    def test_tutor_list_links_to_each_edit_page(self):
        tutor_ids = [self.seed_tutor(), self.seed_tutor('Helen Vasquez', 'Maths')]

        response = self.client.get('/tutors')

        self.assertEqual(response.status_code, 200)
        page = TutorPageParser(response.get_data(as_text=True))
        for tutor_id in tutor_ids:
            self.assertIn(f'/tutors/{tutor_id}', page.links)

    def assert_tutor_form(self, response, action, expected_values):
        self.assertEqual(response.status_code, 200)
        page = TutorPageParser(response.get_data(as_text=True))
        forms = [form for form in page.forms if form['attrs'].get('action') == action]
        self.assertEqual(len(forms), 1, 'Expected one form targeting the tutor route.')
        form = forms[0]
        self.assertEqual(form['attrs'].get('method', 'get').lower(), 'post')
        self.assertTrue(form['submit'], 'The form needs a submit control.')
        for name, value in expected_values.items():
            self.assertIn(name, form['inputs'])
            field = form['inputs'][name]
            self.assertEqual(field.get('value', ''), value)
            self.assertIn('required', field)
            self.assertNotIn('disabled', field)
            self.assertNotIn('readonly', field)

    def test_add_form_has_blank_required_fields_and_posts_to_tutor_list(self):
        response = self.client.get('/tutors')

        self.assert_tutor_form(response, '/tutors', {'name': '', 'subjects': ''})

    def test_edit_form_prefills_details_and_posts_to_selected_tutor(self):
        tutor_id = self.seed_tutor('Helen Vasquez', 'Senior Mathematics')

        response = self.client.get(f'/tutors/{tutor_id}')

        self.assert_tutor_form(response, f'/tutors/{tutor_id}', {
            'name': 'Helen Vasquez', 'subjects': 'Senior Mathematics',
        })

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


    def test_get_tutor_displays_the_requested_tutor(self):
        tutor_id = self.seed_tutor()
        self.seed_tutor('Helen Vasquez', 'Senior Mathematics')

        response = self.client.get(f'/tutors/{tutor_id}')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('Tomás Ferreira', page)
        self.assertIn('Physics, Chemistry', page)
        self.assertNotIn('Helen Vasquez', page)

    def test_post_tutor_updates_only_the_requested_tutor_and_redirects(self):
        tutor_id = self.seed_tutor()
        self.seed_tutor('Helen Vasquez', 'Senior Mathematics')
        before = self.tutors()

        response = self.client.post(f'/tutors/{tutor_id}', data={
            'name': 'Tom Ferreira', 'subjects': 'Maths Methods',
        })

        self.assertIn(response.status_code, (302, 303))
        self.assertEqual(urlsplit(response.headers['Location']).path, '/tutors')
        expected = [dict(tutor) for tutor in before]
        expected[0].update(name='Tom Ferreira', subjects='Maths Methods')
        self.assertEqual(self.tutors(), expected)

    def test_post_tutor_rejects_missing_required_fields_without_changes(self):
        tutor_id = self.seed_tutor()
        before = self.tutors()
        for field in ('name', 'subjects'):
            with self.subTest(field=field):
                data = {'name': 'Changed Name', 'subjects': 'Changed Subject'}
                del data[field]

                response = self.client.post(
                    f'/tutors/{tutor_id}', data=data, follow_redirects=True,
                )

                self.assertIn(response.status_code, (200, 400))
                self.assertRegex(response.get_data(as_text=True), r'(?i)required')
                self.assertEqual(self.tutors(), before)

    def test_unknown_tutor_returns_404_without_changes(self):
        tutor_id = self.seed_tutor()
        before = self.tutors()
        for method in ('GET', 'POST'):
            with self.subTest(method=method):
                response = self.client.open(
                    f'/tutors/{tutor_id + 1}', method=method,
                    data={'name': 'Missing Tutor', 'subjects': 'Maths'},
                )

                self.assertEqual(response.status_code, 404)
                self.assertEqual(self.tutors(), before)


if __name__ == '__main__':
    unittest.main()
