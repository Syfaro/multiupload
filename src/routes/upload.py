from typing import List

import csv
import time
import simplecrypt

from os.path import join
from io import StringIO

from flask import Blueprint
from flask import current_app
from flask import flash
from flask import g
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import send_from_directory
from flask import url_for

from werkzeug.utils import secure_filename

from requests import HTTPError

from constant import Sites

from description import parse_description

from models import Account
from models import SavedSubmission
from models import Site
from models import db

from sentry import sentry

from sites import AccountExists
from sites import BadCredentials
from sites import SiteError

from sites.known import KNOWN_SITES
from sites.known import known_list

from submission import Submission
from submission import Rating

from utils import get_active_notices
from utils import login_required
from utils import send_to_influx
from utils import random_string

app = Blueprint('upload', __name__)


def safe_ext(name: str):
    if '.' not in name:
        return False

    split = name.rsplit('.', 1)[1].lower()\

    if split not in current_app.config['ALLOWED_EXTENSIONS']:
        return False

    return split


@app.route('/beta', methods=['GET'])
@app.route('/beta/<path:p>', methods=['GET'])
@login_required
def beta_upload(p=None):
    return render_template('app.html', user=g.user)


@app.route('/upload', methods=['GET'])
@login_required
def upload_form():
    return render_template('upload.html', user=g.user, sites=known_list(),
                           notices=get_active_notices(for_user=g.user.id))


@app.route('/preview/description')
@login_required
def preview_description():
    accounts = request.args.getlist('account')
    description = request.args.get('description', '')

    descriptions = []
    sites_done = []

    for site in accounts:
        account = Account.query.filter_by(user_id=session['id']).filter_by(id=int(site)).first()

        if account.site.value in sites_done or account.site == Sites.Twitter:
            continue

        descriptions.append({
            'site': account.site.name,
            'description': parse_description(description, account.site.value),
        })

        sites_done.append(account.site.value)

    return jsonify({
        'descriptions': descriptions,
    })


def write_upload_time(start_time, site=None, measurement='upload_time'):
    duration = time.time() - start_time

    point = {
        'measurement': measurement,
        'fields': {
            'duration': duration,
        },
    }

    if site:
        point['tags'] = {'site': site}

    send_to_influx(point)


@app.route('/upload', methods=['POST'])
@login_required
def upload_post():
    total_time = time.time()

    title = request.form.get('title', None)
    description = request.form.get('description', None)
    keywords = request.form.get('keywords', None)
    rating = request.form.get('rating', None)

    saved_id = request.form.get('id')

    if saved_id:
        saved: SavedSubmission = SavedSubmission.query.filter_by(user_id=g.user.id).filter_by(id=saved_id).first()
        saved.title = title
        saved.description = description
        saved.tags = keywords
        if rating:
            saved.rating = Rating(rating)
    else:
        saved = SavedSubmission(g.user, title, description, keywords, rating)
        db.session.add(saved)

    saved.set_accounts(request.form.getlist('account'))

    upload = request.files.get('image', None)

    has_error = False

    if not title:
        flash('Missing title.')
        has_error = True

    if not description:
        flash('Missing description.')
        has_error = True

    if not keywords:
        flash('Missing keywords.')
        has_error = True

    if not upload and not saved_id:
        flash('Missing image.')
        has_error = True

    if not request.form.getlist('account'):
        flash('No site selected.')
        has_error = True

    if not rating:
        flash('No content rating selected.')
        has_error = True

    if has_error:
        if all(v is None or v == '' for v in [title, description, keywords, rating, upload]):
            return redirect(url_for('upload.upload_form'))

        if upload:
            ext = safe_ext(upload.filename)
            if upload and ext:
                saved.original_filename = secure_filename(upload.filename)

                name = random_string(16) + '.' + ext

                upload.save(join(current_app.config['UPLOAD_FOLDER'], name))
                saved.image_filename = name
                saved.image_mimetype = upload.mimetype

        db.session.commit()
        i = saved.id

        return redirect(url_for('upload.upload_review', review=i))

    submission = Submission(title, description, keywords, rating, saved if saved_id else upload)

    basic_error = False

    for account in Account.query.filter_by(user_id=g.user.id).all():
        account.used_last = 0

    accounts: List[Account] = []
    for acct in request.form.getlist('account'):
        account = Account.query.get(acct)

        if not account or account.user_id != g.user.id:
            flash('Account does not exist or does not belong to current user.')
            return redirect(url_for('upload.upload_form'))

        account.used_last = 1

        accounts.append(account)

    db.session.commit()

    if basic_error:
        return redirect(url_for('upload.upload_form'))

    accounts = sorted(accounts, key=lambda x: x.site_id)

    twitter_link_id = request.form.get('twitterlink', None)
    if twitter_link_id is not None:
        try:
            twitter_link_id = int(twitter_link_id)
        except ValueError:
            twitter_link_id = None
    twitter_link = None

    upload_error = False

    uploads: List[dict] = []
    for account in accounts:
        start_time = time.time()

        decrypted = simplecrypt.decrypt(session['password'], account.credentials)

        link = None

        for site in KNOWN_SITES:
            if site.SITE == account.site:
                s = site(decrypted, account)

                errors = s.validate_submission(submission)
                if errors:
                    for error in errors:
                        flash(error)
                        continue

                try:
                    link = s.submit_artwork(submission, extra={
                        'twitter_link': twitter_link,
                        'deviantart_category': request.form.get('deviantart-category'),
                    })

                except BadCredentials:
                    flash('Unable to upload on {site} to account {account}, you may need to log in again.'.format(
                        site=account.site.name, account=account.username))
                    upload_error = True
                    continue

                except SiteError as ex:
                    flash('Unable to upload on {site} to account {account}: {msg}'.format(
                        site=account.site.name, account=account.username, msg=ex.message
                    ))
                    upload_error = True
                    continue

                except HTTPError:
                    flash('Unable to upload on {site} to account {account} due to a site issue.'.format(
                        site=account.site.name, account=account.username
                    ))
                    upload_error = True
                    continue

                uploads.append({
                    'link': link,
                    'name': '{site} - {account}'.format(site=site.SITE.name, account=account.username)
                })

        if account.id == twitter_link_id:
            twitter_link = link

        write_upload_time(start_time, account.site.value)

    if upload_error:
        flash('As an error occured, the submission has not been removed from the pending review list.')
    else:
        db.session.delete(saved)

    db.session.commit()

    write_upload_time(total_time, measurement='upload_time_total')

    return render_template('after_upload.html', uploads=uploads, user=g.user)


@app.route('/upload/csv', methods=['GET'])
@login_required
def upload_csv():
    return render_template('review/upload.html')


@app.route('/upload/csv', methods=['POST'])
@login_required
def upload_from_csv():
    file = request.files.get('csv')
    if not file:
        raise Exception('Missing CSV file.')

    reader = csv.DictReader(StringIO(file.read().decode('utf-8')))

    for row in reader:
        title = row.get('title')
        description = row.get('description')
        tags = row.get('tags')
        rating = row.get('rating')
        if rating:
            rating = Rating(rating)

        if all(v is None for v in [title, description, tags, rating]):
            continue

        sub = SavedSubmission(g.user, title, description, tags, rating)

        db.session.add(sub)

    db.session.commit()

    return redirect(url_for('upload.upload_list'))


@app.route('/upload/review', methods=['GET'])
@login_required
def upload_list():
    submissions = SavedSubmission.query.filter_by(user_id=g.user.id).filter_by(submitted=False).all()

    return render_template('review/list.html', user=g.user, submissions=submissions)


@app.route('/upload/remove', methods=['POST'])
@login_required
def upload_remove():
    sub_id = request.form.get('id')

    if not sub_id:
        return redirect(url_for('upload.upload_list'))

    sub = SavedSubmission.query.filter_by(user_id=g.user.id).filter_by(id=sub_id).first()

    if not sub:
        return redirect(url_for('upload.upload_list'))

    db.session.delete(sub)
    db.session.commit()

    return redirect(url_for('upload.upload_list'))


@app.route('/upload/save', methods=['POST'])
@login_required
def upload_save():
    title = request.form.get('title')
    description = request.form.get('description')
    tags = request.form.get('keywords')
    rating = request.form.get('rating')
    if rating:
        rating = Rating(rating)
    accounts = request.form.getlist('account')

    sub: SavedSubmission = SavedSubmission.query.filter_by(
        user_id=g.user.id).filter_by(id=request.form.get('id')).first()

    if not sub:
        sub = SavedSubmission(g.user, title, description, tags, rating)
        db.session.add(sub)

    sub.title = title
    sub.description = description
    sub.tags = tags
    sub.rating = rating
    sub.set_accounts(accounts)

    image = request.files.get('image')
    ext = safe_ext(image.filename)
    if image and ext:
        sub.original_filename = secure_filename(image.filename)

        name = random_string(16) + '.' + ext

        image.save(join(current_app.config['UPLOAD_FOLDER'], name))
        sub.image_filename = name
        sub.image_mimetype = image.mimetype

    db.session.commit()

    return redirect(url_for('upload.upload_list'))


@app.route('/upload/review/<int:review>', methods=['GET'])
@login_required
def upload_review(review=None):
    q = SavedSubmission.query.filter_by(user_id=g.user.id).filter_by(submitted=False)
    if review:
        q = q.filter_by(id=review)
    sub: SavedSubmission = q.first()

    remaining = SavedSubmission.query.filter_by(user_id=g.user.id).filter_by(submitted=False).count()

    if sub:
        return render_template('review/review.html', sub=sub, rating=Rating, user=g.user, remaining=remaining,
                               accounts=sub.all_selected_accounts(g.user), sites=known_list())

    return 'Nothing in review queue.'


@app.route('/upload/review/<int:review>', methods=['POST'])
@login_required
def submit_review(review):
    sub = SavedSubmission.query.get(review)
    if sub is None:
        return 'Invalid item.'
    if sub.user_id != g.user.id:
        return 'Not yours to review.'

    print(sub.title)


@app.route('/accounts')
@login_required
def manage_accounts():
    return render_template('accounts.html', sites=known_list(), user=g.user)


@app.route('/add')
@login_required
def add():
    return render_template('add_site.html', sites=known_list(), user=g.user)


@app.route('/add/<int:site_id>', methods=['GET'])
@login_required
def add_account_form(site_id):
    try:
        site = Sites(site_id)
    except ValueError:
        return 'Unknown site ID!'

    extra_data = {}

    for known_site in KNOWN_SITES:
        if known_site.SITE == site:
            s = known_site()

            try:
                pre = s.pre_add_account()
            except SiteError as ex:
                sentry.captureException()
                return 'There was an error with the site: {msg}'.format(msg=ex.message)

            if pre is not None:
                if isinstance(pre, dict):
                    extra_data = pre
                else:
                    return pre

    return render_template('add_site/%d.html' % site_id, site=site, extra_data=extra_data, user=g.user)


@app.route('/add/<int:site_id>/callback', methods=['GET'])
@login_required
def add_account_callback(site_id):
    site = Sites(site_id)

    if not site:
        return 'Unknown site ID!'

    extra_data = {}

    for known_site in KNOWN_SITES:
        if known_site.SITE == site:
            s = known_site()

            try:
                callback = s.add_account_callback()
            except SiteError as ex:
                sentry.captureException()
                return 'There was an error with the site: {msg}'.format(msg=ex.message)

            if callback is not None:
                if isinstance(callback, dict):
                    extra_data = callback
                elif isinstance(callback, str):
                    return callback
                else:
                    return callback

    return render_template('add_site/%d.html' % site_id, site=site, extra_data=extra_data, user=g.user)


@app.route('/add/<int:site_id>', methods=['POST'])
@login_required
def add_account_post(site_id):
    start_time = time.time()

    try:
        site = Sites(site_id)
    except ValueError:
        flash('Unknown site ID.')
        return redirect(url_for('upload.add_account_form'))

    try:
        for known_site in KNOWN_SITES:
            if known_site.SITE == site:
                s = known_site()
                data = s.parse_add_form(request.form)
                s.add_account(data)

    except BadCredentials:
        flash('Unable to authenticate')
        return redirect(url_for('upload.add_account_form', site_id=site.value))

    except AccountExists:
        flash('Account already exists.')
        return redirect(url_for('upload.manage_accounts'))

    send_to_influx({
        'measurement': 'account_time_add',
        'fields': {
            'duration': time.time() - start_time,
        },
        'tags': {
            'site': site.value,
        },
    })

    return redirect(url_for('upload.manage_accounts'))


@app.route('/remove/<int:account_id>')
@login_required
def remove_form(account_id):
    account = Account.query.get(account_id)

    if not account:
        flash('Account does not exist.')
        return redirect(url_for('upload.upload_form'))

    if account.user_id != g.user.id:
        flash('Account does not belong to you.')
        return redirect(url_for('upload.manage_accounts'))

    return render_template('remove.html', account=account, user=g.user)


@app.route('/remove', methods=['POST'])
@login_required
def remove():
    account_id = request.form.get('id')
    if not account_id:
        flash('Missing account ID.')
        return redirect(url_for('upload.manage_accounts'))

    account = Account.query.get(account_id)

    if not account:
        flash('Account does not exist.')
        return redirect(url_for('upload.manage_accounts'))

    if account.user_id != g.user.id:
        flash('Account does not belong to you.')
        return redirect(url_for('upload.manage_accounts'))

    db.session.delete(account)
    db.session.commit()

    flash('Account removed.')
    return redirect(url_for('upload.manage_accounts'))


@app.route('/upload/imagepreview/<filename>')
def view_upload(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@app.app_template_filter('has_text')
def has_text(s):
    return '✗' if not s else '✓'
