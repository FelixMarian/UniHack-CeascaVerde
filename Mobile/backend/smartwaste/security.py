import hashlib
import secrets
from datetime import timedelta, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from sqlalchemy import select, delete
from .models import User, Session, now

passwords = PasswordHash.recommended()
dummy_hash = passwords.hash(secrets.token_urlsafe(24))
bearer = HTTPBearer(auto_error=False)


def db(request: Request):
    with request.app.state.sw_sessions() as session:
        yield session


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), session=Depends(db)):
    invalid = HTTPException(401, 'Sesiune expirată. Autentifică-te din nou.', headers={'WWW-Authenticate': 'Bearer'})
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise invalid
    login_session = session.get(Session, digest(credentials.credentials))
    if not login_session:
        raise invalid
    expiry = login_session.expires_at.replace(tzinfo=timezone.utc) if login_session.expires_at.tzinfo is None else login_session.expires_at
    user = session.get(User, login_session.user_id)
    if expiry <= now() or not user or not user.active:
        raise invalid
    return user


def admin(user=Depends(current_user)):
    if user.role != 'Admin':
        raise HTTPException(403, 'Acces rezervat administratorului.')
    return user


def public_user(user):
    return {k: getattr(user, k) for k in ('id', 'username', 'role', 'display_name', 'active', 'demo', 'hq_latitude', 'hq_longitude')}


def revoke(session, user_id):
    session.execute(delete(Session).where(Session.user_id == user_id))


def issue(session, user, hours):
    token = secrets.token_urlsafe(48)
    expires = now() + timedelta(hours=hours)
    session.add(Session(token_hash=digest(token), user_id=user.id, expires_at=expires))
    session.commit()
    return {'access_token': token, 'token_type': 'bearer', 'expires_at': expires, 'user': public_user(user)}
