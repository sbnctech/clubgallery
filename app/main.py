"""
SBNC Photo Gallery System - Flask Application Factory
"""

from flask import Flask, redirect, url_for
from flask_login import LoginManager
from werkzeug.security import generate_password_hash, check_password_hash

from app.config import SECRET_KEY, DEBUG
from app.database import get_db, init_db


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__,
                template_folder='admin/templates',
                static_folder='admin/static')

    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['DEBUG'] = DEBUG

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        with get_db() as conn:
            user = conn.execute(
                'SELECT * FROM admin_users WHERE id = ?',
                (user_id,)
            ).fetchone()
            if user:
                return AdminUser(dict(user))
        return None

    # Register blueprints
    from app.admin.routes import admin_bp
    from app.gallery.routes import gallery_bp
    from app.admin.auth import auth_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(gallery_bp)
    app.register_blueprint(auth_bp)

    @app.route('/')
    def index():
        return redirect(url_for('gallery.gallery_page'))

    return app


class AdminUser:
    """User class for Flask-Login."""

    def __init__(self, user_data):
        self.id = user_data['id']
        self.email = user_data['email']
        self.is_active = user_data.get('is_active', True)
        self.is_super_admin = user_data.get('is_super_admin', False)
        self.member_id = user_data.get('member_id')

    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


def create_admin_user(email, password, is_super_admin=False):
    """Create a new admin user."""
    password_hash = generate_password_hash(password)

    with get_db() as conn:
        conn.execute('''
            INSERT INTO admin_users (email, password_hash, is_super_admin)
            VALUES (?, ?, ?)
        ''', (email, password_hash, is_super_admin))

    print(f"Created admin user: {email}")


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
