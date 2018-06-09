from os.path import join
from typing import List

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from models import SavedSubmission, SubmissionGroup, db
from submission import Rating
from utils import login_required, random_string, safe_ext, save_multi_dict

app = Blueprint('list', __name__)


@app.route('/index', methods=['GET'])
@login_required
def index():
    groups: List[SubmissionGroup] = SubmissionGroup.get_groups()
    ungrouped: List[SavedSubmission] = SubmissionGroup.get_ungrouped_submissions()

    return render_template(
        'review/list.html', user=g.user, groups=groups, ungrouped=ungrouped
    )


@app.route('/remove', methods=['POST'])
@login_required
def remove():
    sub_id: str = request.form.get('id')

    if not sub_id:
        return redirect(url_for('list.index'))

    try:
        sub = SavedSubmission.find(int(sub_id))
    except ValueError:
        flash('Invalid submission ID.')
        return redirect(url_for('list.index'))

    if not sub:
        return redirect(url_for('list.index'))

    db.session.delete(sub)
    db.session.commit()

    flash('Removed submission.')
    return redirect(url_for('list.index'))


@app.route('/save', methods=['POST'])
@login_required
def save():
    sub_id: str = request.form.get('id')
    title: [None, str] = request.form.get('title')
    description: [None, str] = request.form.get('description')
    tags: [None, str] = request.form.get('keywords')
    rating: [None, str] = request.form.get('rating')
    if rating:
        rating = Rating(rating)
    accounts: List[str] = request.form.getlist('account')
    image: FileStorage = request.files.get('image')

    try:
        sub: SavedSubmission = SavedSubmission.find(int(sub_id))
    except ValueError:
        sub = None

    if not sub:
        sub = SavedSubmission(g.user, title, description, tags, rating)
        db.session.add(sub)

    sub.title = title
    sub.description = description
    sub.tags = tags
    sub.rating = rating
    sub.set_accounts(accounts)
    sub.data = save_multi_dict(request.form)

    ext = safe_ext(image.filename) if image else None
    if ext:
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

    posts: str = j.get('posts')
    group_id: str = j.get('group_id')
    group_name: str = j.get('group_name')

    if not posts:
        flash('No posts selected.')
        return redirect(url_for('list.index'))

    if group_id and group_id != 'new':
        try:
            group: SubmissionGroup = SubmissionGroup.find(int(group_id))
        except (TypeError, ValueError):
            flash('Invalid group ID.')
            return redirect(url_for('list.index'))
    elif group_name:
        group = SubmissionGroup(g.user, group_name)
        db.session.add(group)
        db.session.commit()
    else:
        flash('Missing group or group name')
        return redirect(url_for('list.index'))

    touched_groups = set()

    for post_id in posts:
        try:
            post: SavedSubmission = SavedSubmission.find(int(post_id))
        except ValueError:
            flash('Invalid post ID.')
            return redirect(url_for('list.index'))

        if not post:
            continue

        if post.group_id:
            touched_groups.add(post.group_id)

        post.group_id = group.id

    for group_id in touched_groups:
        try:
            group: SubmissionGroup = SubmissionGroup.find(int(group_id))
        except ValueError:
            flash('Invalid group ID.')
            return redirect(url_for('list.index'))

        if not group:
            continue

        if not group.submissions and not group.master:
            db.session.delete(group)

    db.session.commit()

    flash('Added posts to group!')
    return redirect(url_for('list.index'))


@app.route('/group/remove', methods=['POST'])
@login_required
def group_remove_post():
    group_id: str = request.form.get('group_id')
    if not group_id:
        return redirect(url_for('list.index'))

    try:
        group: SubmissionGroup = SubmissionGroup.find(int(group_id))
    except ValueError:
        flash('Bad group ID.')
        return redirect(url_for('list.index'))

    for sub in group.submissions:
        sub.group_id = None

    master = group.master
    if master:
        db.session.delete(master)
        db.session.commit()

    db.session.delete(group)
    db.session.commit()

    flash('Removed group and returned items to ungrouped.')
    return redirect(url_for('list.index'))


@app.route('/group/delete', methods=['POST'])
@login_required
def group_delete_post():
    group_id: str = request.form.get('group_id')
    if not group_id:
        return redirect(url_for('list.index'))

    try:
        group: SubmissionGroup = SubmissionGroup.find(int(group_id))
    except ValueError:
        flash('Bad group ID.')
        return redirect(url_for('list.index'))

    for sub in group.submissions:
        db.session.delete(sub)
    db.session.commit()

    if group.master:  # not returned from group.submissions
        db.session.delete(group.master)
        db.session.commit()

    db.session.delete(group)
    db.session.commit()

    flash('Removed group and deleted items.')
    return redirect(url_for('list.index'))
