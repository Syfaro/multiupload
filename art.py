from flask import Flask, render_template, request, session, redirect, jsonify, flash, url_for, g, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from bs4 import BeautifulSoup
from functools import wraps
from raven.contrib.flask import Sentry
import bcrypt
import simplecrypt
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
sentry = Sentry(app)

rng = random.SystemRandom()

headers = {
    'User-Agent': 'Furry Multiupload 0.1 / Syfaro <syfaro@foxpaw.in>'
}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(16), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    dark_theme = db.Column(db.Boolean, default=0)

    accounts = db.relationship('Account', backref='user', lazy='dynamic')

    def __init__(self, username, password):
        self.username = username.lower()
        self.password = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt())

    def verify(self, password):
        return bcrypt.hashpw(password.encode('utf-8'), self.password.encode('utf-8')) == self.password.encode('utf-8')


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
    return ''.join(rng.choice(string.ascii_lowercase) for i in range(length))


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


def git_version():
    from subprocess import Popen, PIPE
    gitproc = Popen(['git', 'rev-parse', 'HEAD'], stdout=PIPE)
    (stdout, _) = gitproc.communicate()
    return stdout.strip().decode('utf-8')

app.jinja_env.globals['git_version'] = git_version()[-7:]


def english_series(items):
    items = tuple(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(x for x in items[:-1]) + ' and ' + items[-1]


@app.route('/')
def home():
    if 'id' in session:
        user = User.query.get(session['id'])

        if user:
            return redirect(url_for('upload_form'))

    text = english_series(site.name for site in Site.query.all())

    return render_template('home.html', text=text)


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

    if len(request.form['username']) > 16:
        flash('Username is too long.')
        return redirect(url_for('home'))

    strength, improvements = passwordmeter.test(request.form['password'])
    if strength < 0.3:
        flash('Weak password. You may wish to try the following suggestions.<br><ul><li>%s</ul></ul>' %
              ('</li><li>'.join(improvements.values())))
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
    return render_template('upload.html', user=g.user, sites=Site.query.all())


def parse_description(description, uploading_to):
    exp = '<\|(\S+),(\d),(\d)\|>'
    match = re.search(exp, description)

    while match:
        start, end = match.span(0)

        try:
            username = match.group(1)
            linking_to = int(match.group(2))
            link_type = int(match.group(3))
        except:
            return False

        new_text = ''

        if uploading_to == linking_to:  # Uploading to same site
            if uploading_to == 1:  # FurAffinity
                if link_type == 0:  # Just link
                    new_text = ':link%s:' % (username)
                elif link_type == 1:  # Just icon
                    new_text = ':%sicon:' % (username)
                elif link_type == 2:  # Both
                    new_text = ':icon%s:' % (username)
            elif uploading_to == 2:  # Weasyl
                if link_type == 0:
                    new_text = '<~%s>' % (username)
                elif link_type == 1:
                    new_text = '<!%s>' % (username)
                elif link_type == 2:
                    new_text = '<!~%s>' % (username)
            elif uploading_to == 3:  # FurryNetwork
                new_text = '[{0}](https://beta.furrynetwork.com/{0}/)'.format(
                    username)
            elif uploading_to == 4:
                if link_type == 0:
                    new_text = '[name]%s[/name]' % (username)
                elif link_type == 1:
                    new_text = '[icon]%s[/icon]' % (username)
                elif link_type == 2:
                    new_text = '[iconname]%s[/iconname]' % (username)
        else:  # Uploading to other site
            if uploading_to == 1:  # Uploading to FurAffinity
                if linking_to == 2:
                    new_text = '[url=https://www.weasyl.com/~{0}]{0}[/url]'.format(
                        username)
                elif linking_to == 3:
                    new_text = '[url=https://beta.furrynetwork.com/{0}]{0}[/url]'.format(
                        username)
                elif linking_to == 4:
                    new_text = '[url=https://inkbunny.net/{0}]{0}[/url]'.format(username)
            # Uploading to FN or Weasyl (same format type)
            elif uploading_to == 2 or uploading_to == 3:
                if linking_to == 1:
                    new_text = '[{0}](https://www.furaffinity.net/user/{0}/)'.format(
                        username)
                elif linking_to == 2:  # Weasyl
                    new_text = '[{0}](https://www.weasyl.com/~{0})'.format(
                        username)
                elif linking_to == 3:  # FurryNetwork
                    new_text = '[{0}](https://beta.furrynetwork.com/{0})'.format(
                        username)
                elif linking_to == 4:
                    new_text = '[{0}](https://inkbunny.net/{0})'.format(username)
            elif uploading_to == 4:
                if linking_to == 1:
                    new_text = '[fa]%s[/fa]' % (username)
                elif linking_to == 2:
                    new_text = '[w]%s[/w]' % (username)
                elif linking_to == 3:
                    new_text = '[url=https://beta.furrynetwork.com/{0}/]{0}[/url]'.format(username)

        description = description[0:start] + new_text + description[end:]

        match = re.search(exp, description)

    # FA and Inkbunny don't support Markdown, try and convert some stuff
    if uploading_to == 1 or uploading_to == 4:
        url = re.compile('\[([^\]]+)\]\(([^)"]+)(?: \"([^\"]+)\")?\)')
        match = url.search(description)

        while match:
            start, end = match.span(0)

            new_link = '[url={url}]{text}[/url]'.format(
                text=match.group(1), url=match.group(2))
            description = description[0:start] + new_link + description[end:]

            match = url.match(description)

    return description


@app.route('/preview/description')
def preview_description():
    descriptions = []
    sites_done = []
    for site in request.args.getlist('account'):
        account = Account.query.filter_by(
            user_id=session['id']).filter_by(id=int(site)).first()
        site = account.site
        if site.id in sites_done:
            continue
        descriptions.append({'site': site.name, 'description': parse_description(
            request.args['description'], site.id)})
        sites_done.append(site.id)

    return jsonify({'descriptions': descriptions})


@app.route('/upload', methods=['POST'])
@login_required
def upload_post():
    if request.form['title'] == '':
        flash('Missing title.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if request.form['description'] == '':
        flash('Missing description.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if request.form['keywords'] == '':
        flash('Missing keywords.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if not request.files.get('image', None):
        flash('Missing image.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if len(request.form.getlist('account')) == 0:
        flash('No site selected.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if not request.form.get('rating'):
        flash('No content rating selected.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    has_less_2 = len(request.form['keywords'].split(' ')) < 2

    accounts = []
    for a in request.form.getlist('account'):
        account = Account.query.get(a)

        if not account or account.user_id != g.user.id:
            flash('Account does not exist or does not belong to current user.')
            return render_template('upload.html', user=g.user, sites=Site.query.all())

        if account.site.id == 2 and has_less_2:
            flash('Weasyl requires at least two tags.')
            return render_template('upload.html', user=g.user, sites=Site.query.all())

        accounts.append(account)

    if not g.user.verify(request.form['site_password']):
        flash('Incorrect password.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    upload = request.files.get('image', None)

    image = (upload.filename, upload.read())

    uploads = []
    for account in accounts:
        decrypted = simplecrypt.decrypt(
            request.form['site_password'], account.credentials)

        site = account.site
        description = parse_description(request.form['description'], site.id)

        if site.id == 1:
            s = requests.session()

            j = json.loads(decrypted)

            rating = '1'
            if request.form['rating'] == 'general':
                rating = '0'
            elif request.form['rating'] == 'mature':
                rating = '2'
            elif request.form['rating'] == 'explicit':
                rating = '1'

            try:
                r = s.get(
                    'https://www.furaffinity.net/submit/', cookies=j, headers=headers)
                r = s.post('https://www.furaffinity.net/submit/', data={
                    'part': '2',
                    'submission_type': 'submission'
                }, cookies=j, headers=headers)

                soup = BeautifulSoup(r.content, 'html.parser')
                key = soup.select('input[name="key"]')[0]['value']
            except:
                flash('Unable to upload to FurAffinity on account %s. Make sure the site is online. If this problem continues, you may need to remove the account and add it again.' % (
                    account.username))
                continue

            try:
                r = s.post('https://www.furaffinity.net/submit/', data={
                    'part': '3',
                    'submission_type': 'submission',
                    'key': key
                }, files={
                    'submission': image
                }, cookies=j, headers=headers)

                soup = BeautifulSoup(r.content, 'html.parser')
                key = soup.select('input[name="key"]')[0]['value']
            except:
                flash('Unable to upload to FurAffinity on account %s. Make sure the site is online. If this problem continues, you may need to remove the account and add it again.' % (
                    account.username))
                continue

            try:
                r = s.post('https://www.furaffinity.net/submit/', data={
                    'part': '5',
                    'submission_type': 'submission',
                    'key': key,
                    'title': request.form['title'],
                    'message': description,
                    'keywords': request.form['keywords'],
                    'rating': rating
                }, cookies=j, headers=headers)
            except:
                flash('An error occured while uploading to FurAffinity on account %s. Make sure the site is online.' % (
                    account.username))
                continue

            uploads.append(
                {'link': r.url, 'name': '%s - %s' % (site.name, account.username)})

        elif site.id == 2:
            s = requests.session()

            rating = '40'
            if request.form['rating'] == 'general':
                rating = '10'
            elif request.form['rating'] == 'mature':
                rating = '30'
            elif request.form['rating'] == 'explicit':
                rating = '40'

            new_header = headers.copy()
            new_header['X-Weasyl-API-Key'] = decrypted

            try:
                r = s.get(
                    'https://www.weasyl.com/submit/visual', headers=new_header)

                soup = BeautifulSoup(r.content, 'html.parser')
                token = soup.select('input[name="token"]')[0]['value']
            except:
                flash('Unable to upload to Weasyl on account %s. Make sure the site is online. If this problem continues, you may need to remove the account and add it again.' % (
                    account.username))
                continue

            try:
                r = s.post('https://www.weasyl.com/submit/visual', data={
                    'token': token,
                    'title': request.form['title'],
                    'content': description,
                    'tags': request.form['keywords'],
                    'rating': rating
                }, headers=new_header, files={
                    'submitfile': image
                })
            except:
                flash('An error occured while uploading to Weasyl on account %s. Make sure the site is online.' % (
                    account.username))
                continue

            uploads.append(
                {'link': r.url, 'name': '%s - %s' % (site.name, account.username)})

        elif site.id == 3:
            s = requests.session()

            j = json.loads(decrypted)

            character_id = j['character_id']

            try:
                r = s.post('https://beta.furrynetwork.com/api/oauth/token', {
                    'grant_type': 'refresh_token',
                    'client_id': '123',
                    'refresh_token': j['refresh']
                }, headers=headers)

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

            new_header = headers.copy()
            new_header['Authorization'] = 'Bearer %s' % (token)

            try:
                r = s.get('https://beta.furrynetwork.com/api/user', data={
                    'user_id': j['user_id']
                }, headers=new_header)

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

            try:
                r = s.get('https://beta.furrynetwork.com/api/submission/%s/artwork/upload' %
                          (username), headers=new_header, params=params)

                r = s.post('https://beta.furrynetwork.com/api/submission/%s/artwork/upload' %
                           (username), headers=new_header, params=params, data=image[1])

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

            try:
                r = s.patch('https://beta.furrynetwork.com/api/artwork/%d' % (j['id']), headers=new_header, data=json.dumps({
                    'rating': rating,
                    'description': description,
                    'title': request.form['title'],
                    'tags': request.form['keywords'].split(' '),
                    'collections': [],
                    'status': 'public'
                }))

                j = json.loads(r.content)
            except:
                flash('It appears that FurryNetwork was down while trying to post on character %s. You may need to manually set the title, description, tags, and set it to be public.' % (
                    account.username))
                continue

            uploads.append({'link': 'https://beta.furrynetwork.com/artwork/%d/' %
                            (j['id']), 'name': '%s - %s' % (site.name, account.username)})

    return render_template('after_upload.html', uploads=uploads, user=g.user)


@app.route('/add')
@login_required
def add():
    sites = Site.query.all()

    return render_template('add_site.html', sites=sites, user=g.user)


@app.route('/add/<int:site_id>', methods=['GET'])
@login_required
def add_account_form(site_id):
    site = Site.query.get(site_id)

    if not site:
        return 'Unknown site ID!'

    extra_data = {}

    if site.id == 1:  # FurAffinity
        s = requests.session()

        r = s.get('https://www.furaffinity.net/login/', headers=headers)
        session['fa_cookie_b'] = r.cookies['b']

        captcha = s.get(
            'https://www.furaffinity.net/captcha.jpg', headers=headers)

        extra_data['captcha'] = base64.b64encode(captcha.content)

    return render_template('add_site/%d.html' % (site_id), site=site, extra_data=extra_data, user=g.user)


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

        if Account.query.filter_by(site_id=site.id).filter_by(user_id=g.user.id).filter(func.lower(Account.username) == func.lower(request.form['username'])).first():
            flash('This account has already been added.')
            return redirect(url_for('upload_form'))

        r = s.post('https://www.furaffinity.net/login/', cookies={'b': session['fa_cookie_b']}, data={
            'action': 'login',
            'name': request.form['username'],
            'pass': request.form['password'],
            'captcha': request.form['captcha']
        }, allow_redirects=False, headers=headers)

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
        new_header = headers.copy()
        new_header['X-Weasyl-API-Key'] = request.form['api_token']

        r = requests.get(
            'https://www.weasyl.com/api/whoami', headers=new_header)

        try:
            j = json.loads(r.content)
        except:
            flash('Invalid API Token')
            return redirect(url_for('add_account_form', site_id=site.id))

        if 'login' not in j:
            flash('Invalid API Token')
            return redirect(url_for('add_account_form', site_id=site.id))

        if Account.query.filter_by(site_id=site.id).filter_by(user_id=g.user.id).filter(func.lower(Account.username) == func.lower(j['login'])).first():
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
        }, headers=headers)

        try:
            j = json.loads(r.content)
        except:
            flash('Invalid username and password, or site is down.')
            return redirect(url_for('add_account_form', site_id=site.id))

        if 'refresh_token' not in j:
            flash('Invalid username and password.')
            return redirect(url_for('add_account_form', site_id=site.id))

        refresh_token = j['refresh_token']

        new_header = headers.copy()
        new_header['Authorization'] = 'Bearer %s' % (j['access_token'])

        r = requests.get('https://beta.furrynetwork.com/api/user', data={
            'user_id': j['user_id']
        }, headers=new_header)

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

    elif site.id == 4:
        if Account.query.filter_by(site_id=site.id).filter_by(user_id=g.user.id).filter(func.lower(Account.username) == func.lower(request.form['username'])).first():
            flash('This account has already been added.')
            return redirect(url_for('upload_form'))

        try:
            r = requests.get('https://inkbunny.net/api_login.php', params={
                'username': request.form['username'],
                'password': request.form['password']
            })

            j = json.loads(r.content.decode('utf-8'))

            if not 'sid' in j or j['sid'] == '':
                raise Exception('Invalid username or password.')
        except:
            flash('Invalid username and password.')
            return redirect(url_for('add_account_form', site_id=site.id))

        account = Account(site.id, session['id'], request.form['username'], json.dumps({
            'username': request.form['username'],
            'password': request.form['password']
        }), request.form['site_password'])

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

    return render_template('remove.html', account=account, user=g.user)


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


@app.route('/changepass', methods=['GET'])
@login_required
def change_password_form():
    return render_template('change_password.html', user=g.user)


@app.route('/changepass', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password', None)
    if not current_password:
        flash('Missing current password.')
        return redirect(url_for('change_password_form'))

    new_password = request.form.get('new_password', None)
    if not new_password:
        flash('Missing new password.')
        return redirect(url_for('change_password_form'))

    new_password_confirm = request.form.get('new_password_confirm', None)
    if not new_password_confirm or new_password != new_password_confirm:
        flash('Password confirmation does not match.')
        return redirect(url_for('change_password_form'))

    strength, improvements = passwordmeter.test(new_password)
    if strength < 0.3:
        flash('Weak password. You may wish to try the following suggestions.<br><ul><li>%s</ul></ul>' %
              ('</li><li>'.join(improvements.values())))
        return redirect(url_for('change_password_form'))

    if not g.user.verify(current_password):
        flash('Current password is incorrect.')
        return redirect(url_for('change_password_form'))

    g.user.password = bcrypt.hashpw(
        new_password.encode('utf-8'), bcrypt.gensalt())

    for account in Account.query.filter_by(user_id=g.user.id).all():
        decrypted = simplecrypt.decrypt(current_password, account.credentials)
        encrypted = simplecrypt.encrypt(new_password, decrypted)
        account.credentials = encrypted

    db.session.commit()

    flash('Password changed.')
    return redirect(url_for('upload_form'))


@app.route('/switchtheme')
@login_required
def switchtheme():
    g.user.dark_theme = not g.user.dark_theme

    db.session.commit()

    return redirect(url_for('upload_form'))

if __name__ == '__main__':
    db.create_all()
    app.run()
