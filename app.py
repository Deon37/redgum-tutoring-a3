from flask import Flask, render_template, request, redirect, url_for, flash
import database

app = Flask(__name__)
app.secret_key = 'dev'

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


@app.route('/tutors')
def tutors():
    return render_template('index.html')


@app.route('/sessions')
def sessions():
    return render_template('index.html')


@app.route('/schedule')
def schedule():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
