from functools import wraps
from flask import request, jsonify
import os

API_KEY = os.getenv("API_KEY")

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "Authorization" not in request.headers:
            return jsonify({"status": "error", "message": "API key required"}), 403

        auth_header = request.headers.get("Authorization")
        if auth_header != f"Bearer {API_KEY}":
            return jsonify({"status": "error", "message": "Invalid API key"}), 403

        return f(*args, **kwargs)

    return decorated_function