from flask import Flask
from flask_cors import CORS

from auth import auth_bp
from camera import camera_bp
from recorded_video import recorded_video_bp

# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

CORS(app)


# ============================================================
# REGISTER BLUEPRINTS
# ============================================================

app.register_blueprint(auth_bp)

app.register_blueprint(camera_bp)

app.register_blueprint(recorded_video_bp)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return "Classroom Engagement AI Backend Running!"


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print("--------------------------------")
    print(
        "Classroom AI Backend"
    )
    print("--------------------------------")

    print(
        "Live Video:"
    )

    print(
        "http://127.0.0.1:5000/video_feed"
    )

    print(
        "Emotion Results:"
    )

    print(
        "http://127.0.0.1:5000/emotion-results"
    )

    print("--------------------------------")

    app.run(

        debug=True,

        use_reloader=False,

        host="0.0.0.0",

        port=5000

    )