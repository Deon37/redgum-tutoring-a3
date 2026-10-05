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

    return render_template('student_detail.html', student=student)


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


@app.route('/availability/<int:availability_id>/delete', methods=['POST'])
def delete_availability(availability_id):
    database.delete_availability(availability_id)
    tutor_id = request.form.get('tutor_id')
    return redirect(url_for('availability', tutor_id=tutor_id))


@app.route('/sessions', methods=['GET', 'POST'])
def sessions():
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        tutor_id = request.form.get('tutor_id', '').strip()
        date = request.form.get('date', '').strip()
        start_time = request.form.get('start_time', '').strip()
        length_mins = request.form.get('length_mins', '').strip()
        if not student_id or not tutor_id or not date or not start_time or not length_mins:
            flash('All fields are required.', 'error')
        else:
            ok, reason = database.check_availability(tutor_id, date, start_time, int(length_mins))
            if not ok:
                flash(reason, 'error')
            else:
                database.book_session(student_id, tutor_id, date, start_time, int(length_mins))
                flash('Session booked.', 'success')
                return redirect(url_for('sessions'))
    return render_template('sessions.html',
        students=database.get_students(),
        tutors=database.get_tutors(),
        sessions=database.get_sessions()
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


@app.route('/schedule')
def schedule():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=app.debug, load_dotenv=False)
