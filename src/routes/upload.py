import json
import os
import shutil
import time
from csv import DictReader
from io import StringIO
from typing import List, Tuple
from zipfile import ZipFile

import magic
import simplecrypt
from chardet import UniversalDetector
from flask import Blueprint, Response, stream_with_context
from flask import current_app
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import send_from_directory
from flask import session
from flask import url_for
from os.path import join
from requests import HTTPError
from werkzeug.utils import secure_filename

from constant import Sites
from models import Account
from models import SavedSubmission
from models import db
from sites import BadCredentials, SiteError
from sites.known import KNOWN_SITES
from sites.known import known_list
from submission import Rating
from submission import Submission
from utils import get_active_notices
from utils import login_required
from utils import parse_resize
from utils import random_string
from utils import safe_ext
from utils import save_multi_dict
from utils import write_upload_time

app = Blueprint('upload', __name__)


@app.route('/art', methods=['GET'])
@login_required
def create_art():
    accounts = map(lambda account: {'account': account, 'selected': account.used_last}, g.user.accounts)

    return render_template('review/review.html', user=g.user, accounts=accounts, sites=known_list(),
                           notices=get_active_notices(for_user=g.user.id), sub=SavedSubmission(), rating=Rating)


def submit_art(submission, account, saved=None, twitter_links=None) -> dict:
    """Upload an art submission to an account.
    :param submission: the Submission object to upload
    :param account: the Account to upload to
    :param saved: if there is an associated SavedSubmission, that
    :param twitter_links: links to use for Twitter
    :return: dict containing a link and name to display
    """
    start_time = time.time()
    decrypted = simplecrypt.decrypt(session['password'], account.credentials)

    for site in KNOWN_SITES:
        if site.SITE == account.site:
            s = site(decrypted, account)

            errors = s.validate_submission(submission)
            if errors:
                for error in errors:
                    flash(error)
                    continue

            submission.image_bytes.seek(0)

            extra = {}

            if saved:
                extra = saved.data

            if twitter_links:
                extra['twitter-links'] = twitter_links

            link = s.submit_artwork(submission, extra=extra)

            write_upload_time(start_time, account.site.value)

            return {
                'link': link,
                'name': '{site} - {account}'.format(site=site.SITE.name, account=account.username)
            }


def upload_and_send(submission, accounts, password, saved, twitter_account_ids):
    twitter_links: List[Tuple[Sites, str]] = []
    upload_accounts: List[Account] = []
    upload_error = False

    yield 'event: count\ndata: {count}\n\n'.format(count=len(accounts))

    for account in accounts:
        try:
            result = submit_art(submission, account, password, saved, twitter_links)
            yield 'event: upload\ndata: {res}\n\n'.format(res=json.dumps(result))

            if account.id in twitter_account_ids:
                twitter_links.append((account.site, result['link'],))
        except BadCredentials:
            yield 'event: badcreds\ndata: {info}\n\n'.format(
                info=json.dumps({'site': account.site.value, 'account': account.username}))
            upload_error = True
        except SiteError as ex:
            yield 'event: siteerror\ndata: {msg}\n\n'.format(msg=json.dumps({
                'msg': ex.message,
                'site': account.site.value,
                'account': account.username,
            }))
            upload_error = True
        except HTTPError as ex:
            yield 'event: httperror\ndata: {info}\n\n'.format(info=json.dumps({
                'site': account.site.value,
                'account': account.username,
                'code': ex.response.status_code,
            }))
            upload_error = True

    if upload_error:
        needs_upload = [account for account in accounts if account not in upload_accounts]
        saved.set_accounts(needs_upload)  # remove accounts already uploaded to
    else:
        db.session.delete(saved)
        db.session.commit()

    yield 'event: done\ndata: completed\n\n'


@app.route('/art/saved', methods=['GET'])
@login_required
def create_art_post_saved():
    saved_id = request.args.get('id')
    saved: SavedSubmission = SavedSubmission.query.filter_by(user_id=g.user.id).filter_by(id=saved_id).first()

    if not saved:
        flash('Unknown item.')
        return redirect(url_for('list.index'))

    submission = Submission(saved.title, saved.description, saved.tags, saved.rating.value, saved)

    for account in Account.query.filter_by(user_id=g.user.id).all():
        account.used_last = 0

    accounts: List[Account] = []
    for account in saved.accounts:
        if not account or account.user_id != g.user.id:
            print('bad account')
            flash('Account does not exist or does not belong to current user.')
            return redirect(url_for('upload.create_art'))

        account.used_last = 1
        accounts.append(account)
    db.session.commit()  # save currently used accounts

    accounts: List[Account] = sorted(accounts, key=lambda x: x.site_id)

    twitter_account = saved.data.get('twitter-account')
    twitter_account_ids = []
    if twitter_account is not None:
        try:
            for i in twitter_account.split(' '):
                twitter_account_ids.append(int(i))
        except ValueError:
            pass

    return Response(
        stream_with_context(upload_and_send(submission, accounts, session['password'], saved, twitter_account_ids)),
        mimetype='text/event-stream')


@app.route('/art', methods=['POST'])
@login_required
def create_art_post():
    total_time = time.time()

    title = request.form.get('title')
    description = request.form.get('description')
    keywords = request.form.get('keywords')
    rating = request.form.get('rating')
    resize = request.form.get('resize')
    upload = request.files.get('image', None)

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

    saved.data = save_multi_dict(request.form)
    saved.set_accounts(request.form.getlist('account'))

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

    if not upload and (not saved_id or saved.image_filename == ''):
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
            return redirect(url_for('upload.create_art'))

        if upload:
            ext = safe_ext(upload.filename)
            if ext:
                saved.original_filename = secure_filename(upload.filename)

                name = random_string(16) + '.' + ext

                upload.save(join(current_app.config['UPLOAD_FOLDER'], name))
                saved.image_filename = name
                saved.image_mimetype = upload.mimetype

        db.session.commit()
        i = saved.id

        return redirect(url_for('upload.review', id=i))

    if upload:
        image_upload = upload
    else:
        image_upload = saved

    submission = Submission(title, description, keywords, rating, image_upload)

    for account in Account.query.filter_by(user_id=g.user.id).all():
        account.used_last = 0

    accounts: List[Account] = []
    for acct in request.form.getlist('account'):
        account = Account.query.get(acct)

        if not account or account.user_id != g.user.id:
            flash('Account does not exist or does not belong to current user.')
            return redirect(url_for('upload.create_art'))

        account.used_last = 1

        accounts.append(account)

    db.session.commit()

    if resize:
        dimensions = parse_resize(resize)
        if dimensions:
            height, width = dimensions

            submission.resize_image(height, width, replace=True)

    accounts = sorted(accounts, key=lambda x: x.site_id)

    twitter_account = request.form.get('twitter-account')
    twitter_account_ids = []
    if twitter_account is not None:
        try:
            for i in twitter_account.split(' '):
                twitter_account_ids.append(int(i))
        except ValueError:
            pass

    upload_error = False

    uploads: List[dict] = []
    uploaded_accounts: List[Account] = []
    twitter_links: List[Tuple[Sites, str]] = []
    for account in accounts:
        try:
            result = submit_art(submission, account, saved, twitter_links)
            uploads.append(result)
            uploaded_accounts.append(account)

            if account.id in twitter_account_ids:
                twitter_links.append((account.site, result['link'],))
        except BadCredentials:
            flash('Unable to upload on {site} to account {account}, you may need to log in again.'.format(
                site=account.site.name, account=account.username))
            upload_error = True
        except SiteError as ex:
            flash('Unable to upload on {site} to account {account}: {msg}'.format(site=account.site.name,
                                                                                  account=account.username,
                                                                                  msg=ex.message))
            upload_error = True
        except HTTPError:
            flash('Unable to upload on {site} to account {account} due to a site issue.'.format(site=account.site.name,
                                                                                                account=account.username))
            upload_error = True

    if upload_error:
        flash('As an error occured, the submission has not been removed from the pending review list.')

        needs_upload = [a for a in uploaded_accounts if a not in uploaded_accounts]
        saved.set_accounts(needs_upload)  # remove accounts already uploaded to

        if upload:
            ext = safe_ext(upload.filename)
            if ext:
                saved.original_filename = secure_filename(upload.filename)

                name = random_string(16) + '.' + ext

                upload.seek(0)
                upload.save(join(current_app.config['UPLOAD_FOLDER'], name))
                saved.image_filename = name
                saved.image_mimetype = upload.mimetype

    else:
        db.session.delete(saved)

    db.session.commit()

    write_upload_time(total_time, measurement='upload_time_total')

    return render_template('after_upload.html', uploads=uploads, user=g.user)


def parse_csv(f, known_files=None, base_files=None):
    detector = UniversalDetector()
    for line in f.readlines():
        detector.feed(line)
        if detector.done:
            break
    detector.close()
    f.seek(0)
    r = f.read().decode(detector.result.get('encoding', 'utf-8'))
    reader = DictReader(StringIO(r))

    mime = magic.Magic(mime=True)

    if base_files:
        foldername = base_files.split('/')[-1]

    count = 0

    for row in reader:
        title = row.get('title')
        description = row.get('description')
        tags = row.get('tags')
        rating = row.get('rating')
        if rating:
            rating = Rating(rating.lower())
        filename = row.get('file')
        accounts = row.get('accounts')

        if all(v is None for v in [title, description, tags, rating, filename]):
            continue

        sub = SavedSubmission(g.user, title, description, tags, rating)
        sub.data = row

        account_ids = []

        user_accounts: List[Account] = Account.query.filter_by(user_id=g.user.id).all()

        if accounts:
            accounts = accounts.split()
            for account in accounts:
                sitename, username = account.split('.', 1)

                for site in known_list():
                    if sitename.casefold() == site[1].casefold():
                        siteid = site[0]

                        i = None

                        for a in user_accounts:
                            if a.site_id == siteid and a.username.replace(' ', '_').casefold() == username.replace(' ',
                                                                                                                   '_').casefold():
                                i = a.id
                                break

                        if not i:
                            flash('Unknown account: {account}'.format(account=account))
                            break

                        account_ids.append(str(i))

                        break

            sub.set_accounts(account_ids)

        count += 1

        if base_files:
            if filename in known_files:
                sub.original_filename = filename
                sub.image_filename = foldername + '/' + filename
                sub.image_mimetype = mime.from_file(os.path.join(base_files, filename))
            else:
                flash('Unknown image: {name}'.format(name=filename))

        db.session.add(sub)

    db.session.commit()

    return count


@app.route('/csv', methods=['GET'])
@login_required
def csv():
    return redirect(url_for('upload.zip'))


@app.route('/csv', methods=['POST'])
@login_required
def csv_post():
    file = request.files.get('file')
    if not file:
        flash('Missing CSV file.')
        return redirect(url_for('upload.zip'))

    parse_csv(file)

    return redirect(url_for('list.index'))


@app.route('/zip', methods=['GET'])
@login_required
def zip():
    return render_template('review/zip.html')


@app.route('/zip', methods=['POST'])
@login_required
def zip_post():
    file = request.files.get('file')
    if not file:
        flash('Missing ZIP file.')
        return redirect(url_for('upload.zip'))

    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], random_string(16))
    if not os.path.exists(folder):
        os.mkdir(folder)

    csv_files = []
    image_files = []

    with ZipFile(file) as z:
        for info in z.infolist():
            if info.file_size > 1000 * 1000 * 10:  # 10MB
                flash('Rejecting {name} as it is larger than 10MB.'.format(name=info.filename))
                continue

            if info.filename.startswith('__MACOSX/'):
                continue

            _, ext = os.path.splitext(info.filename)
            ext = ext.lower()

            z.extract(info.filename, folder)

            if ext in ('.png', '.jpg', '.jpeg', '.gif'):
                image_files.append(info.filename)
            elif ext in ('.csv', '.xls', 'xlsx'):
                csv_files.append(info.filename)
            else:
                flash('Unknown file: {name}'.format(name=info.filename))

    no_valid = all(not f for f in [csv_files, image_files])

    if no_valid:
        flash('No valid files found in ZIP!')
        shutil.rmtree(folder)

        return redirect(url_for('list.index'))

    count = 0

    for c in csv_files:
        with open(os.path.join(folder, c), 'rb') as f:
            count += parse_csv(f, image_files, folder)

    flash('Added {count} submissions.'.format(count=count))

    return redirect(url_for('list.index'))


@app.route('/review/<int:id>', methods=['GET'])
@login_required
def review(id=None):
    q = SavedSubmission.query.filter_by(user_id=g.user.id)
    if id:
        q = q.filter_by(id=id)
    sub: SavedSubmission = q.first()

    if sub:
        return render_template('review/review.html', sub=sub, rating=Rating, user=g.user,
                               accounts=sub.all_selected_accounts(g.user), sites=known_list())

    return redirect(url_for('list.index'))


@app.route('/imagepreview/<path:filename>')
def image(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@app.app_template_filter('has_text')
def has_text(s):
    return '✗' if not s else '✓'
