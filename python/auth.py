import os
from datetime import timedelta
from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, jsonify, current_app

auth_bp = Blueprint('auth', __name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')

_sb = None


def _get_sb():
    global _sb
    if _sb is None and SUPABASE_URL and SUPABASE_ANON_KEY:
        from supabase import create_client
        _sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _sb


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # If Supabase is not configured, skip auth (local dev mode)
        if not SUPABASE_URL:
            return f(*args, **kwargs)
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login')
def login_page():
    if SUPABASE_URL and 'user_id' in session:
        return redirect('/dashboard')
    return render_template('login.html',
                           supabase_url=SUPABASE_URL,
                           supabase_anon_key=SUPABASE_ANON_KEY)


@auth_bp.route('/signup')
def signup_page():
    if SUPABASE_URL and 'user_id' in session:
        return redirect('/dashboard')
    return render_template('signup.html',
                           supabase_url=SUPABASE_URL,
                           supabase_anon_key=SUPABASE_ANON_KEY)


@auth_bp.route('/auth/callback')
def auth_callback():
    return render_template('auth_callback.html',
                           supabase_url=SUPABASE_URL,
                           supabase_anon_key=SUPABASE_ANON_KEY)


@auth_bp.route('/auth/session', methods=['POST'])
def set_session():
    body = request.get_json()
    if not body or 'access_token' not in body:
        return jsonify({'error': 'Missing token'}), 400

    sb = _get_sb()
    if not sb:
        return jsonify({'error': 'Auth not configured — set SUPABASE_URL and SUPABASE_ANON_KEY'}), 500

    try:
        resp = sb.auth.get_user(body['access_token'])
        user = resp.user
        if not user:
            return jsonify({'error': 'Invalid token'}), 401
        session.permanent = True
        session['user_id'] = user.id
        session['user_email'] = user.email
        return jsonify({'ok': True})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 401


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/login')
