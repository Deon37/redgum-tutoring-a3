from datetime import date, datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from config import load_settings
import database

app = Flask(__name__)
app.config.update(load_settings())

database.init_app(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/students', methods=['GET', 'POST'])
def students():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        year_level = request.form.get('year_level', '').strip()
        contact_name = request.form.get('contact_name', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()

        if not name or not year_level or not contact_name or not contact_phone:
            flash('All fields are required.', 'error')
        else:
            database.add_student(name, year_level, contact_name, contact_phone)
            flash(f'{name} added.', 'success')
            return redirect(url_for('students'))

    query = request.args.get('search', '').strip()
    if query:
        student_list = database.search_students(query)
    else:
        student_list = database.get_students()
    return render_template('students.html', students=student_list, search=query)


@app.route('/students/<int:student_id>', methods=['GET', 'POST'])
def student_detail(student_id):
    student = database.get_student(student_id)
    if student is None:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        year_level = request.form.get('year_level', '').strip()
        contact_name = request.form.get('contact_name', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()

        if not name or not year_level or not contact_name or not contact_phone:
            flash('All fields are required.', 'error')
        else:
            try:
                database.update_student(student_id, name, year_level, contact_name, contact_phone)
            except ValueError as error:
                flash(str(error), 'error')
            else:
                flash(f'{name} updated.', 'success')
                return redirect(url_for('students'))

    return render_template('student_detail.html', student=student,
                           upcoming=database.get_student_upcoming_sessions(student_id),
                           past=database.get_student_past_sessions(student_id))


@app.route('/students/<int:student_id>/deactivate', methods=['POST'])
def deactivate_student(student_id):
    student = database.get_student(student_id)
    if student is None:
        abort(404)
    database.deactivate_student(student_id)
    flash(f'{student["name"]} has been deactivated.', 'success')
    return redirect(url_for('students'))


@app.route('/tutors', methods=['GET', 'POST'])
def tutors():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subjects = request.form.get('subjects', '').strip()

        try:
            database.add_tutor(name, subjects)
        except ValueError as error:
            flash(str(error), 'error')
        else:
            flash(f'{name} added.', 'success')
            return redirect(url_for('tutors'))

    return render_template('tutors.html', tutors=database.get_tutors())


@app.route('/tutors/<int:tutor_id>', methods=['GET', 'POST'])
def tutor_detail(tutor_id):
    tutor = database.get_tutor(tutor_id)
    if tutor is None:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subjects = request.form.get('subjects', '').strip()

        try:
            database.update_tutor(tutor_id, name, subjects)
        except ValueError as error:
            flash(str(error), 'error')
        else:
            flash(f'{name} updated.', 'success')
            return redirect(url_for('tutors'))

    return render_template('tutor_detail.html', tutor=tutor)


@app.route('/tutors/<int:tutor_id>/deactivate', methods=['POST'])
def deactivate_tutor(tutor_id):
    tutor = database.get_tutor(tutor_id)
    if tutor is None:
        abort(404)
    database.deactivate_tutor(tutor_id)
    flash(f'{tutor["name"]} has been deactivated.', 'success')
    return redirect(url_for('tutors'))


@app.route('/tutors/<int:tutor_id>/sessions')
def tutor_sessions(tutor_id):
    tutor = database.get_tutor(tutor_id)
    if tutor is None:
        abort(404)
    sessions = database.get_tutor_upcoming_sessions(tutor_id)
    return render_template('tutor_sessions.html', tutor=tutor, sessions=sessions)


@app.route('/tutors/<int:tutor_id>/availability', methods=['GET', 'POST'])
def availability(tutor_id):
    tutor = database.get_tutor(tutor_id)
    if tutor is None:
        flash('Tutor not found.', 'error')
        return redirect(url_for('tutors'))

    if request.method == 'POST':
        day = request.form.get('day_of_week', '').strip()
        start = request.form.get('start_time', '').strip()
        end = request.form.get('end_time', '').strip()

        if not day or not start or not end:
            flash('All fields are required.', 'error')
        elif start >= end:
            flash('End time must be after start time.', 'error')
        else:
            database.add_availability(tutor_id, day, start, end)
            flash('Availability saved.', 'success')
            return redirect(url_for('availability', tutor_id=tutor_id))

    windows = database.get_availability(tutor_id)
    return render_template('availability.html', tutor=tutor, windows=windows)


@app.route('/tutors/<int:tutor_id>/blackouts', methods=['GET', 'POST'])
def blackouts(tutor_id):
    tutor = database.get_tutor(tutor_id)
    if tutor is None:
        abort(404)

    if request.method == 'POST':
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()
        try:
            database.add_blackout(tutor_id, start_date, end_date)
        except ValueError as error:
            flash(str(error), 'error')
        else:
            flash('Blackout period saved.', 'success')
            return redirect(url_for('blackouts', tutor_id=tutor_id))

    return render_template('blackouts.html', tutor=tutor,
                           periods=database.get_blackouts(tutor_id))


@app.route('/availability/<int:availability_id>/delete', methods=['POST'])
def delete_availability(availability_id):
    database.delete_availability(availability_id)
    tutor_id = request.form.get('tutor_id')
    return redirect(url_for('availability', tutor_id=tutor_id))


@app.route('/sessions', methods=['GET', 'POST'])
def sessions():
    day_filter = request.args.get('day', '').strip() if request.method == 'GET' else ''
    submitted = request.form if request.method == 'POST' else request.args
    values = {field: submitted.get(field, '').strip() for field in (
        'student_id', 'tutor_id', 'subject', 'date', 'start_time', 'length_mins',
    )}
    subject = values['subject']
    date = values['date']
    start_time = values['start_time']
    length_mins = None
    slot_error = None
    if any((date, start_time, values['length_mins'])):
        if not all((date, start_time, values['length_mins'])):
            slot_error = 'Date, start time and length are required to filter availability.'
        else:
            try:
                length_mins = int(values['length_mins'])
                if (datetime.strptime(date, '%Y-%m-%d').date().isoformat() != date
                        or datetime.strptime(start_time, '%H:%M').strftime('%H:%M') != start_time
                        or length_mins not in (60, 90)):
                    raise ValueError
            except ValueError:
                slot_error = 'Enter a valid date, start time and a length of 60 or 90 minutes.'

    if request.method == 'POST':
        student_id = values['student_id']
        tutor_id = values['tutor_id']
        if not all((student_id, tutor_id, date, start_time, values['length_mins'])):
            flash('All fields are required.', 'error')
        elif slot_error:
            flash(slot_error, 'error')
        else:
            tutor = database.get_tutor(tutor_id)
            if tutor is None:
                flash('Tutor not found. Select an active tutor.', 'error')
            elif not tutor['active']:
                flash('This tutor is inactive. Select an active tutor.', 'error')
            elif subject and not database.tutor_teaches_subject(tutor, subject):
                flash(f'{tutor["name"]} is not qualified to teach {subject}.', 'error')
            else:
                ok, reason = database.check_availability(tutor_id, date, start_time, length_mins)
                if not ok:
                    flash(reason, 'error')
                else:
                    database.book_session(student_id, tutor_id, date, start_time, length_mins)
                    flash('Session booked.', 'success')
                    return redirect(url_for('sessions', subject=subject) if subject else url_for('sessions'))
    elif slot_error:
        flash(slot_error, 'error')

    subjects = {}
    for tutor in database.get_tutors():
        for entry in tutor['subjects'].split(','):
            if entry.strip():
                subjects.setdefault(entry.strip().casefold(), entry.strip())
    return render_template('sessions.html',
        students=database.get_students(),
        tutors=database.get_tutors(subject, date if not slot_error else None,
                                  start_time if not slot_error else None, length_mins),
        subjects=sorted(subjects.values(), key=str.casefold),
        form_values=values,
        sessions=database.get_sessions_by_date(day_filter) if day_filter else database.get_sessions(),
        day_filter=day_filter,
    )


@app.route('/sessions/<int:session_id>/edit', methods=['GET', 'POST'])
def session_detail(session_id):
    session = database.get_session(session_id)
    if session is None:
        abort(404)

    if request.method == 'POST':
        date = request.form.get('date', '').strip()
        start_time = request.form.get('start_time', '').strip()
        length_mins = request.form.get('length_mins', '').strip()

        if not date or not start_time or not length_mins:
            flash('All fields are required.', 'error')
        else:
            ok, reason = database.check_availability(session['tutor_id'], date, start_time, int(length_mins))
            if not ok:
                flash(reason, 'error')
            else:
                database.update_session(session_id, date, start_time, int(length_mins))
                flash('Session updated.', 'success')
                return redirect(url_for('sessions'))

    return render_template('session_detail.html', session=session)


@app.route('/sessions/<int:session_id>/notes', methods=['POST'])
def session_notes(session_id):
    session = database.get_session(session_id)
    if session is None:
        abort(404)
    if 'notes' not in request.form:
        flash('Session notes are required.', 'error')
        return render_template('session_detail.html', session=session), 400

    database.update_session_notes(session_id, request.form['notes'])
    flash('Session notes saved.', 'success')
    return redirect(url_for('session_detail', session_id=session_id))


@app.route('/sessions/<int:session_id>/status', methods=['POST'])
def session_status(session_id):
    session = database.get_session(session_id)
    if session is None:
        abort(404)
    status = request.form.get('status', '').strip()
    try:
        database.update_session_status(session_id, status)
    except ValueError as error:
        flash(str(error), 'error')
    else:
        flash('Session status updated.', 'success')
    return redirect(url_for('session_detail', session_id=session_id))


@app.route('/sessions/<int:session_id>/cancel', methods=['POST'])
def cancel_session(session_id):
    session = database.get_session(session_id)
    if session is None:
        abort(404)
    database.cancel_session(session_id)
    flash('Session cancelled.', 'success')
    return redirect(url_for('sessions'))


@app.route('/schedule')
def schedule():
    # Default to this calendar week's Tuesday in the centre's Ipswich time zone.
    today = datetime.now(timezone(timedelta(hours=10))).date()
    week_start = today - timedelta(days=today.weekday()) + timedelta(days=1)
    selected_week = request.args.get('week_start')
    status_code = 200
    if selected_week is not None:
        try:
            selected_date = date.fromisoformat(selected_week)
            if selected_date.isoformat() != selected_week or selected_date.weekday() != 1:
                raise ValueError
            selected_date + timedelta(days=4)
        except (ValueError, OverflowError):
            flash('Choose a valid Tuesday date for the start of the week.', 'error')
            status_code = 400
        else:
            week_start = selected_date

    week_end = week_start + timedelta(days=4)
    sessions = database.get_week_sessions(week_start.isoformat(), week_end.isoformat())
    days = []
    for offset, name in enumerate(('Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')):
        day = (week_start + timedelta(days=offset)).isoformat()
        days.append({'name': name, 'date': day,
                     'sessions': [session for session in sessions if session['date'] == day]})

    previous_week = week_start - timedelta(days=7) if week_start.toordinal() > 7 else None
    next_week = week_start + timedelta(days=7) if (date.max - week_start).days >= 11 else None
    return render_template('schedule.html', days=days, week_start=week_start,
                           week_end=week_end, previous_week=previous_week,
                           next_week=next_week, has_sessions=bool(sessions)), status_code


if __name__ == '__main__':
    app.run(debug=app.debug, load_dotenv=False)
