from typing import Any

from authlib.integrations.flask_oauth2 import current_token
from flask import Blueprint, g, jsonify

from multiupload.csrf import csrf
from multiupload.oauth import authorization, require_oauth
from multiupload.utils import login_required


app = Blueprint('oauth', __name__)


@app.route('/authorize', methods=['GET', 'POST'])
@login_required
def authorize() -> Any:
    return authorization.create_authorization_response(grant_user=g.user)


@app.route('/token', methods=['POST'])
@csrf.exempt
def issue_token() -> Any:
    return authorization.create_token_response()


@app.route('/userinfo')
@require_oauth('profile')
def userinfo() -> Any:
    user = current_token.user

    return jsonify({'id': user.id, 'name': user.username, 'email': user.email})
