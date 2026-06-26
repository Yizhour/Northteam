from flask import Flask

from .config import SCHEDULER_ENABLED, ensure_directories
from .routes import bp
from .scheduler import scheduler_service


def create_app():
    ensure_directories()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024
    app.register_blueprint(bp)
    if SCHEDULER_ENABLED:
        scheduler_service.start()
    return app
