from csv import DictReader
from io import StringIO
import json
import os
from os.path import join
import shutil
import time
from typing import Any, BinaryIO, Generator, List, Optional, Tuple, Type, cast
from zipfile import ZipFile

from chardet import UniversalDetector
import filetype
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    stream_with_context,
    url_for,
)
from requests import HTTPError
import simplecrypt
from werkzeug.utils import secure_filename

from multiupload.constant import Sites
from multiupload.models import (
    Account,
    SavedSubmission,
    SavedTemplate,
    SubmissionGroup,
    db,
)
from multiupload.sites import BadCredentials, SiteError
from multiupload.sites.known import KNOWN_SITES, known_list
from multiupload.submission import Rating, Submission
from multiupload.utils import (
    login_required,
    parse_resize,
    random_string,
    safe_ext,
    save_debug_pages,
    save_multi_dict,
    write_upload_time,
)

app = Blueprint('upload', __name__)


@app.route('/art', methods=['GET'])
@login_required
def create_art() -> Any:
    accounts = map(
        lambda account: {'account': account, 'selected': account.used_last},
        g.user.accounts,
    )

    items = sorted(accounts, key=lambda a: a['account'].site.name)

    templates = SavedTemplate.query.filter_by(user_id=g.user.id).all()

    return render_template(
        'review/review.html', accounts=items, sub=SavedSubmission(), templates=templates
    )


def submit_art(
    submission: Submission,
    account: Account,
    saved: Optional[SavedSubmission] = None,
    twitter_links: Optional[List[Tuple[Sites, str]]] = None,
) -> Optional[dict]:
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

            # If this was not empty, it should have been caught by now.
            assert submission.image_bytes is not None
            submission.image_bytes.seek(0)

            extra = {}

            if saved:
                try:
                    extra = saved.data
                except:
                    pass

            if twitter_links:
                extra['twitter-links'] = twitter_links

            link = s.submit_artwork(submission, extra=extra)

            write_upload_time(start_time, account.site.value)

            return {
                'link': link,
                'name': '{site} - {account}'.format(
                    site=site.SITE.name, account=account.username
                ),
            }

    return None


def upload_and_send(
    submission: Submission, accounts: List[Account], saved: SavedSubmission
) -> Generator[str, None, None]:
    twitter_account = saved.data.get('twitter-account')
    twitter_account_ids = []
    if twitter_account is not None:
        try:
            for i in twitter_account.split(' '):
                twitter_account_ids.append(int(i))
        except ValueError:
            pass

    twitter_links: List[Tuple[Sites, str]] = []
    upload_accounts: List[Account] = []
    upload_error = False

    yield 'event: count\ndata: {count}\n\n'.format(count=len(accounts))

    for account in accounts:
        try:
            result = submit_art(submission, account, saved, twitter_links)
            yield 'event: upload\ndata: {res}\n\n'.format(res=json.dumps(result))

            # Must be valid as we did not throw an Exception
            assert result is not None

            if account.id in twitter_account_ids:
                twitter_links.append((account.site, result['link']))

            upload_accounts.append(account)
        except BadCredentials:
            save_debug_pages()
            yield 'event: badcreds\ndata: {info}\n\n'.format(
                info=json.dumps(
                    {'site': account.site.name, 'account': account.username}
                )
            )
            upload_error = True
        except SiteError as ex:
            save_debug_pages()
            yield 'event: siteerror\ndata: {msg}\n\n'.format(
                msg=json.dumps(
                    {
                        'msg': ex.message,
                        'site': account.site.name,
                        'account': account.username,
                    }
                )
            )
            upload_error = True
        except HTTPError as ex:
            save_debug_pages()
            yield 'event: httperror\ndata: {info}\n\n'.format(
                info=json.dumps(
                    {
                        'site': account.site.name,
                        'account': account.username,
                        'code': ex.response.status_code,
                    }
                )
            )
            upload_error = True

    if upload_error:
        needs_upload = [
            account.id for account in accounts if account.id not in upload_accounts
        ]
        saved.set_accounts(needs_upload)  # remove accounts already uploaded to
    else:
        db.session.delete(saved)
        db.session.commit()

    yield 'event: done\ndata: completed\n\n'


@app.route('/art/saved', methods=['GET'])
@login_required
def create_art_post_saved() -> Any:
    saved_id = request.args['id']
    try:
        saved = SavedSubmission.find(int(saved_id))
    except ValueError:
        saved = None

    if not saved:
        flash('Unknown item.')
        return redirect(url_for('list.index'))

    submission = Submission(
        saved.title, saved.description, saved.tags, saved.rating.value, saved
    )

    for account in Account.all():
        account.used_last = 0

    accounts: List[Account] = []
    for saved_account in saved.accounts:
        if not saved_account or saved_account.user_id != g.user.id:
            flash('Account does not exist or does not belong to current user.')
            return redirect(url_for('upload.create_art'))

        saved_account.used_last = 1
        accounts.append(saved_account)
    db.session.commit()  # save currently used accounts

    accounts = sorted(accounts, key=lambda x: x.site_id)

    return Response(
        stream_with_context(upload_and_send(submission, accounts, saved)),
        mimetype='text/event-stream',
    )


@app.route('/art', methods=['POST'])
@login_required
def create_art_post() -> Any:
    total_time = time.time()

    title = request.form.get('title', '')
    description = request.form.get('description', '')
    keywords = request.form.get('keywords', '')
    rating = request.form.get('rating', '')
    resize = request.form.get('resize', '')
    upload = request.files.get('image', None)

    saved_id = request.form.get('id', '')

    if saved_id:
        saved: SavedSubmission = SavedSubmission.query.filter_by(
            user_id=g.user.id
        ).filter_by(id=saved_id).first()
        saved.title = title
        saved.description = description
        saved.tags = keywords
        if rating:
            saved.rating = Rating(rating)
    else:
        saved = SavedSubmission(g.user, title, description, keywords, None)
        if rating:
            saved.rating = Rating(rating)
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
        if all(
            v is None or v == '' for v in [title, description, keywords, rating, upload]
        ):
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

        return redirect(url_for('upload.review', sub_id=i))

    if upload:
        image_upload = upload
    else:
        image_upload = saved

    submission = Submission(title, description, keywords, rating, image_upload)

    for account in Account.all():
        account.used_last = 0

    accounts: List[Account] = []
    for account_id in request.form.getlist('account'):
        acct = Account.find(account_id)

        if not acct:
            flash('Account does not exist.')
            continue

        acct.used_last = 1
        accounts.append(acct)

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
            assert result is not None  # Would have thrown exception otherwise
            uploads.append(result)
            uploaded_accounts.append(account)

            if account.id in twitter_account_ids:
                twitter_links.append((account.site, result['link']))
        except BadCredentials:
            save_debug_pages()
            flash(
                'Unable to upload on {site} to account {account}, you may need to log in again.'.format(
                    site=account.site.name, account=account.username
                )
            )
            upload_error = True
        except SiteError as ex:
            save_debug_pages()
            flash(
                'Unable to upload on {site} to account {account}: {msg}'.format(
                    site=account.site.name, account=account.username, msg=ex.message
                )
            )
            upload_error = True
        except HTTPError:
            save_debug_pages()
            flash(
                'Unable to upload on {site} to account {account} due to a site issue.'.format(
                    site=account.site.name, account=account.username
                )
            )
            upload_error = True

    if upload_error:
        flash(
            'As an error occured, the submission has not been removed from the pending review list.'
        )

        needs_upload = [a.id for a in uploaded_accounts if a not in uploaded_accounts]
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


def parse_csv(
    f: BinaryIO, known_files: List[str] = None, base_files: Optional[str] = None
) -> int:
    detector = UniversalDetector()
    for line in f.readlines():
        detector.feed(line)
        if detector.done:
            break
    detector.close()
    f.seek(0)
    r = f.read().decode(detector.result.get('encoding', 'utf-8'))
    reader = DictReader(StringIO(r))

    foldername: Optional[str]
    if base_files:
        path = os.path.normpath(base_files)
        foldername = path.split(os.sep)[-1]
    else:
        foldername = None

    count = 0

    for row in reader:
        title = row.get('title')
        description = row.get('description')
        tags = row.get('tags')
        rating_str = row.get('rating', '')
        rating: Optional[Rating]
        if rating_str:
            rating = Rating(rating_str.lower())
        else:
            rating = None
        filename = row.get('file')
        accounts = row.get('accounts', '')

        if all(v is None for v in [title, description, tags, rating, filename]):
            continue

        sub = SavedSubmission(g.user, title, description, tags, rating)
        sub.data = row

        account_ids = []

        user_accounts: List[Account] = Account.query.filter_by(user_id=g.user.id).all()

        if accounts:
            for account in accounts.split():
                sitename, username = account.split('.', 1)

                for site in known_list():
                    if sitename.casefold() == site[1].casefold():
                        siteid = site[0]

                        i = None

                        for a in user_accounts:
                            folded = (
                                a.username.replace(' ', '_').casefold()
                                == username.replace(' ', '_').casefold()
                            )
                            if a.site_id == siteid and folded:
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
            assert filename is not None
            assert known_files is not None

            if filename in known_files:
                sub.original_filename = filename
                if foldername:
                    sub.image_filename = foldername + '/' + filename
                else:
                    sub.image_filename = filename
                sub.image_mimetype = filetype.guess_mime(
                    os.path.join(base_files, filename)
                )
            else:
                flash('Unknown image: {name}'.format(name=filename))

        db.session.add(sub)

    db.session.commit()

    return count


@app.route('/csv', methods=['GET'])
@login_required
def csv() -> Any:
    return redirect(url_for('upload.zip'))


@app.route('/csv', methods=['POST'])
@login_required
def csv_post() -> Any:
    file = request.files.get('file')
    if not file:
        flash('Missing CSV file.')
        return redirect(url_for('upload.zip'))

    parse_csv(file)

    return redirect(url_for('list.index'))


@app.route('/zip', methods=['GET'])
@login_required
def zip() -> Any:
    return render_template('review/zip.html')


@app.route('/zip', methods=['POST'])
@login_required
def zip_post() -> Any:
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
                flash(
                    'Rejecting {name} as it is larger than 10MB.'.format(
                        name=info.filename
                    )
                )
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
            count += parse_csv(cast(BinaryIO, f), image_files, folder)

    flash('Added {count} submissions.'.format(count=count))

    return redirect(url_for('list.index'))


@app.route('/review/<int:sub_id>', methods=['GET'])
@login_required
def review(sub_id: int) -> Any:
    sub = SavedSubmission.find(sub_id)

    if sub:
        return render_template(
            'review/review.html', sub=sub, accounts=sub.all_selected_accounts(g.user)
        )

    return redirect(url_for('list.index'))


@app.route('/imagepreview/<path:filename>')
def image(filename: str) -> Any:
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@app.app_template_filter('has_text')
def has_text(s: bool) -> str:
    return '✗' if not s else '✓'


@app.app_template_global('rating')
def global_rating() -> Type[Rating]:
    return Rating


@app.app_template_global('known_sites')
def global_known_sites() -> List[Tuple[int, str]]:
    return known_list()


@app.route('/group/create', methods=['GET'])
@login_required
def create_group() -> Any:
    items = map(
        lambda account: {'account': account, 'selected': account.used_last},
        g.user.accounts,
    )

    accounts = sorted(items, key=lambda a: a['account'].site.name)

    return render_template('review/group.html', accounts=accounts, is_group=True)


@app.route('/group/create', methods=['POST'])
@login_required
def create_group_post() -> Any:
    title = request.form['title']
    description = request.form.get('description')
    keywords = request.form.get('keywords')
    rating = request.form.get('rating')
    images = []
    titles = []
    for i in range(4):
        image_upload = request.files.get('image-' + str(i + 1))
        if not image_upload or image_upload.filename == '':
            continue
        images.append(image_upload)

        item = request.form.get('title-' + str(i + 1))
        if not item or item == '':
            continue
        titles.append(item)
    data = save_multi_dict(request.form)
    accounts = request.form.getlist('account')

    group = SubmissionGroup(g.user, title, grouped=True)
    db.session.add(group)
    db.session.commit()

    master = SavedSubmission(g.user, title, description, keywords, rating)
    master.master = True
    master.data = data
    master.set_accounts(accounts)
    master.group_id = group.id
    db.session.add(master)

    for idx, image_upload in enumerate(images):
        saved = SavedSubmission(g.user, titles[idx], description, keywords, rating)
        saved.data = data
        saved.set_accounts(accounts)
        saved.group_id = group.id

        ext = safe_ext(image_upload.filename)
        if ext:
            saved.original_filename = secure_filename(image_upload.filename)

            name = random_string(16) + '.' + ext

            image_upload.save(join(current_app.config['UPLOAD_FOLDER'], name))
            saved.image_filename = name
            saved.image_mimetype = image_upload.mimetype
        else:
            flash('{0} has a bad file extension'.format(image_upload.filename))
            continue

        db.session.add(saved)

    db.session.commit()

    return redirect(url_for('list.index'))


@app.route('/master/<int:id>', methods=['GET'])
@login_required
def update_master(id: int) -> Any:
    sub = SavedSubmission.find(id)

    if not sub:
        return abort(404)

    return render_template(
        'review/master.html', sub=sub, accounts=sub.all_selected_accounts(g.user)
    )


@app.route('/master', methods=['POST'])
@login_required
def update_master_post() -> Any:
    sub_id = request.form['id']
    title = request.form.get('title')
    description = request.form.get('description')
    keywords = request.form.get('keywords')
    rating = request.form.get('rating')

    sub = SavedSubmission.find(sub_id)
    if not sub:
        return abort(404)

    sub.title = title
    sub.description = description
    sub.tags = keywords
    sub.rating = Rating(rating)
    sub.data = save_multi_dict(request.form)

    assert sub.group is not None
    sub.group.name = title

    db.session.commit()

    flash('Updated master!')

    return redirect(url_for('list.index'))


def perform_group_upload(group_id: int) -> Generator[str, None, None]:
    group = SubmissionGroup.find(group_id)
    if not group:
        raise Exception()
    master = group.master

    had_error = False

    twitter_account = master.data.get('twitter-account')
    twitter_account_ids = []
    twitter_links: List[Tuple[Any, str]] = []
    if twitter_account is not None:
        try:
            for i in twitter_account.split(' '):
                twitter_account_ids.append(int(i))
        except ValueError:
            pass

    extra = master.data

    assert master.accounts is not None
    accounts: List[Account] = sorted(master.accounts, key=lambda x: x.site_id)

    yield 'event: count\ndata: {0}\n\n'.format(len(accounts))

    for account in accounts:
        decrypted = simplecrypt.decrypt(session['password'], account.credentials)

        extra['twitter-links'] = twitter_links

        for site in KNOWN_SITES:
            if site.SITE == account.site:
                s = site(decrypted, account)

                if s.supports_group():
                    errors = s.validate_submission(master)
                    if errors:
                        for error in errors:
                            yield 'event: validationerror\ndata: {0}\n\n'.format(error)
                            continue

                    try:
                        link = s.upload_group(group, extra)
                    except BadCredentials:
                        save_debug_pages()
                        yield 'event: badcreds\ndata: {0}\n\n'.format(
                            json.dumps(
                                {'site': account.site.name, 'account': account.username}
                            )
                        )
                        had_error = True
                        continue
                    except SiteError as ex:
                        save_debug_pages()
                        yield 'event: siteerror\ndata: {msg}\n\n'.format(
                            msg=json.dumps(
                                {
                                    'msg': ex.message,
                                    'site': account.site.name,
                                    'account': account.username,
                                }
                            )
                        )
                        had_error = True
                        continue
                    except HTTPError as ex:
                        save_debug_pages()
                        yield 'event: httperror\ndata: {info}\n\n'.format(
                            info=json.dumps(
                                {
                                    'site': account.site.name,
                                    'account': account.username,
                                    'code': ex.response.status_code,
                                }
                            )
                        )
                        had_error = True
                        continue

                    yield 'event: upload\ndata: {0}\n\n'.format(
                        json.dumps(
                            {
                                'link': link,
                                'name': '{site} - {account}'.format(
                                    site=site.SITE.name, account=account.username
                                ),
                            }
                        )
                    )

                    if account.id in twitter_account_ids:
                        twitter_links.append((account.site, link))
                else:
                    submissions = group.submissions
                    sub_count = len(submissions)

                    for idx, sub in enumerate(submissions):
                        errors = s.validate_submission(sub)
                        if errors:
                            for error in errors:
                                yield 'event: validationerror\ndata: {0}\n\n'.format(
                                    json.dumps(
                                        {
                                            'msg': error,
                                            'site': account.site.name,
                                            'account': account.username,
                                        }
                                    )
                                )
                                continue

                        try:
                            link = s.submit_artwork(sub.submission, extra)
                        except BadCredentials:
                            save_debug_pages()
                            yield 'event: badcreds\ndata: {0}\n\n'.format(
                                json.dumps(
                                    {
                                        'site': account.site.name,
                                        'account': account.username,
                                    }
                                )
                            )
                            had_error = True
                            continue
                        except SiteError as ex:
                            save_debug_pages()
                            yield 'event: siteerror\ndata: {msg}\n\n'.format(
                                msg=json.dumps(
                                    {
                                        'msg': ex.message,
                                        'site': account.site.name,
                                        'account': account.username,
                                    }
                                )
                            )
                            had_error = True
                            continue
                        except HTTPError as ex:
                            save_debug_pages()
                            yield 'event: httperror\ndata: {info}\n\n'.format(
                                info=json.dumps(
                                    {
                                        'site': account.site.name,
                                        'account': account.username,
                                        'code': ex.response.status_code,
                                    }
                                )
                            )
                            had_error = True
                            continue

                        yield 'event: upload\ndata: {0}\n\n'.format(
                            json.dumps(
                                {
                                    'link': link,
                                    'name': '{site} - {account}'.format(
                                        site=site.SITE.name, account=account.username
                                    ),
                                }
                            )
                        )

                        if account.id in twitter_account_ids:
                            if extra.get('twitter-image') == str(idx + 1):
                                twitter_links.append((account.site, link))

                        if 1 < sub_count != idx + 1:
                            yield 'event: delay\ndata: start\n\n'
                            time.sleep(20)
                            yield 'event: delay\ndata: end\n\n'

                yield 'event: groupdone\ndata: done\n\n'

    if not had_error:
        db.session.delete(master)
        for sub in group.submissions:
            db.session.delete(sub)
        db.session.commit()

        db.session.delete(group)
        db.session.commit()

    yield 'event: done\ndata: done\n\n'


@app.route('/group/post')
@login_required
def group_upload() -> Any:
    group_id = request.args['id']

    return Response(
        stream_with_context(perform_group_upload(group_id)),
        mimetype='text/event-stream',
    )
