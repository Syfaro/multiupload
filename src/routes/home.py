import passwordmeter
from flask import Blueprint
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from models import User
from models import db
from sites.known import known_names
from utils import english_series
from utils import get_active_notices
from utils import send_to_influx

app = Blueprint('home', __name__)


@app.route('/')
def home():
    if 'id' in session:
        user = User.query.get(session['id'])

        if user:
            return redirect(url_for('upload.create'))

    text = english_series(known_names())

    return render_template('home.html', text=text, notices=get_active_notices())


@app.route('/logout')
def logout():
    session.pop('id', None)

    return redirect(url_for('home.home'))


@app.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username', None)
    password = request.form.get('password', None)

    if not username:
        flash('Missing username.')
        return redirect(url_for('home.home'))

    if not password:
        flash('Missing password.')
        return redirect(url_for('home.home'))

    user = User.query.filter_by(username=username).first()

    if not user or not user.verify(password):
        flash('Invalid username or password.')
        return redirect(url_for('home.home'))

    session['id'] = user.id
    session['password'] = password

    return redirect(url_for('upload.create'))


@app.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username', None)
    password = request.form.get('password', None)
    confirm_password = request.form.get('confirm_password', None)

    if not username:
        flash('Missing username.')
        return redirect(url_for('home.home'))

    if not password:
        flash('Missing password.')
        return redirect(url_for('home.home'))

    if not confirm_password:
        flash('Missing password confirmation.')
        return redirect(url_for('home.home'))

    if len(username) > 16:
        flash('Username is too long.')
        return redirect(url_for('home.home'))

    strength, improvements = passwordmeter.test(password)

    send_to_influx({
        "measurement": "password_strength",
        "fields": {
            "strength": strength,
        },
    })

    if strength < 0.3:
        flash('Weak password. You may wish to try the following suggestions.<br><ul><li>%s</ul></ul>' %
              ('</li><li>'.join(improvements.values())))
        return redirect(url_for('home.home'))

    by_username = User.query.filter_by(username=username.lower()).first()
    if by_username is not None:
        flash('Username is already in use.')
        return redirect(url_for('home.home'))

    if password != confirm_password:
        flash('Password does not match confirmation.')
        return redirect(url_for('home.home'))

    user = User(username, password)

    db.session.add(user)
    db.session.commit()

    session['id'] = user.id
    session['password'] = password

    return redirect(url_for('upload.create'))
