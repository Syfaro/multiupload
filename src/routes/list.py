from os.path import join

from flask import Blueprint
from flask import current_app
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from werkzeug.utils import secure_filename

from models import SavedSubmission
from models import SubmissionGroup
from models import db
from submission import Rating
from utils import login_required
from utils import random_string
from utils import safe_ext
from utils import save_multi_dict

app = Blueprint('list', __name__)


@app.route('/index', methods=['GET'])
@login_required
def index():
    groups = SubmissionGroup.get_groups()
    ungrouped = SubmissionGroup.get_ungrouped_submissions()

    return render_template('review/list.html', user=g.user, groups=groups, ungrouped=ungrouped)


@app.route('/remove', methods=['POST'])
@login_required
def remove():
    sub_id = request.form.get('id')

    if not sub_id:
        return redirect(url_for('list.index'))

    sub = SavedSubmission.query.filter_by(user_id=g.user.id).filter_by(id=sub_id).first()

    if not sub:
        return redirect(url_for('list.index'))

    db.session.delete(sub)
    db.session.commit()

    flash('Removed submission.')

    return redirect(url_for('list.index'))


@app.route('/save', methods=['POST'])
@login_required
def save():
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
    sub.data = save_multi_dict(request.form)

    image = request.files.get('image')
    ext = safe_ext(image.filename) if image else None
    if image and ext:
        sub.original_filename = secure_filename(image.filename)

        name = random_string(16) + '.' + ext

        image.save(join(current_app.config['UPLOAD_FOLDER'], name))
        sub.image_filename = name
        sub.image_mimetype = image.mimetype

    db.session.commit()

    flash('Submission saved.')

    return redirect(url_for('list.index'))


@app.route('/group/add', methods=['POST'])
@login_required
def group_add_post():
    j = request.get_json()

    posts = j.get('posts')
    group_id = j.get('group_id')
    group_name = j.get('group_name')

    if not posts:
        flash('No posts selected.')
        return redirect(url_for('list.index'))

    if not group_id and group_name:
        group = SubmissionGroup(g.user, group_name)
        db.session.add(group)
        db.session.commit()
    else:
        group = SubmissionGroup.query.filter_by(user_id=g.user.id).filter_by(id=group_id).first()

    touched_groups = set()

    for post_id in posts:
        post: SavedSubmission = SavedSubmission.query.filter_by(user_id=g.user.id).filter_by(id=post_id).first()
        if not post:
            continue
        if post.group_id:
            touched_groups.add(post.group_id)
        post.group_id = group.id

    for group in touched_groups:
        group: SubmissionGroup = SubmissionGroup.query.filter_by(user_id=g.user.id).filter_by(id=group).first()
        if not group:
            continue
        if not group.submissions:
            db.session.delete(group)

    db.session.commit()
    flash('Added posts to groups!')

    return redirect(url_for('list.index'))


@app.route('/group/remove', methods=['POST'])
@login_required
def group_remove_post():
    group_id = request.form.get('group_id')
    if not group_id:
        return redirect(url_for('list.index'))

    group: SubmissionGroup = SubmissionGroup.query.filter_by(user_id=g.user.id).filter_by(id=group_id).first()

    for sub in group.submissions:
        sub.group_id = None

    db.session.delete(group)
    db.session.commit()

    flash('Removed group and returned items to ungrouped.')
    return redirect(url_for('list.index'))


@app.route('/group/delete', methods=['POST'])
@login_required
def group_delete_post():
    group_id = request.form.get('group_id')
    if not group_id:
        return redirect(url_for('list.index'))

    group: SubmissionGroup = SubmissionGroup.query.filter_by(user_id=g.user.id).filter_by(id=group_id).first()

    for sub in group.submissions:
        db.session.delete(sub)
    db.session.commit()

    db.session.delete(group)
    db.session.commit()

    flash('Removed group and deleted items.')
    return redirect(url_for('list.index'))


@app.route('/group/time', methods=['POST'])
@login_required
def group_time_post():
    pass