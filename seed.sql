INSERT OR IGNORE INTO students (id, name, year_level, contact_name, contact_phone) VALUES
(1, 'Emma Chen', 10, 'Linda Chen', '0411 222 333'),
(2, 'Jake Thompson', 9, 'Mark Thompson', '0412 345 678'),
(3, 'Liam O''Brien', 7, 'Fiona O''Brien', '0413 456 789');

INSERT OR IGNORE INTO tutors (id, name, subjects) VALUES
(1, 'Tomas Rivera', 'Maths, Science'),
(2, 'Sarah Park', 'English, History');

INSERT OR IGNORE INTO availability (id, tutor_id, day_of_week, start_time, end_time) VALUES
(1, 1, 'Monday', '09:00', '13:00'),
(2, 1, 'Wednesday', '14:00', '18:00'),
(3, 1, 'Friday', '09:00', '12:00'),
(4, 2, 'Tuesday', '10:00', '14:00'),
(5, 2, 'Thursday', '13:00', '17:00'),
(6, 2, 'Saturday', '09:00', '13:00');

INSERT OR IGNORE INTO sessions (id, student_id, tutor_id, date, start_time, length_mins, status) VALUES
(1, 1, 1, '2026-09-28', '09:00', 60, 'booked'),
(2, 3, 2, '2026-09-29', '10:00', 90, 'booked');
