from flask import Flask, render_template, request, session, redirect, jsonify, flash, url_for, g, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from bs4 import BeautifulSoup
from functools import wraps
import bcrypt
import simplecrypt
import pymysql
import requests
import base64
import json
import re
import string
import random
import passwordmeter

app = Flask(__name__)

app.config.from_object('config')

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(16), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    accounts = db.relationship('Account', backref='user', lazy='dynamic')

    def __init__(self, username, password):
        self.username = username.lower()
        self.password = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt())

    def verify(self, password):
        return bcrypt.hashpw(password.encode('utf-8'), self.password.encode('utf-8')) == self.password


class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def __init__(self, name):
        self.name = name


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(120), nullable=False)
    credentials = db.Column(db.LargeBinary, nullable=False)

    site = db.relationship(
        'Site', backref=db.backref('account', lazy='dynamic'))

    def __init__(self, site_id, user_id, username, credentials, password):
        self.site_id = site_id
        self.user_id = user_id
        self.username = username
        self.credentials = simplecrypt.encrypt(password, credentials)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not 'id' in session:
            return redirect(url_for('home'))

        user = User.query.get(session['id'])

        if not user:
            return redirect(url_for('home'))

        g.user = user

        return f(*args, **kwargs)

    return decorated_function


def random_string(length):
    return ''.join(random.choice(string.lowercase) for i in range(length))


@app.before_request
def csrf_protect():
    if request.method == 'POST':
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            abort(403)


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = random_string(16)
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token


@app.route('/')
def home():
    if 'id' in session:
        user = User.query.get(session['id'])

        if user:
            return redirect(url_for('upload_form'))

    count = Site.query.count()

    return render_template('home.html', count=count)


@app.route('/logout')
def logout():
    session.pop('id', None)

    return redirect(url_for('home'))


@app.route('/login', methods=['POST'])
def login():
    if 'username' not in request.form or request.form['username'] == '':
        flash('Missing username.')
        return redirect(url_for('home'))

    if 'password' not in request.form or request.form['password'] == '':
        flash('Missing password.')
        return redirect(url_for('home'))

    user = User.query.filter_by(username=request.form['username']).first()

    if not user or not user.verify(request.form['password']):
        flash('Invalid username or password.')
        return redirect(url_for('home'))

    session['id'] = user.id

    return redirect(url_for('upload_form'))


@app.route('/register', methods=['POST'])
def register():
    if 'username' not in request.form or request.form['username'] == '':
        flash('Missing username.')
        return redirect(url_for('home'))

    if 'password' not in request.form or request.form['password'] == '':
        flash('Missing password.')
        return redirect(url_for('home'))

    if 'confirm_password' not in request.form or request.form['confirm_password'] == '':
        flash('Missing password confirmation.')
        return redirect(url_for('home'))

    strength, improvements = passwordmeter.test(request.form['password'])
    if strength < 0.3:
        flash('Weak password.')
        return redirect(url_for('home'))

    by_username = User.query.filter_by(
        username=request.form['username'].lower()).first()
    if by_username is not None:
        flash('Username is already in use.')
        return redirect(url_for('home'))

    if request.form['password'] != request.form['confirm_password']:
        flash('Password does not match confirmation.')
        return redirect(url_for('home'))

    user = User(request.form['username'], request.form['password'])

    db.session.add(user)
    db.session.commit()

    session['id'] = user.id

    return redirect(url_for('upload_form'))


@app.route('/upload', methods=['GET'])
@login_required
def upload_form():
    return render_template('upload.html', user=g.user)


@app.route('/upload', methods=['POST'])
@login_required
def upload_post():
    if request.form['title'] == '':
        flash('Missing title.')
        return render_template('upload.html', user=g.user)

    if request.form['description'] == '':
        flash('Missing description.')
        return render_template('upload.html', user=g.user)

    if request.form['keywords'] == '':
        flash('Missing keywords.')
        return render_template('upload.html', user=g.user)

    if not request.files.get('image', None):
        flash('Missing image.')
        return render_template('upload.html', user=g.user)

    if len(request.form.getlist('account')) == 0:
        flash('No site selected.')
        return render_template('upload.html', user=g.user)

    if not request.form.get('rating'):
        flash('No content rating selected.')
        return render_template('upload.html', user=g.user)

    has_less_2 = len(request.form['keywords'].split(' ')) < 2

    accounts = []
    for a in request.form.getlist('account'):
        account = Account.query.get(a)

        if not account or account.user_id != g.user.id:
            flash('Account does not exist or does not belong to current user.')
            return render_template('upload.html', user=g.user)

        if account.site.id == 2 and has_less_2:
            flash('Weasyl requires at least two tags.')
            return render_template('upload.html', user=g.user)

        accounts.append(account)

    if not g.user.verify(request.form['site_password']):
        flash('Incorrect password.')
        return render_template('upload.html', user=g.user)

    upload = request.files.get('image', None)

    image = (upload.filename, upload.read())

    uploads = []
    for account in accounts:
        decrypted = simplecrypt.decrypt(
            request.form['site_password'], account.credentials)

        site = account.site

        if site.id == 1:
            s = requests.session()

            j = json.loads(decrypted)

            rating = '2'
            if request.form['rating'] == 'general':
                rating = '0'
            elif request.form['rating'] == 'mature':
                rating = '2'
            elif request.form['rating'] == 'explicit':
                rating = '1'

            r = s.get('https://www.furaffinity.net/submit/', cookies=j)
            r = s.post('https://www.furaffinity.net/submit/', data={
                'part': '2',
                'submission_type': 'submission'
            }, cookies=j)
            soup = BeautifulSoup(r.content, 'html.parser')
            try:
                key = soup.select('input[name="key"]')[0]['value']
            except:
                flash('Unable to upload to FurAffinity on account %s. Make sure the site is online. If this problem continues, you may need to remove the account and add it again.' % (
                    account.username))
                continue
            r = s.post('https://www.furaffinity.net/submit/', data={
                'part': '3',
                'submission_type': 'submission',
                'key': key
            }, files={
                'submission': image
            }, cookies=j)
            soup = BeautifulSoup(r.content, 'html.parser')
            try:
                key = soup.select('input[name="key"]')[0]['value']
            except:
                flash('Unable to upload to FurAffinity on account %s. Make sure the site is online. If this problem continues, you may need to remove the account and add it again.' % (
                    account.username))
                continue
            r = s.post('https://www.furaffinity.net/submit/', data={
                'part': '5',
                'submission_type': 'submission',
                'key': key,
                'title': request.form['title'],
                'message': request.form['description'],
                'keywords': request.form['keywords'],
                'rating': rating
            }, cookies=j)

            uploads.append(
                {'link': r.url, 'name': '%s - %s' % (site.name, account.username)})

        elif site.id == 2:
            s = requests.session()

            rating = '40'
            if request.form['rating'] == 'general':
                rating = '10'
            elif request.form['rating'] == 'mature':
                rating = '20'
            elif request.form['rating'] == 'explicit':
                rating = '40'

            r = s.get('https://www.weasyl.com/submit/visual', headers={
                'X-Weasyl-API-Key': decrypted
            })
            soup = BeautifulSoup(r.content, 'html.parser')
            try:
                token = soup.select('input[name="token"]')[0]['value']
            except:
                flash('Unable to upload to Weasyl on account %s. Make sure the site is online. If this problem continues, you may need to remove the account and add it again.' % (
                    account.username))
                continue
            r = s.post('https://www.weasyl.com/submit/visual', data={
                'token': token,
                'title': request.form['title'],
                'content': request.form['description'],
                'tags': request.form['keywords'],
                'rating': rating
            }, headers={
                'X-Weasyl-API-Key': decrypted
            }, files={
                'submitfile': image
            })

            uploads.append(
                {'link': r.url, 'name': '%s - %s' % (site.name, account.username)})

        elif site.id == 3:
            s = requests.session()

            j = json.loads(decrypted)
            character_id = j['character_id']

            r = s.post('https://beta.furrynetwork.com/api/oauth/token', {
                'grant_type': 'refresh_token',
                'client_id': '123',
                'refresh_token': j['refresh']
            })

            try:
                j = json.loads(r.content)
            except:
                flash('Unable to upload to FurryNetwork on character %s. Make sure the site is online. If this problem continues, you may need to remove the account and add it again.' % (
                    account.username))
                continue

            if not 'access_token' in j:
                flash('It appears your access token to FurryNetwork on character %s has expired. Please remove the account and add it again.' % (
                    account.username))
                continue

            token = j['access_token']

            r = s.get('https://beta.furrynetwork.com/api/user', data={
                'user_id': j['user_id']
            }, headers={
                'Authorization': 'Bearer %s' % (token)
            })

            try:
                j = json.loads(r.content)
            except:
                flash('It appears that FurryNetwork was down while trying to post on character %s. Please try again later.' % (
                    account.username))
                continue

            username = ''
            for character in j['characters']:
                if character['id'] == character_id:
                    username = character['name']

            if username == '':
                flash('It appears the character %s was removed from FurryNetwork. Please remove this character.' % (
                    user.username))
                continue

            params = {
                'resumableChunkNumber': '1',
                'resumableChunkSize': len(image[1]),
                'resumableCurrentChunkSize': len(image[1]),
                'resumableTotalSize': len(image[1]),
                'resumableType': upload.mimetype,
                'resumableIdentifier': '%d-%s' % (len(image[1]), re.sub('\W+', '', upload.filename)),
                'resumableFilename': upload.filename,
                'resumableRelativePath': upload.filename,
                'resumableTotalChunks': '1'
            }

            r = s.get('https://beta.furrynetwork.com/api/submission/%s/artwork/upload' % (username), headers={
                'Authorization': 'Bearer %s' % (token)
            }, params=params)

            r = s.post('https://beta.furrynetwork.com/api/submission/%s/artwork/upload' % (username), headers={
                'Authorization': 'Bearer %s' % (token)
            }, params=params, data=image[1])

            try:
                j = json.loads(r.content)
            except:
                flash('It appears that FurryNetwork was down while trying to post on character %s. Please try again later.' % (
                    account.username))
                continue

            rating = 2
            if request.form['rating'] == 'general':
                rating = 0
            elif request.form['rating'] == 'mature':
                rating = 1
            elif request.form['rating'] == 'explicit':
                rating = 2

            r = s.patch('https://beta.furrynetwork.com/api/artwork/%d' % (j['id']), headers={
                'Authorization': 'Bearer %s' % (token)
            }, data=json.dumps({
                'rating': rating,
                'description': request.form['description'],
                'title': request.form['title'],
                'tags': request.form['keywords'].split(' '),
                'collections': [],
                'status': 'public'
            }))

            uploads.append({'link': 'https://beta.furrynetwork.com/artwork/%d/' %
                            (j['id']), 'name': '%s - %s' % (site.name, account.username)})

    return render_template('after_upload.html', uploads=uploads)


@app.route('/add')
@login_required
def add():
    sites = Site.query.all()

    return render_template('add_site.html', sites=sites)


@app.route('/add/<int:site_id>', methods=['GET'])
@login_required
def add_account_form(site_id):
    site = Site.query.get(site_id)

    if not site:
        return 'Unknown site ID!'

    extra_data = {}

    if site.id == 1:  # FurAffinity
        s = requests.session()

        r = s.get('https://www.furaffinity.net/login/')
        session['fa_cookie_b'] = r.cookies['b']

        captcha = s.get('https://www.furaffinity.net/captcha.jpg')

        extra_data['captcha'] = base64.b64encode(captcha.content)

    return render_template('add_site/%d.html' % (site_id), site=site, extra_data=extra_data)


@app.route('/add/<int:site_id>', methods=['POST'])
@login_required
def add_account_post(site_id):
    site = Site.query.get(site_id)

    if not site:
        flash('Unknown site ID.')
        return redirect(url_for('add_account_form'))

    if not g.user.verify(request.form['site_password']):
        flash('You need to correctly enter the password for this website.')
        return redirect(url_for('add_account_form', site_id=site.id))

    if site.id == 1:  # FurAffinity
        s = requests.session()

        if Account.query.filter_by(site_id=site.id).filter_by(user_id=g.user.id).filter(func.lower(Account.username)==func.lower(request.form['username'])).first():
            flash('This account has already been added.')
            return redirect(url_for('upload_form'))

        r = s.post('https://www.furaffinity.net/login/', cookies={'b': session['fa_cookie_b']}, data={
            'action': 'login',
            'name': request.form['username'],
            'pass': request.form['password'],
            'captcha': request.form['captcha']
        }, allow_redirects=False)

        if 'a' not in r.cookies:
            flash(
                'Please make sure you entered your username, password, and the captcha correctly.')
            return redirect(url_for('add_account_form', site_id=site.id))

        secure_data = {
            'a': r.cookies['a'],
            'b': session['fa_cookie_b']
        }

        j = json.dumps(secure_data).encode('utf-8')

        account = Account(
            site.id, session['id'], request.form['username'], j, request.form['site_password'])

        db.session.add(account)
        db.session.commit()

        session.pop('fa_cookie_b', None)

    elif site.id == 2:
        r = requests.get('https://www.weasyl.com/api/whoami', headers={
            'X-Weasyl-API-Key': request.form['api_token']
        })

        try:
            j = json.loads(r.content)
        except:
            flash('Invalid API Token')
            return redirect(url_for('add_account_form', site_id=site.id))

        if 'login' not in j:
            flash('Invalid API Token')
            return redirect(url_for('add_account_form', site_id=site.id))

        if Account.query.filter_by(site_id=site.id).filter_by(user_id=g.user.id).filter(func.lower(Account.username)==func.lower(j['login'])).first():
            flash('This account has already been added.')
            return redirect(url_for('upload_form'))

        account = Account(site.id, session['id'], j['login'], request.form[
                          'api_token'], request.form['site_password'])

        db.session.add(account)
        db.session.commit()

    elif site.id == 3:
        r = requests.post('https://beta.furrynetwork.com/api/oauth/token', data={
            'username': request.form['email'],
            'password': request.form['password'],
            'grant_type': 'password',
            'client_id': '123',
            'client_secret': ''
        })

        try:
            j = json.loads(r.content)
        except:
            flash('Invalid username and password, or site is down.')
            return redirect(url_for('add_account_form', site_id=site.id))

        if 'refresh_token' not in j:
            flash('Invalid username and password.')
            return redirect(url_for('add_account_form', site_id=site.id))

        refresh_token = j['refresh_token']

        r = requests.get('https://beta.furrynetwork.com/api/user', data={
            'user_id': j['user_id']
        }, headers={
            'Authorization': 'Bearer %s' % (j['access_token'])
        })

        try:
            j = json.loads(r.content)
        except:
            flash('Site is likely down, please try again later.')
            return redirect(url_for('add_account_form', site_id=site.id))

        previous_accounts = Account.query.filter_by(
            user_id=g.user.id).filter_by(site_id=site.id).all()

        for character in j['characters']:
            character_exists = False

            for account in previous_accounts:
                account_data = simplecrypt.decrypt(
                    request.form['site_password'], account.credentials)

                j = json.loads(account_data)

                if j['character_id'] == character['id']:
                    flash('Character %s already in database.' %
                          (character['name']))
                    character_exists = True
                    break

            if character_exists:
                continue

            creds = {'character_id': character['id'], 'refresh': refresh_token}

            account = Account(site.id, session['id'], character['display_name'], json.dumps(
                creds), request.form['site_password'])

            db.session.add(account)

        db.session.commit()

    return redirect(url_for('upload_form'))


@app.route('/remove/<int:account_id>')
@login_required
def remove_form(account_id):
    account = Account.query.get(account_id)

    if not account:
        flash('Account does not exist.')
        return redirect(url_for('upload_form'))

    if account.user_id != g.user.id:
        flash('Account does not belong to you.')
        return redirect(url_for('upload_form'))

    return render_template('remove.html', account=account)


@app.route('/remove', methods=['POST'])
@login_required
def remove():
    account = Account.query.get(request.form['id'])

    if not account:
        flash('Account does not exist.')
        return redirect(url_for('upload_form'))

    if account.user_id != g.user.id:
        flash('Account does not belong to you.')
        return redirect(url_for('upload_form'))

    db.session.delete(account)
    db.session.commit()

    flash('Account removed.')
    return redirect(url_for('upload_form'))

if __name__ == '__main__':
    db.create_all()
    app.run()
