from flask import Blueprint, request, jsonify
from database import users


# Create authentication Blueprint
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():

    data = request.json

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "message": "Email and password are required"
        }), 400

    # Check if user already exists
    existing_user = users.find_one({
        "email": email
    })

    if existing_user:
        return jsonify({
            "success": False,
            "message": "User already exists"
        }), 409

    # Create new user
    users.insert_one({
        "email": email,
        "password": password
    })

    return jsonify({
        "success": True,
        "message": "Registration successful"
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():

    data = request.json

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "message": "Email and password are required"
        }), 400

    # Find user
    user = users.find_one({
        "email": email,
        "password": password
    })

    if not user:
        return jsonify({
            "message": "Invalid email or password"
        }), 401

    return jsonify({
    "success": True,
    "message": "Login successful"
    }), 200