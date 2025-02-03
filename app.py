import dotenv
import logging
import json

dotenv.load_dotenv()

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
from middleware.api_key import require_api_key
from database import supabase
from handlers.articles import articles_module
from handlers.filings import filings_module
from handlers.subscription import subscription_module
from handlers.support import log_request_info

app = Flask(__name__)
app.register_blueprint(articles_module)
app.register_blueprint(filings_module)
app.register_blueprint(subscription_module)

app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
app.config["UPLOAD_FOLDER"] = "/tmp"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

@app.before_request
def log_request():
    log_request_info(logging.INFO, f"Received {request.method} request to {request.path}")
    

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        print(e.original_exception)
        response = e.get_response()
        response.data = json.dumps({
            "status":"error",
            "message": str(e.original_exception),
        })
        response.content_type = "application/json"

        return response

    return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/logs", methods=["GET"])
@require_api_key
def get_logs():
    response = supabase.table("idx_news_logs").select("*").order("timestamp", desc=True).execute()
    return jsonify(response.data)




if __name__ == "__main__":
    app.run(debug=False)
