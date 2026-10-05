"""Flask application entry point.

Routes and business logic live in dedicated modules. This file only creates
the Flask app, registers blueprints, and starts the development server.
"""

from flask import Flask


def create_app():
    app = Flask(__name__)

    from flask_cors import CORS
    CORS(app)

    from auth import auth_bp
    from camera import camera_bp
    from recorded_video import recorded_video_bp
   

    app.register_blueprint(auth_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(recorded_video_bp)
  

    @app.route("/")
    def home():
        return "Classroom Engagement AI Backend Running!"

    return app


app = create_app()


if __name__ == "__main__":
    print("--------------------------------")
    print("Classroom AI Backend")
    print("--------------------------------")
    print("Live Video: http://127.0.0.1:5000/video_feed")
    print("Emotion Results: http://127.0.0.1:5000/emotion-results")
    print("--------------------------------")

    app.run(
        debug=True,
        use_reloader=False,
        host="0.0.0.0",
        port=5000,
    )