import hashlib, hmac, os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Header, HTTPException

SECRET = os.getenv('SMARTBORDER_SECRET', 'replace-this-secret-for-production')
ALGO = 'HS256'

def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 180000).hex()
    return f'{salt.hex()}:{digest}'

def verify_password(password: str, encoded: str) -> bool:
    salt_hex, digest = encoded.split(':', 1)
    got = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), 180000).hex()
    return hmac.compare_digest(got, digest)

def issue_token(officer_id: str, name: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {'sub': officer_id, 'name': name, 'role': role, 'iat': now, 'exp': now + timedelta(hours=8)}
    return jwt.encode(payload, SECRET, algorithm=ALGO)

def current_user(authorization: str = Header(default='')):
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Authentication required')
    try:
        return jwt.decode(authorization.split(' ', 1)[1], SECRET, algorithms=[ALGO])
    except Exception:
        raise HTTPException(401, 'Session expired or invalid')
