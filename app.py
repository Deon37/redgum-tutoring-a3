from flask import Flask, render_template
import database

app = Flask(__name__)

database.init_app(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/students')
def students():
    return render_template('index.html')


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
