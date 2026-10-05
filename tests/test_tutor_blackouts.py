"""TDD contract: inclusive, whole-day tutor blackouts override weekly availability."""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

with patch.dict(os.environ, {'SECRET_KEY': 'test-only-key', 'FLASK_DEBUG': 'false'}):
    from app import app
import database


class TutorBlackoutTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db_path = Path(directory.name) / 'blackouts.db'
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
            self.student_id = connection.execute(
                'INSERT INTO students (name, year_level, contact_name, contact_phone) '
                'VALUES (?, ?, ?, ?)', ('Example Student', 11, 'Example Parent', '0400000000')
            ).lastrowid
            for tutor_id in self.tutor_ids:
                for day in ('Tuesday', 'Wednesday', 'Thursday', 'Friday'):
                    connection.execute(
                        'INSERT INTO availability (tutor_id, day_of_week, start_time, end_time) '
                        'VALUES (?, ?, ?, ?)', (tutor_id, day, '15:00', '20:00'),
                    )
            connection.commit()

    def rows(self, table):
        # Separate connections verify committed records survive between requests.
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(f'SELECT * FROM {table} ORDER BY id')]

    def add_blackout(self, start='2026-09-01', end='2026-09-04', tutor=0):
        response = self.client.post(f'/tutors/{self.tutor_ids[tutor]}/blackouts', data={
            'start_date': start, 'end_date': end,
        })
        self.assertIn(response.status_code, (302, 303), 'Saving a blackout should redirect.')

    def booking_data(self, day, tutor=0, start='15:30'):
        return {
            'student_id': self.student_id, 'tutor_id': self.tutor_ids[tutor],
            'date': day, 'start_time': start, 'length_mins': '60',
        }

    def assert_blackout_feedback(self, response):
        self.assertIn(response.status_code, (200, 400))
        self.assertRegex(response.get_data(as_text=True), r'(?i)blackout|on leave|away|unavailable')

    def test_records_multiple_periods_and_lists_only_selected_tutors_blackouts(self):
        periods = [('2026-09-01', '2026-09-04'), ('2026-09-09', '2026-09-09')]
        for start, end in periods:
            self.add_blackout(start, end)
        self.add_blackout('2026-09-15', '2026-09-18', tutor=1)

        saved = [(row['tutor_id'], row['start_date'], row['end_date'])
                 for row in self.rows('blackouts')]
        self.assertEqual(saved, [*(
            (self.tutor_ids[0], start, end) for start, end in periods
        ), (self.tutor_ids[1], '2026-09-15', '2026-09-18')])
        # A fresh client/request must see the saved periods.
        response = app.test_client().get(f'/tutors/{self.tutor_ids[0]}/blackouts')
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for start, end in periods:
            self.assertIn(start, page)
            self.assertIn(end, page)
        self.assertNotIn('2026-09-15', page)
        self.assertNotIn('2026-09-18', page)

    def test_rejects_missing_invalid_or_reversed_dates_without_saving(self):
        for start, end in (
            (None, '2026-09-04'), ('2026-09-01', None), ('', '2026-09-04'),
            ('not-a-date', '2026-09-04'), ('2026-09-01', 'not-a-date'),
            ('2026-02-30', '2026-03-04'), ('2026-09-04', '2026-09-01'),
        ):
            with self.subTest(start=start, end=end):
                data = {field: value for field, value in (
                    ('start_date', start), ('end_date', end),
                ) if value is not None}
                response = self.client.post(
                    f'/tutors/{self.tutor_ids[0]}/blackouts', data=data, follow_redirects=True,
                )
                self.assertIn(response.status_code, (200, 400))
                self.assertRegex(response.get_data(as_text=True),
                                 r'(?i)required|invalid|valid date|before|after')
                self.assertEqual(self.rows('blackouts'), [])

    def test_blackout_overrides_availability_and_blocks_entire_inclusive_period(self):
        self.add_blackout()
        self.add_blackout('2026-09-09', '2026-09-09')
        windows = self.rows('availability')
        for day, start in (
            ('2026-09-01', '15:00'), ('2026-09-02', '17:30'),
            ('2026-09-04', '19:00'), ('2026-09-09', '16:00'),
        ):
            with self.subTest(day=day, start=start):
                with app.app_context():
                    available, reason = database.check_availability(self.tutor_ids[0], day, start, 60)
                self.assertFalse(available, 'Blackouts must override an otherwise valid window.')
                self.assertRegex(reason, r'(?i)blackout|on leave|away|unavailable')
                response = self.client.post('/sessions', data=self.booking_data(day, start=start),
                                            follow_redirects=True)
                self.assert_blackout_feedback(response)
                self.assertEqual(self.rows('sessions'), [])
        self.assertEqual(self.rows('availability'), windows)

    def test_other_dates_and_tutors_remain_bookable_within_weekly_availability(self):
        self.add_blackout()
        for day, tutor in (('2026-08-28', 0), ('2026-09-08', 0), ('2026-09-01', 1)):
            response = self.client.post('/sessions', data=self.booking_data(day, tutor))
            self.assertIn(response.status_code, (302, 303))
        saved = self.rows('sessions')
        self.assertEqual([(row['date'], row['tutor_id']) for row in saved], [
            ('2026-08-28', self.tutor_ids[0]), ('2026-09-08', self.tutor_ids[0]),
            ('2026-09-01', self.tutor_ids[1]),
        ])
        # An unblocked date still requires the whole session to fit its window.
        response = self.client.post('/sessions', data=self.booking_data(
            '2026-09-08', start='19:30',
        ), follow_redirects=True)
        self.assertIn(response.status_code, (200, 400))
        self.assertRegex(response.get_data(as_text=True), r'(?i)not available|unavailable')
        self.assertEqual(self.rows('sessions'), saved)

    def test_moving_session_into_blackout_is_refused_without_changing_booking(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            session_id = connection.execute(
                'INSERT INTO sessions (student_id, tutor_id, date, start_time, length_mins, notes) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (self.student_id, self.tutor_ids[0], '2026-08-28', '15:30', 60, 'Keep this note'),
            ).lastrowid
            connection.commit()
        self.add_blackout()
        before = self.rows('sessions')

        response = self.client.post(f'/sessions/{session_id}/edit', data={
            'date': '2026-09-01', 'start_time': '16:00', 'length_mins': '90',
        }, follow_redirects=True)

        self.assert_blackout_feedback(response)
        self.assertEqual(self.rows('sessions'), before)


if __name__ == '__main__':
    unittest.main()
