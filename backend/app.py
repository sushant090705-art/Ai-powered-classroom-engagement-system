from flask import Flask
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__)
CORS(app)

client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["classroom_engagement"]

print("MongoDB connected successfully!")

@app.route("/")
def home():
    return "Classroom Engagement AI Backend Running!"


if __name__ == "__main__":
    app.run(debug=True)