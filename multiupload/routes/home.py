from typing import Any

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
import passwordmeter
import requests
from sqlalchemy import func

from multiupload.models import Notice, User, db
from multiupload.sites.known import KNOWN_SITES, known_names
from multiupload.utils import english_series, get_active_notices, send_to_influx

app = Blueprint('home', __name__)


@app.route('/')
def home() -> Any:
    if 'id' in session and User.query.get(session['id']):
        return redirect(url_for('upload.create_art'))

    text = english_series(known_names())

    return render_template('home.html', text=text)


@app.route('/features')
def features() -> Any:
    if 'id' in session:
        g.user = User.query.get(session['id'])

    return render_template('features.html', sites=KNOWN_SITES)


@app.route('/upload')
def upload_redir() -> Any:
    return redirect(url_for('upload.create_art'))


@app.route('/logout')
def logout() -> Any:
    session.clear()

    return redirect(url_for('home.home'))


@app.route('/login', methods=['POST'])
def login_post() -> Any:
    username: str = request.form.get('username', '')
    password: str = request.form.get('password', '')

    if not username:
        flash('Missing username.')
        return redirect(url_for('home.home'))

    session['username'] = username

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

    redir = session.pop('redir', None)
    if redir:
        return redirect(redir)

    return redirect(url_for('upload.create_art'))


@app.route('/register', methods=['POST'])
def register_post() -> Any:
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    email = request.form.get('email', '')

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

    if password != confirm_password:
        flash('Password does not match confirmation.')
        return redirect(url_for('home.home'))

    if email:
        if '@' not in email:
            flash('Invalid email.')
            return redirect(url_for('home.home'))

        # Ensure email is not in use
        if User.query.filter(func.lower(User.email) == func.lower(email)).first():
            flash('Email already in use.')
            return redirect(url_for('home.home'))

    strength, improvements = passwordmeter.test(password)

    send_to_influx(
        {"measurement": "password_strength", "fields": {"strength": strength}}
    )

    if strength < 0.3:
        flash(
            'Weak password. You may wish to try the following suggestions.<br><ul><li>%s</ul></ul>'
            % ('</li><li>'.join(improvements.values()))
        )
        return redirect(url_for('home.home'))

    # Ensure username is not in use
    if (
        User.query.filter(func.lower(User.username) == func.lower(username)).first()
        is not None
    ):
        flash('Username is already in use.')
        return redirect(url_for('home.home'))

    user = User(username, password, email)

    db.session.add(user)
    db.session.commit()

    session['id'] = user.id
    session['password'] = password

    if email:
        with open('multiupload/templates/email.txt') as f:
            email_body = f.read()

        requests.post(
            current_app.config['MAILGUN_ENDPOINT'],
            auth=('api', current_app.config['MAILGUN_KEY']),
            data={
                'from': current_app.config['MAILGUN_ADDRESS'],
                'to': email,
                'subject': 'Verify your Furry Art Multiuploader email address',
                'h:Reply-To': 'syfaro@huefox.com',
                'text': email_body.format(
                    username=username,
                    link=current_app.config['MAILGUN_VERIFY'].format(
                        user.email_verifier
                    ),
                ),
            },
        )

        flash('A link was sent to you to verify your email address.')

    return redirect(url_for('upload.create_art'))


@app.app_template_global('notices')
def global_notices() -> Any:  # TODO: not be any
    if hasattr(g, 'user'):
        return get_active_notices(g.user.id)
    else:
        return Notice.find_active()
