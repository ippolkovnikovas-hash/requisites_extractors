import os
from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'uploads')
    app.config['EXPORT_FOLDER'] = os.path.join(base_dir, 'exports')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)
    from .routes import web_bp
    app.register_blueprint(web_bp)
    return app
