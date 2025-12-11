"""
SBNC Photo Gallery System - Authentication
Handle admin login/logout.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from datetime import datetime

from app.database import get_db
from app.main import AdminUser

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        with get_db() as conn:
            user = conn.execute(
                'SELECT * FROM admin_users WHERE email = ? AND is_active = TRUE',
                (email,)
            ).fetchone()

            if user and check_password_hash(user['password_hash'], password):
                # Update last login
                conn.execute(
                    'UPDATE admin_users SET last_login = ? WHERE id = ?',
                    (datetime.utcnow(), user['id'])
                )

                admin_user = AdminUser(dict(user))
                login_user(admin_user)

                next_page = request.args.get('next')
                return redirect(next_page or url_for('admin.dashboard'))

            flash('Invalid email or password', 'error')

    return render_template('admin/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))
