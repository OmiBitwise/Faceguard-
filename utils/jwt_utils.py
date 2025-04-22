# utils/jwt_utils.py
import jwt
from datetime import datetime, timedelta
from flask import current_app
from functools import wraps
from flask import request, redirect, url_for, flash


def generate_jwt(user_id, username, email, expires_in=3600):
    payload = {
        'user_id': str(user_id),
        'username': username,
        'email': email,
        'exp': datetime.utcnow() + timedelta(seconds=expires_in)
    }
    token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    return token

def decode_jwt(token):
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    

def jwt_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        token = request.cookies.get('jwt_token')
        if not token:
            flash('Login required!', 'error')
            return redirect(url_for('login.handle_login'))
        
        payload = decode_jwt(token)
        if not payload:
            flash('Invalid or expired token. Please log in again.', 'error')
            return redirect(url_for('login.handle_login'))

        # Optionally: attach user info to request context
        request.user = payload
        return view_func(*args, **kwargs)
    return wrapper
def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt_token')
        if not token:
            return redirect(url_for('login.handle_login'))
        
        user_data = decode_jwt(token)
        if not user_data:
            return redirect(url_for('login.handle_login'))

        # You can optionally attach user info to `request` if needed
        request.user = user_data
        return f(*args, **kwargs)
    return decorated_function
