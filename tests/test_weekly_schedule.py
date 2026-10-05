import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

with patch.dict(os.environ, {'SECRET_KEY': 'test-only-key', 'FLASK_DEBUG': 'false'}):
    from app import app
import database


class SchedulePageParser(HTMLParser):
    """Read booking rows without relying on CSS or HTML whitespace."""

    def __init__(self, html):
        super().__init__()
        self.text = []
        self.rows = []
        self.row = None
        self.feed(html)

    @property
    def visible_text(self):
        return ' '.join(' '.join(self.text).split())

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []

    def handle_data(self, data):
        self.text.append(data)
        if self.row is not None:
            self.row.append(data)

    def handle_endtag(self, tag):
        if tag == 'tr' and self.row is not None:
            self.rows.append(' '.join(' '.join(self.row).split()))
            self.row = None


class WeeklyScheduleTests(unittest.TestCase):
    WEEK_START = '2026-08-11'
    DAYS = ('Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db_path = Path(directory.name) / 'schedule.db'
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
            self.tutor_ids = [connection.execute(
                'INSERT INTO tutors (name, subjects) VALUES (?, ?)', (name, 'Physics')
            ).lastrowid for name in ('Example Tutor A', 'Example Tutor B')]
            connection.commit()

    def seed_session(self, student, day, start='15:30', length=60, status='booked', tutor=0):
        # Seed directly: these tests cover viewing, rather than creating bookings.
        with closing(sqlite3.connect(self.db_path)) as connection:
            student_id = connection.execute(
                'INSERT INTO students (name, year_level, contact_name, contact_phone) '
                'VALUES (?, ?, ?, ?)', (student, 11, 'Example Parent', '0400000000')
            ).lastrowid
            connection.execute(
                'INSERT INTO sessions '
                '(student_id, tutor_id, date, start_time, length_mins, status) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (student_id, self.tutor_ids[tutor], day, start, length, status),
            )
            connection.commit()
        return {
            'student_name': student, 'tutor_name': f'Example Tutor {"AB"[tutor]}',
            'date': day, 'start_time': start, 'length_mins': length, 'status': status,
        }

    def schedule(self, week_start=WEEK_START):
        response = self.client.get('/schedule', query_string={'week_start': week_start})
        self.assertEqual(response.status_code, 200)
        return SchedulePageParser(response.get_data(as_text=True))

    def assert_week(self, page, week_start=WEEK_START):
        positions = []
        for offset, day in enumerate(self.DAYS):
            self.assertIn(day, page.visible_text)
            positions.append(page.visible_text.index(day))
            expected_date = date.fromisoformat(week_start) + timedelta(days=offset)
            self.assertIn(expected_date.isoformat(), page.visible_text)
        self.assertEqual(positions, sorted(positions))
        self.assertNotRegex(page.visible_text, r'\b(?:Monday|Sunday)\b')

    def assert_booking(self, page, session):
        rows = [row for row in page.rows if session['student_name'] in row]
        self.assertEqual(len(rows), 1, 'Show each booking once, with its details together.')
        for field in ('date', 'tutor_name', 'start_time', 'status'):
            self.assertIn(session[field], rows[0])
        self.assertRegex(rows[0], rf'\b{session["length_mins"]}\s+(?:mins|minutes)\b')

    def test_week_shows_all_days_and_bookings_for_all_tutors(self):
        sessions = [
            self.seed_session('Tuesday Student', '2026-08-11'),
            self.seed_session('Wednesday Student', '2026-08-12', length=90, tutor=1),
            self.seed_session('Thursday Student', '2026-08-13', status='cancelled'),
            self.seed_session('Friday Student', '2026-08-14', status='attended', tutor=1),
            self.seed_session('Saturday Student', '2026-08-15', start='08:30', status='missed'),
        ]
        page = self.schedule()
        self.assert_week(page)
        for session in sessions:
            self.assert_booking(page, session)

    def test_selected_week_includes_endpoints_and_excludes_other_dates(self):
        tuesday = self.seed_session('Opening Booking', self.WEEK_START)
        saturday = self.seed_session('Closing Booking', '2026-08-15', start='12:00')
        next_week = self.seed_session('Next Week Booking', '2026-08-18', tutor=1)
        excluded = [self.seed_session(name, day) for name, day in (
            ('Previous Week Booking', '2026-08-08'),
            ('Monday Booking', '2026-08-10'), ('Sunday Booking', '2026-08-16'),
        )]

        page = self.schedule()
        for session in (tuesday, saturday):
            self.assert_booking(page, session)
        for session in [*excluded, next_week]:
            self.assertNotIn(session['student_name'], page.visible_text)

        page = self.schedule('2026-08-18')
        self.assert_week(page, '2026-08-18')
        self.assert_booking(page, next_week)
        for session in [*excluded, tuesday, saturday]:
            self.assertNotIn(session['student_name'], page.visible_text)

    def test_bookings_are_ordered_by_date_then_start_time(self):
        late = self.seed_session('Late Tuesday', self.WEEK_START, start='17:00')
        friday = self.seed_session('Friday Booking', '2026-08-14', tutor=1)
        early = self.seed_session('Early Tuesday', self.WEEK_START, start='15:00', tutor=1)
        page = self.schedule()
        expected = [early, late, friday]
        for session in expected:
            self.assert_booking(page, session)
        names = [session['student_name'] for session in expected]
        actual = [name for row in page.rows for name in names if name in row]
        self.assertEqual(actual, names)

    def test_empty_week_keeps_all_days_and_explains_no_bookings(self):
        self.seed_session('Outside Week Booking', '2026-08-18')
        page = self.schedule()
        self.assert_week(page)
        self.assertRegex(page.visible_text, r'(?i)\bno\s+(?:sessions|bookings)\b')
        self.assertNotIn('Outside Week Booking', page.visible_text)


if __name__ == '__main__':
    unittest.main()
