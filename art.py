from flask import Flask, render_template, request, session, redirect, jsonify, flash, url_for, g, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from bs4 import BeautifulSoup
from functools import wraps
from raven.contrib.flask import Sentry
from PIL import Image
from description import parse_description
from flask_influxdb import InfluxDB
import io
import bcrypt
import simplecrypt
import requests
import base64
import json
import re
import string
import random
import passwordmeter
import time
import tweepy

app = Flask(__name__)

app.config.from_object('config')

db = SQLAlchemy(app)
sentry = Sentry(app)
influx = InfluxDB(app)

rng = random.SystemRandom()

headers = {
    'User-Agent': 'Furry Multiupload 0.1 / Syfaro <syfaro@foxpaw.in>'
}


def current_time():
    return float(time.time())


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
        selfpassword = self.password.encode('utf-8')
        return bcrypt.hashpw(password.encode('utf-8'), selfpassword) == selfpassword


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
    used_last = db.Column(db.Boolean, default=True)

    site = db.relationship(
        'Site', backref=db.backref('account', lazy='dynamic'))

    config = db.relationship('AccountConfig', lazy='dynamic', cascade='delete')

    def __init__(self, site_id, user_id, username, credentials, password):
        self.site_id = site_id
        self.user_id = user_id
        self.username = username
        self.credentials = simplecrypt.encrypt(password, credentials)

    def __getitem__(self, arg):
        return self.config.filter_by(key=arg).first()


class AccountConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    account_id = db.Column(
        db.Integer, db.ForeignKey('account.id'), nullable=False)

    key = db.Column(db.String(120), nullable=False)
    val = db.Column(db.String(120), nullable=False)

    account = db.relationship('Account', back_populates='config')

    def __init__(self, account_id, key, val):
        self.account_id = account_id
        self.key = key
        self.val = val


class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=1, nullable=False)

    def __init__(self, text):
        self.text = text

    def wasViewedBy(self, user):
        return NoticeViewed.query.filter_by(notice_id=self.id, user_id=user).first()


class NoticeViewed(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, notice, user):
        self.notice_id = notice
        self.user_id = user


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

app.jinja_env.globals['git_version'] = git_version()[:7]


def english_series(items):
    items = tuple(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(x for x in items[:-1]) + ' and ' + items[-1]


if not app.debug:
    @app.errorhandler(Exception)
    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template('500.html',
                               event_id=g.sentry_event_id,
                               public_dsn=sentry.client.get_public_dsn('https')
                               )


def get_active_notices(for_user=None):
    notices = Notice.query.filter_by(active=True).order_by(Notice.id.desc()).all()

    if for_user:
        notices = filter(lambda x: not x.wasViewedBy(for_user), notices)

    return notices


@app.route('/')
def home():
    if 'id' in session:
        user = User.query.get(session['id'])

        if user:
            return redirect(url_for('upload_form'))

    text = english_series(site.name for site in Site.query.all())

    return render_template('home.html', text=text, notices=get_active_notices())


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
    influx.connection.write_points([{
        "measurement": "password_strength",
        "fields": {
            "strength": strength,
        },
    }])

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
    return render_template('upload.html', user=g.user, sites=Site.query.all(), notices=get_active_notices(for_user=g.user.id))


@app.route('/dismiss/<int:alert>', methods=['POST'])
@login_required
def dismiss_notice(alert):
    viewed = NoticeViewed(alert, g.user.id)

    db.session.add(viewed)
    db.session.commit()

    return 'Saved'


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


def write_upload_time(starttime, site=None, measurement="upload_time"):
    time = current_time()
    duration = time - starttime

    point = {
        "measurement": measurement,
        "fields": {
            "length": duration,
        },
    }

    if site:
        point['tags'] = {'site': site}

    influx.connection.write_points([point])


@app.route('/upload', methods=['POST'])
@login_required
def upload_post():
    totaltime = current_time()

    if request.form['title'] == '':
        flash('Missing title.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if request.form['description'] == '':
        flash('Missing description.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if request.form['keywords'] == '':
        flash('Missing keywords.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    hashtags = []
    for keyword in request.form['keywords'].split(' '):
        if keyword.startswith('#'):
            hashtags.append(keyword)
    hashtags = ' '.join(hashtags)

    keywords = ' '.join(filter(lambda x: not x.startswith('#'), request.form['keywords'].split(' ')))

    has_less_2 = len(keywords.split(' ')) < 2

    if not request.files.get('image', None):
        flash('Missing image.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if len(request.form.getlist('account')) == 0:
        flash('No site selected.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if not request.form.get('rating'):
        flash('No content rating selected.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    for account in Account.query.filter_by(user_id=g.user.id).all():
        account.used_last = 0

    basicError = False

    accounts = []
    for a in request.form.getlist('account'):
        account = Account.query.get(a)

        if not account or account.user_id != g.user.id:
            flash('Account does not exist or does not belong to current user.')
            return render_template('upload.html', user=g.user, sites=Site.query.all())

        account.used_last = 1

        if account.site.id == 2 and has_less_2:
            flash('Weasyl requires at least two tags.')
            basicError = True

        if account.site.id == 5 and has_less_2:
            flash('SoFurry requires at least two tags.')
            basicError = True

        accounts.append(account)

    db.session.commit()

    if basicError:
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    if not g.user.verify(request.form['site_password']):
        flash('Incorrect password.')
        return render_template('upload.html', user=g.user, sites=Site.query.all())

    upload = request.files.get('image', None)

    image = (upload.filename, upload.read())

    accounts = sorted(accounts, key=lambda account: account.site_id)

    try:
        twitter_link_id = request.form.get('twitterlink', None)
        if twitter_link_id is not None:
            twitter_link_id = int(twitter_link_id)
    except:
        print('Bad twitterlink ID')
    twitter_link = None

    uploads = []
    for account in accounts:
        decrypted = simplecrypt.decrypt(
            request.form['site_password'], account.credentials)

        starttime = current_time()

        site = account.site
        description = parse_description(request.form['description'], site.id)

        link = None

        if site.id == 1:
            s = requests.session()

            j = json.loads(decrypted.decode('utf-8'))

            rating = '1'
            if request.form['rating'] == 'general':
                rating = '0'
            elif request.form['rating'] == 'mature':
                rating = '2'
            elif request.form['rating'] == 'explicit':
                rating = '1'

            original_image = io.BytesIO(image[1])
            img = Image.open(original_image)
            h, w = img.size

            has_resized = False

            if h > 1280 or w > 1280:
                img.thumbnail((1280, 1280), Image.ANTIALIAS)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                resized_image = io.BytesIO()
                img.save(resized_image, 'JPEG')
                has_resized = True

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
                    'submission': image if not has_resized else (image[0], resized_image.getvalue())
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
                    'keywords': keywords,
                    'rating': rating
                }, cookies=j, headers=headers)
            except:
                flash('An error occured while uploading to FurAffinity on account %s. Make sure the site is online.' % (
                    account.username))
                continue

            resolution = account['resolution_furaffinity']
            resolution = not resolution or resolution.val == 'yes'

            if has_resized and resolution:
                match = re.search('view\/(\d+)', r.url).group(1)

                try:
                    r = s.post('https://www.furaffinity.net/controls/submissions/changesubmission/%s/' % (match), data={
                        'update': 'yes',
                        'rebuild-thumbnail': '1'
                    }, files={
                        'newsubmission': (image[0], original_image.getvalue())
                    }, cookies=j, headers=headers)

                    flash(
                        'Image was automatically resized and reuploaded to FA for full resolution')
                except:
                    flash(
                        'Image was unable to be automatically resized for FA requirements, it has been uploaded at a lower resolution')
                    pass

            link = r.url

            uploads.append({
                'link': r.url,
                'name': '%s - %s' % (site.name, account.username)
            })

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
                    'tags': keywords,
                    'rating': rating
                }, headers=new_header, files={
                    'submitfile': image
                })
            except:
                flash('An error occured while uploading to Weasyl on account %s. Make sure the site is online.' % (
                    account.username))
                continue

            link = r.url

            uploads.append({
                'link': r.url,
                'name': '%s - %s' % (site.name, account.username)
            })

        elif site.id == 3:
            s = requests.session()

            j = json.loads(decrypted.decode('utf-8'))

            character_id = j['character_id']

            try:
                r = s.post('https://beta.furrynetwork.com/api/oauth/token', {
                    'grant_type': 'refresh_token',
                    'client_id': '123',
                    'refresh_token': j['refresh']
                }, headers=headers)

                j = json.loads(r.content.decode('utf-8'))
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

                j = json.loads(r.content.decode('utf-8'))
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

                j = json.loads(r.content.decode('utf-8'))
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
                    'tags': keywords.split(' '),
                    'collections': [],
                    'status': 'public'
                }))

                j = json.loads(r.content.decode('utf-8'))
            except:
                flash('It appears that FurryNetwork was down while trying to post on character %s. You may need to manually set the title, description, tags, and set it to be public.' % (
                    account.username))
                continue

            if 'errors' in j and 'tags' in j['errors']:
                flash('There was an error using your tags on FurryNetwork with character %s. Your submission has been uploaded, but is currently unlisted.' % (
                    account.username))
                continue
            elif 'id' not in j:
                flash('An error occured updating your submission on FurryNetwork with character %s. It has been uploaded, but is currently unlisted.' % (
                    account.username))
                continue

            link = 'https://beta.furrynetwork.com/artwork/%d/' % (j['id'])

            uploads.append({
                'link': link,
                'name': '%s - %s' % (site.name, account.username)
            })

        elif site.id == 4:
            s = requests.session()

            creds = json.loads(decrypted.decode('utf-8'))

            try:
                r = s.post(
                    'https://inkbunny.net/api_login.php', data=creds, headers=headers)
                j = json.loads(r.content.decode('utf-8'))
                if 'error_message' in j:
                    flash('Inkbunny returned error for account %s: %s' %
                          (account.username, j['error_message']))
                if 'sid' not in j:
                    raise Exception('Invalid username and password.')
            except:
                flash('Unable to login to Inkbunny on account %s. Make sure the site is online. If this problem continues, you may need to remove the account and add it again.' % (
                    account.username))
                continue

            try:
                r = s.post('https://inkbunny.net/api_upload.php', data={
                    'sid': j['sid']
                }, files={
                    'uploadedfile[]': image
                }, headers=headers)
                j = json.loads(r.content.decode('utf-8'))
                if 'error_message' in j:
                    flash('Inkbunny returned error for account %s: %s' %
                          (account.username, j['error_message']))
                if 'submission_id' not in j:
                    raise Exception('Unable to upload.')
            except:
                flash('Unable to upload to Inkbunny on account %s.' %
                      (account.username))
                continue

            try:
                data = {
                    'sid': j['sid'],
                    'submission_id': j['submission_id'],
                    'title': request.form['title'],
                    'desc': description,
                    'keywords': keywords,
                    'visibility': 'yes'
                }

                if request.form['rating'] == 'mature':
                    data['tag[2]'] = 'yes'
                elif request.form['rating'] == 'explicit':
                    data['tag[4]'] = 'yes'

                r = s.post(
                    'https://inkbunny.net/api_editsubmission.php', data=data, headers=headers)
                j = json.loads(r.content.decode('utf-8'))

                if 'error_message' in j:
                    flash('Inkbunny returned error for account %s: %s' %
                          (account.username, j['error_message']))
            except:
                flash('Unable to update Inkbunny submission on account %s.' %
                      (account.username))
                continue

            link = 'https://inkbunny.net/submissionview.php?id=%s' % (j['submission_id'])

            uploads.append({
                'link': link,
                'name': '%s - %s' % (site.name, account.username)
            })

        elif site.id == 5:
            s = requests.session()

            creds = json.loads(decrypted.decode('utf-8'))

            try:
                r = s.post('https://www.sofurry.com/user/login', data={
                    'LoginForm[sfLoginUsername]': creds['username'],
                    'LoginForm[sfLoginPassword]': creds['password']
                }, headers=headers)
            except:
                flash('SoFurry appears to be down while uploading to account %s. Please try again later.' % (
                    account.username))
                continue

            if r.url.endswith('/user/login'):
                flash('Invalid username or password.')
                continue

            if not 'sfuser' in s.cookies:
                flash('Unable to find SoFurry login cookie.')
                continue

            try:
                r = s.get(
                    'https://www.sofurry.com/upload/details?contentType=1', headers=headers)

                soup = BeautifulSoup(r.content, 'html.parser')

                key = soup.select('input[name="YII_CSRF_TOKEN"]')[0]['value']
                key2 = soup.select('#UploadForm_P_id')[0]['value']
            except:
                flash('Unable to get submission form for SoFurry on account %s.' % (
                    account.username))
                continue

            rating = '1'

            should_remap = account.config.filter_by(
                key='remap_sofurry').first()
            if should_remap and should_remap.val == 'yes':
                if request.form['rating'] == 'general':
                    rating = '0'
                elif request.form['rating'] == 'mature':
                    rating = '1'
                elif request.form['rating'] == 'explicit':
                    rating = '2'
            else:
                if request.form['rating'] == 'general':
                    rating = '0'
                elif request.form['rating'] == 'mature' or request.form['rating'] == 'explicit':
                    rating = '1'

            try:
                r = s.post('https://www.sofurry.com/upload/details?contentType=1', data={
                    'UploadForm[P_title]': request.form['title'],
                    'UploadForm[contentLevel]': rating,
                    'UploadForm[description]': description,
                    'UploadForm[formtags]': ', '.join(keywords.split(' ')),
                    'YII_CSRF_TOKEN': key,
                    'UploadForm[P_id]': key2
                }, files={
                    'UploadForm[binarycontent]': image
                }, headers=headers)
            except:
                flash(
                    'Unable to upload submission to SoFurry on account %s.' % (account.username))
                continue

            link = r.url

            uploads.append({
                'link': r.url,
                'name': '%s - %s' % (site.name, account.username)
            })

        elif site.id == 6:
            creds = json.loads(decrypted.decode('utf-8'))

            auth = tweepy.OAuthHandler(app.config['TWITTER_KEY'], app.config['TWITTER_SECRET'])
            auth.set_access_token(creds['token'], creds['secret'])

            api = tweepy.API(auth)

            i = io.BytesIO(image[1])

            status = '%s %s' % (request.form['title'], hashtags)

            if twitter_link is not None:
                status += ' ' + twitter_link

            try:
                s = api.update_with_media(filename=image[0], file=i, status=status)
            except:
                flash('Unable to upload to Twitter on account %s.' % (account.username))
                continue

            uploads.append({
                'link': 'https://twitter.com/%s/status/%s' % (s.user.screen_name, s.id_str),
                'name': '%s - %s' % (site.name, account.username)
            })

        if account.id == twitter_link_id:
            twitter_link = link

        write_upload_time(starttime, site.id)

    write_upload_time(totaltime, measurement="total_upload_time")

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

        r = s.get(
            'https://www.furaffinity.net/login/?mode=imagecaptcha', headers=headers)
        session['fa_cookie_b'] = r.cookies['b']

        try:
            src = BeautifulSoup(r.content, 'html.parser').select(
                '#captcha_img')[0]['src']
            captcha = s.get(
                'https://www.furaffinity.net' + src, headers=headers)

            extra_data['captcha'] = base64.b64encode(
                captcha.content).decode('utf-8')

        except:
            flash('Please reload the page, FurAffinty had an error.')

    elif site.id == 6:
        auth = tweepy.OAuthHandler(
            app.config['TWITTER_KEY'], app.config['TWITTER_SECRET'], app.config['TWITTER_CALLBACK'])

        try:
            auth_url = auth.get_authorization_url()
        except e:
            return 'Unable to get URL for Twitter, please try again later.'

        session['request_token'] = auth.request_token

        return redirect(auth_url)

    return render_template('add_site/%d.html' % (site_id), site=site, extra_data=extra_data, user=g.user)


@app.route('/add/<int:site_id>/callback', methods=['GET'])
@login_required
def add_account_callback(site_id):
    site = Site.query.get(site_id)

    if not site:
        return 'Unknown site ID!'

    extra_data = {}

    if site.id == 6:
        verifier = request.args.get('oauth_verifier')
        token = session.pop('request_token', None)
        auth = tweepy.OAuthHandler(
            app.config['TWITTER_KEY'], app.config['TWITTER_SECRET'], app.config['TWITTER_CALLBACK'])
        auth.request_token = token

        try:
            auth.get_access_token(verifier)
        except:
            return 'Some kind of error with Twitter, please try again later.'

        session['taccess'] = auth.access_token
        session['tsecret'] = auth.access_token_secret

        api = tweepy.API(auth)
        me = api.me()

        extra_data['me'] = me

    return render_template('add_site/%d.html' % (site_id), site=site, extra_data=extra_data, user=g.user)


@app.route('/add/<int:site_id>', methods=['POST'])
@login_required
def add_account_post(site_id):
    starttime = current_time()

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

        s.get('https://www.furaffinity.net/login/?mode=imagecaptcha',
              cookies={'b': session['fa_cookie_b']}, headers=headers)

        r = s.post('https://www.furaffinity.net/login/', cookies={'b': session['fa_cookie_b']}, data={
            'action': 'login',
            'name': request.form['username'],
            'pass': request.form['password'],
            'captcha': request.form['captcha'],
            'use_old_captcha': '1'
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
            j = json.loads(r.content.decode('utf-8'))
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
            j = json.loads(r.content.decode('utf-8'))
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
            j = json.loads(r.content.decode('utf-8'))
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

                j = json.loads(account_data.decode('utf-8'))

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
            r = requests.post('https://inkbunny.net/api_login.php', params={
                'username': request.form['username'],
                'password': request.form['password']
            }, headers=headers)

            j = json.loads(r.content.decode('utf-8'))

            if not 'sid' in j or j['sid'] == '':
                raise Exception('Invalid username or password.')
        except:
            flash('Invalid username or password.')
            return redirect(url_for('add_account_form', site_id=site.id))

        account = Account(site.id, session['id'], request.form['username'], json.dumps({
            'username': request.form['username'],
            'password': request.form['password']
        }), request.form['site_password'])

        db.session.add(account)
        db.session.commit()

    elif site.id == 5:
        s = requests.session()

        r = s.post('https://www.sofurry.com/user/login', data={
            'LoginForm[sfLoginUsername]': request.form['username'],
            'LoginForm[sfLoginPassword]': request.form['password']
        }, headers=headers)

        if r.url.endswith('/user/login'):
            flash('Invalid username or password.')
            return redirect(url_for('add_account_form', site_id=site.id))

        if not 'sfuser' in s.cookies:
            flash('Unable to find SoFurry login cookie.')
            return redirect(url_for('add_account_form', site_id=site.id))

        account = Account(site.id, session['id'], request.form['username'], json.dumps({
            'username': request.form['username'],
            'password': request.form['password']
        }), request.form['site_password'])

        db.session.add(account)
        db.session.commit()

    elif site.id == 6:
        auth = tweepy.OAuthHandler(
            app.config['TWITTER_KEY'], app.config['TWITTER_SECRET'])
        auth.set_access_token(session['taccess'], session['tsecret'])

        api = tweepy.API(auth)
        me = api.me()

        account = Account(site.id, session['id'], me.screen_name, json.dumps({
            'token': session.pop('taccess'),
            'secret': session.pop('tsecret'),
        }), request.form['site_password'])

        db.session.add(account)
        db.session.commit()

    time = current_time()
    duration = time - starttime
    influx.connection.write_points([{
        "measurement": "add_account_time",
        "fields": {
            "length": duration,
        },
        "tags": {
            "site": site.id,
        },
    }])

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

    return redirect(url_for('settings'))


@app.route('/settings')
@login_required
def settings():
    sofurry = []
    furaffinity = []

    for account in g.user.accounts:
        if account.site_id == 5:
            remap = account['remap_sofurry']

            sofurry.append({
                'id': account.id,
                'username': account.username,
                'enabled': remap and remap.val == 'yes'
            })
        elif account.site_id == 1:
            resolution = account['resolution_furaffinity']

            furaffinity.append({
                'id': account.id,
                'username': account.username,
                'enabled': not resolution or resolution.val == 'yes'
            })

    return render_template('settings.html', user=g.user, sofurry=sofurry, furaffinity=furaffinity)


@app.route('/settings/sofurry/remap', methods=['POST'])
@login_required
def settings_sofurry_remap():
    sofurry_accounts = [
        account for account in g.user.accounts if account.site_id == 5 and account.user_id == g.user.id]

    for account in sofurry_accounts:
        remap = account['remap_sofurry']

        if not remap:
            remap = AccountConfig(account.id, 'remap_sofurry', 'no')
            db.session.add(remap)

        if request.form.get('account[%d]' % (account.id)) == 'on':
            remap.val = 'yes'
        else:
            remap.val = 'no'

    db.session.commit()

    return redirect(url_for('settings'))


@app.route('/settings/furaffinity/resolution', methods=['POST'])
@login_required
def settings_furaffinity_resolution():
    furaffinity_accounts = [
        account for account in g.user.accounts if account.site_id == 1 and account.user_id == g.user.id]

    for account in furaffinity_accounts:
        resolution = account['resolution_furaffinity']

        if not resolution:
            resolution = AccountConfig(
                account.id, 'resolution_furaffinity', 'yes')
            db.session.add(resolution)

        if request.form.get('account[%d]' % (account.id)) == 'on':
            resolution.val = 'yes'
        else:
            resolution.val = 'no'

    db.session.commit()

    return redirect(url_for('settings'))


if __name__ == '__main__':
    db.create_all()
    app.run()
