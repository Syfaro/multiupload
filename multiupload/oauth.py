from authlib.integrations.flask_oauth2 import AuthorizationServer, ResourceProtector
from authlib.integrations.sqla_oauth2 import create_bearer_token_validator
from authlib.oauth2.rfc6749.grants import (
    AuthorizationCodeGrant as _AuthorizationCodeGrant
)
from authlib.oauth2.rfc6749.wrappers import OAuth2Request
from authlib.oidc.core.grants import OpenIDCode as _OpenIDCode
from authlib.oidc.core import UserInfo
from werkzeug.security import gen_salt
from multiupload.models import db, User, Client, AuthorizationCode, Token
from typing import Optional, List, Any
from flask import Flask


class _JWTConfig:
    _config: dict = {'alg': 'HS256', 'exp': 3600}

    def set_config(self, config: dict) -> None:
        self._config.update(config)

    @property
    def data(self) -> dict:
        return self._config


config = _JWTConfig()


def exists_nonce(nonce: str, request: OAuth2Request) -> bool:
    exists = AuthorizationCode.query.filter_by(
        client_id=request.client_id, nonce=nonce
    ).first()
    return bool(exists)


def generate_user_info(user: User, scope: List[str]) -> UserInfo:
    return UserInfo(sub=str(user.id), name=user.username, email=user.email)


def create_authorization_code(
    client: Client, grant_user: User, request: OAuth2Request
) -> AuthorizationCode:
    code = gen_salt(48)
    nonce = request.data.get('nonce')
    item = AuthorizationCode(
        code=code,
        client_id=client.client_id,
        redirect_uri=request.redirect_uri,
        scope=request.scope,
        user_id=grant_user.id,
        nonce=nonce,
    )
    db.session.add(item)
    db.session.commit()
    return code


class AuthorizationCodeGrant(_AuthorizationCodeGrant):
    def create_authorization_code(
        self, client: Client, grant_user: User, request: OAuth2Request
    ) -> AuthorizationCode:
        return create_authorization_code(client, grant_user, request)

    def parse_authorization_code(
        self, code: str, client: Client
    ) -> Optional[AuthorizationCode]:
        item = AuthorizationCode.query.filter_by(
            code=code, client_id=client.client_id
        ).first()
        if item and not item.is_expired():
            return item
        return None

    def delete_authorization_code(self, authorization_code: AuthorizationCode) -> None:
        db.session.delete(authorization_code)
        db.session.commit()

    def authenticate_user(self, authorization_code: AuthorizationCode) -> User:
        return User.query.get(authorization_code.user_id)


class OpenIDCode(_OpenIDCode):
    def exists_nonce(self, nonce: str, request: OAuth2Request) -> bool:
        return exists_nonce(nonce, request)

    def get_jwt_config(self, grant: Any) -> dict:
        return config.data

    def generate_user_info(self, user: User, scope: List[str]) -> UserInfo:
        return generate_user_info(user, scope)


def query_client(client_id: str) -> Optional[Client]:
    return Client.query.filter_by(client_id=client_id).first()


def save_token(token_data: dict, request: OAuth2Request) -> None:
    if request.user:
        user_id = request.user.get_user_id()
    else:
        user_id = None

    token = Token(client_id=request.client.client_id, user_id=user_id, **token_data)
    db.session.add(token)
    db.session.commit()


authorization = AuthorizationServer()
require_oauth = ResourceProtector()


def config_oauth(app: Flask) -> None:
    config.set_config({'key': app.config['JWT_KEY'], 'iss': app.config['JWT_ISS']})

    authorization.init_app(app, query_client=query_client, save_token=save_token)

    authorization.register_grant(
        AuthorizationCodeGrant, [OpenIDCode(require_nonce=False)]
    )

    bearer_cls = create_bearer_token_validator(db.session, Token)
    require_oauth.register_token_validator(bearer_cls())
