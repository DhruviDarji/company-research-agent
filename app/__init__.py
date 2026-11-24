"""Flask application factory."""
from flask import Flask
from flask_cors import CORS

from .config import Config


def create_app(config_class=Config):
    app = Flask(__name__)  # uses app/templates and app/static by default
    app.config.from_object(config_class)
    CORS(app, origins=app.config["CORS_ORIGINS"])

    from .routes.api import api
    from .routes.pages import pages
    app.register_blueprint(pages)
    app.register_blueprint(api, url_prefix="/api")
    return app
