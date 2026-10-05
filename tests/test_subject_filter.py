import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

with patch.dict(os.environ, {'SECRET_KEY': 'test-only-key', 'FLASK_DEBUG': 'false'}):
    from app import app
import database


class BookingFormParser(HTMLParser):
    """Read tutor choices and the submitted subject from the booking form only."""

    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.form = None
        self.select = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.form = {'attrs': attrs, 'inputs': {}, 'selects': {}}
            self.forms.append(self.form)
        elif self.form is not None:
            if tag == 'input' and attrs.get('name'):
                self.form['inputs'][attrs['name']] = attrs
            elif tag == 'select':
                self.select = []
                self.form['selects'][attrs.get('name')] = self.select
            elif tag == 'option' and self.select is not None:
                self.select.append(attrs)

    def handle_endtag(self, tag):
        if tag == 'select':
            self.select = None
        elif tag == 'form':
            self.form = None
            self.select = None


class SubjectFilterTests(unittest.TestCase):
    DATE = '2026-09-01'  # Tuesday

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db_path = Path(directory.name) / 'subjects.db'
        db_patch = patch.object(database, 'DATABASE', str(self.db_path))
        db_patch.start()
        self.addCleanup(db_patch.stop)
        config_patch = patch.dict(app.config, TESTING=True, SECRET_KEY='test-only-key')
        config_patch.start()
        self.addCleanup(config_patch.stop)
        self.client = app.test_client()
        schema = Path(__file__).resolve().parents[1] / 'schema.sql'
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(schema.read_text(encoding='utf-8'))
            self.student_id = connection.execute(
                'INSERT INTO students (name, year_level, contact_name, contact_phone) '
                'VALUES (?, ?, ?, ?)', ('Example Student', 11, 'Example Parent', '0400000000')
            ).lastrowid
            self.tutor_ids = {}
            for name, subjects, active in (
                ('Multi Tutor', 'Maths, Chemistry,  Physics ', 1),
                ('Physics Tutor', 'physics', 1), ('English Tutor', 'English', 1),
                ('Similar Tutor', 'Biophysics', 1), ('Inactive Tutor', 'Physics', 0),
                ('Away Tutor', 'Physics', 1), ('Short Window Tutor', 'Physics', 1),
                ('No Window Tutor', 'Physics', 1),
            ):
                tutor_id = connection.execute(
                    'INSERT INTO tutors (name, subjects, active) VALUES (?, ?, ?)',
                    (name, subjects, active),
                ).lastrowid
                self.tutor_ids[name] = tutor_id
                if name != 'No Window Tutor':
                    connection.execute(
                        'INSERT INTO availability (tutor_id, day_of_week, start_time, end_time) '
                        'VALUES (?, ?, ?, ?)',
                        (tutor_id, 'Tuesday', '15:00', '16:30' if name == 'Short Window Tutor' else '18:00'),
                    )
            connection.execute(
                'INSERT INTO blackouts (tutor_id, start_date, end_date) VALUES (?, ?, ?)',
                (self.tutor_ids['Away Tutor'], self.DATE, self.DATE),
            )
            connection.commit()

    def booking_form(self, response):
        self.assertEqual(response.status_code, 200)
        page = BookingFormParser(response.get_data(as_text=True))
        forms = [form for form in page.forms if 'tutor_id' in form['selects']
                 and form['attrs'].get('method', 'get').lower() == 'post']
        self.assertEqual(len(forms), 1, 'Expected one booking form with tutor choices.')
        return forms[0]

    def tutor_options(self, form):
        return {int(option['value']) for option in form['selects']['tutor_id']
                if option.get('value') and 'disabled' not in option}

    def sessions(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute('SELECT * FROM sessions ORDER BY id')]

    def booking_data(self, tutor):
        return {
            'student_id': self.student_id, 'tutor_id': self.tutor_ids[tutor],
            'subject': ' physics ', 'date': self.DATE, 'start_time': '15:30', 'length_mins': '60',
        }

    def test_subject_filter_matches_whole_subjects_and_excludes_inactive_tutors(self):
        expected = {self.tutor_ids[name] for name in (
            'Multi Tutor', 'Physics Tutor', 'Away Tutor', 'Short Window Tutor', 'No Window Tutor',
        )}
        for subject in (' physics ', 'PHYSICS'):
            with self.subTest(subject=subject):
                response = self.client.get('/sessions', query_string={'subject': subject})
                form = self.booking_form(response)
                self.assertEqual(self.tutor_options(form), expected)
                # Preserve the filter in POST so qualification can be checked server-side.
                field = form['inputs'].get('subject')
                if field is not None:
                    self.assertNotIn('disabled', field)
                    selected = field.get('value', '')
                else:
                    choices = form['selects'].get('subject', [])
                    selected = next((option.get('value', '') for option in choices
                                     if 'selected' in option), '')
                self.assertEqual(selected.strip().casefold(), 'physics')

    def test_time_filter_requires_full_availability_and_respects_blackouts(self):
        response = self.client.get('/sessions', query_string={
            'subject': 'Physics', 'date': self.DATE, 'start_time': '15:30', 'length_mins': '90',
        })

        self.assertEqual(self.tutor_options(self.booking_form(response)), {
            self.tutor_ids['Multi Tutor'], self.tutor_ids['Physics Tutor'],
        })

    def test_no_qualified_tutors_shows_empty_choices_and_clear_feedback(self):
        response = self.client.get('/sessions', query_string={'subject': 'History'})

        self.assertEqual(self.tutor_options(self.booking_form(response)), set())
        self.assertRegex(response.get_data(as_text=True),
                         r'(?i)no\s+(?:available|qualified|matching)\s+tutors')

    def test_post_rejects_unqualified_or_inactive_tutor_without_saving(self):
        for tutor in ('English Tutor', 'Inactive Tutor'):
            with self.subTest(tutor=tutor):
                before = self.sessions()
                response = self.client.post('/sessions', data=self.booking_data(tutor), follow_redirects=True)

                self.assertIn(response.status_code, (200, 400))
                self.assertEqual(self.sessions(), before, 'An invalid tutor choice must not save a booking.')
                self.assertRegex(response.get_data(as_text=True),
                                 r'(?i)not qualified|does not teach|cannot teach|inactive|not active')

    def test_post_saves_booking_with_qualified_available_tutor(self):
        response = self.client.post('/sessions', data=self.booking_data('Multi Tutor'))

        self.assertIn(response.status_code, (302, 303))
        self.assertEqual(urlsplit(response.headers['Location']).path, '/sessions')
        saved = self.sessions()
        self.assertEqual(len(saved), 1)
        self.assertEqual((saved[0]['student_id'], saved[0]['tutor_id'], saved[0]['date'],
                          saved[0]['start_time'], saved[0]['length_mins'], saved[0]['status']),
                         (self.student_id, self.tutor_ids['Multi Tutor'], self.DATE, '15:30', 60, 'booked'))


if __name__ == '__main__':
    unittest.main()
