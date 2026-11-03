"""Flask application entry point.

Routes and business logic live in dedicated modules. This file only creates
the Flask app, registers blueprints, and starts the development server.
"""

import logging
from flask import Flask

from logging_config import setup_logging

logger = logging.getLogger(__name__)


def create_app():
    # Must run before the blueprint imports below: they load the AI models
    # at import time and log while doing so.
    setup_logging()

    app = Flask(__name__)

    from flask_cors import CORS
    CORS(app)

    from auth import auth_bp
    from camera import camera_bp
    from recorded_video import recorded_video_bp
    from analytics import analytics_bp
    from reports import reports_bp
    from alerts import alerts_bp  
   

    app.register_blueprint(auth_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(recorded_video_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(alerts_bp)

    @app.route("/")
    def home():
        return "Classroom Engagement AI Backend Running!"

    return app


app = create_app()


if __name__ == "__main__":
    logger.info("Classroom AI Backend starting")
    logger.info("Live Video: http://127.0.0.1:5000/video_feed")
    logger.info("Emotion Results: http://127.0.0.1:5000/emotion-results")

    app.run(
        debug=True,
        use_reloader=False,
        host="0.0.0.0",
        port=5000,
    )