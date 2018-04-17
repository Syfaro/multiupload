import passwordmeter
import requests
from flask import Blueprint, current_app
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from sqlalchemy import func

from models import User
from models import db
from sites.known import known_names, KNOWN_SITES
from utils import english_series
from utils import get_active_notices
from utils import send_to_influx

app = Blueprint('home', __name__)


@app.route('/')
def home():
    if 'id' in session:
        user = User.query.get(session['id'])

        if user:
            return redirect(url_for('upload.create_art'))

    text = english_series(known_names())

    return render_template('home.html', text=text, notices=get_active_notices())


@app.route('/features')
def features():
    if 'id' in session:
        g.user = User.query.get(session['id'])

    return render_template('features.html', sites=KNOWN_SITES)


@app.route('/upload')
def upload_redir():
    return redirect(url_for('upload.create_art'))


@app.route('/logout')
def logout():
    session.clear()

    return redirect(url_for('home.home'))


@app.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')

    if not username:
        flash('Missing username.')
        return redirect(url_for('home.home'))

    if not password:
        flash('Missing password.')
        return redirect(url_for('home.home'))

    user = User.by_name_or_email(username)

    if not user or not user.verify(password):
        flash('Invalid username or password.')
        return redirect(url_for('home.home'))

    if username == user.email and not user.email_verified:
        flash('You have not yet verified this email.')
        return redirect(url_for('home.home'))

    session['id'] = user.id
    session['password'] = password

    return redirect(url_for('upload.create_art'))


@app.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    email = request.form.get('email')

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

    if email:
        if '@' not in email:
            flash('Invalid email.')
            return redirect(url_for('home.home'))

        user = User.query.filter(func.lower(User.email) == func.lower(email)).first()

        if user:
            flash('Email already in use.')
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

    by_username = User.query.filter(func.lower(User.username) == func.lower(username)).first()

    if by_username is not None:
        flash('Username is already in use.')
        return redirect(url_for('home.home'))

    if password != confirm_password:
        flash('Password does not match confirmation.')
        return redirect(url_for('home.home'))

    user = User(username, password, email)

    db.session.add(user)
    db.session.commit()

    session['id'] = user.id
    session['password'] = password

    if email:
        with open('templates/email.txt') as f:
            email_body = f.read()

        requests.post(current_app.config['MAILGUN_ENDPOINT'], auth=('api', current_app.config['MAILGUN_KEY']), data={
            'from': current_app.config['MAILGUN_ADDRESS'],
            'to': email,
            'subject': 'Verify your Furry Art Multiuploader email address',
            'h:Reply-To': 'syfaro@huefox.com',
            'text': email_body.format(username=username,
                                      link=current_app.config['MAILGUN_VERIFY'].format(user.email_verifier))
        })

        flash('A link was sent to you to verify your email address.')

    return redirect(url_for('upload.create_art'))
