"""
Shared authentication utilities.

Provides a canonical require_auth decorator and token decoding logic
used across all routes.
"""
import jwt
from functools import wraps
from flask import request, jsonify

from config import JWT_SECRET


def decode_token():
    """
    Decode JWT from Authorization header.
    
    Returns:
        tuple: (payload, error_tuple) where error_tuple is None on success,
               or (message, status_code) on failure.
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        return None, ("No token provided", 401)
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, ("Session expired", 401)
    except jwt.InvalidTokenError:
        return None, ("Invalid token", 401)


def require_auth(f):
    """
    Decorator to require valid JWT authentication.
    
    - Bypasses authentication for OPTIONS requests (CORS preflight)
    - Decodes JWT from Authorization header
    - Sets request.current_user to the decoded payload
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "OPTIONS":
            return jsonify({}), 200
        payload, err = decode_token()
        if err:
            return jsonify({"status": "error", "message": err[0]}), err[1]
        request.current_user = payload
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """
    Decorator to require admin role.
    
    Admin status is determined by email in ADMIN_EMAILS config.
    Falls back to require_auth behavior if email check is skipped.
    """
    from config import ADMIN_EMAILS
    
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "OPTIONS":
            return jsonify({}), 200
        payload, err = decode_token()
        if err:
            return jsonify({"status": "error", "message": err[0]}), err[1]
        if payload.get("email", "").lower() not in ADMIN_EMAILS:
            return jsonify({"status": "error", "message": "Admin access required"}), 403
        request.current_user = payload
        return f(*args, **kwargs)
    return decorated
