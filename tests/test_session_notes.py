import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

with patch.dict(os.environ, {'SECRET_KEY': 'test-only-key', 'FLASK_DEBUG': 'false'}):
    from app import app
import database


class NotesPageParser(HTMLParser):
    """Inspect editable notes and session history without CSS dependencies."""

    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.rows = []
        self.form = self.textarea = self.row = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.form = {'attrs': attrs, 'textareas': {}, 'submit': False}
            self.forms.append(self.form)
        elif tag == 'textarea' and self.form is not None:
            self.textarea = {'attrs': attrs, 'text': ''}
            self.form['textareas'][attrs.get('name')] = self.textarea
        elif self.form is not None and (
            (tag == 'button' and attrs.get('type', 'submit') == 'submit')
            or (tag == 'input' and attrs.get('type') == 'submit')
        ):
            self.form['submit'] = True
        if tag == 'tr':
            self.row = []

    def handle_data(self, data):
        if self.textarea is not None:
            self.textarea['text'] += data
        if self.row is not None:
            self.row.append(data)

    def handle_endtag(self, tag):
        if tag == 'textarea':
            self.textarea = None
        elif tag == 'form':
            self.form = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(' '.join(' '.join(self.row).split()))
            self.row = None


class SessionNotesTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db_path = Path(directory.name) / 'notes.db'
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
            tutors = [connection.execute(
                'INSERT INTO tutors (name, subjects) VALUES (?, ?)', (name, 'Maths')
            ).lastrowid for name in ('Example Tutor A', 'Example Tutor B')]
            students = [connection.execute(
                'INSERT INTO students (name, year_level, contact_name, contact_phone) '
                'VALUES (?, ?, ?, ?)', (name, 11, 'Example Parent', '0400000000')
            ).lastrowid for name in ('Example Student', 'Other Student')]
            self.student_id = students[0]
            self.session_ids = []
            for student, tutor, day, notes in (
                (students[0], tutors[0], '2026-08-11', 'Fractions and decimals.'),
                (students[0], tutors[1], '2026-08-18', 'Quadratics; next focus is graphs.'),
                (students[1], tutors[0], '2026-08-12', 'Other student: trigonometry.'),
            ):
                self.session_ids.append(connection.execute(
                    'INSERT INTO sessions '
                    '(student_id, tutor_id, date, start_time, length_mins, status, notes) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (student, tutor, day, '15:30', 60, 'attended', notes),
                ).lastrowid)
            connection.commit()
        # No availability windows: recording historical notes must not rebook a session.

    def sessions(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute('SELECT * FROM sessions ORDER BY id')]

    def notes_form(self, response):
        self.assertEqual(response.status_code, 200)
        page = NotesPageParser(response.get_data(as_text=True))
        forms = [form for form in page.forms if 'notes' in form['textareas']]
        self.assertEqual(len(forms), 1, 'Provide one editable session-notes form.')
        return forms[0]

    def test_session_page_has_editable_prefilled_notes_form(self):
        session_id = self.session_ids[0]
        form = self.notes_form(self.client.get(f'/sessions/{session_id}/edit'))

        self.assertEqual(form['attrs'].get('method', 'get').lower(), 'post')
        self.assertEqual(form['attrs'].get('action'), f'/sessions/{session_id}/notes')
        self.assertTrue(form['submit'])
        field = form['textareas']['notes']
        self.assertEqual(field['text'], 'Fractions and decimals.')
        self.assertNotIn('disabled', field['attrs'])
        self.assertNotIn('readonly', field['attrs'])

    def test_save_and_update_notes_persist_without_changing_bookings(self):
        session_id = self.session_ids[0]
        notes = "Factorisation and completing the square.\nNext: Sam's questions about x < 0 & y > 0."
        for previous in (None, 'Previous topic summary.'):
            with self.subTest(previous=previous):
                with closing(sqlite3.connect(self.db_path)) as connection:
                    connection.execute('UPDATE sessions SET notes = ? WHERE id = ?', (previous, session_id))
                    connection.commit()
                before = self.sessions()

                response = self.client.post(f'/sessions/{session_id}/notes', data={'notes': notes})

                self.assertIn(response.status_code, (302, 303))
                expected = [dict(row) for row in before]
                expected[0]['notes'] = notes
                self.assertEqual(self.sessions(), expected)
                reopened = app.test_client().get(f'/sessions/{session_id}/edit')
                self.assertEqual(self.notes_form(reopened)['textareas']['notes']['text'], notes)
                self.assertIn('x &lt; 0 &amp; y &gt; 0', reopened.get_data(as_text=True))

    def test_student_history_shows_notes_from_each_tutor_for_only_that_student(self):
        response = app.test_client().get(f'/students/{self.student_id}')

        self.assertEqual(response.status_code, 200)
        page = NotesPageParser(response.get_data(as_text=True))
        for day, tutor, notes in (
            ('2026-08-11', 'Example Tutor A', 'Fractions and decimals.'),
            ('2026-08-18', 'Example Tutor B', 'Quadratics; next focus is graphs.'),
        ):
            rows = [row for row in page.rows if notes in row]
            self.assertEqual(len(rows), 1, 'Show each session note with its tutor and date.')
            self.assertIn(day, rows[0])
            self.assertIn(tutor, rows[0])
        self.assertNotIn('Other student: trigonometry.', response.get_data(as_text=True))

    def test_missing_notes_or_unknown_session_cannot_change_records(self):
        before = self.sessions()
        response = self.client.post(f'/sessions/{self.session_ids[0]}/notes', data={})

        self.assertEqual(response.status_code, 400)
        self.assertRegex(response.get_data(as_text=True), r'(?i)notes.*required')
        self.assertEqual(self.sessions(), before)
        response = self.client.post('/sessions/9999/notes', data={'notes': 'Missing session.'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.sessions(), before)


if __name__ == '__main__':
    unittest.main()
