import dotenv

dotenv.load_dotenv()

from flask import Flask, jsonify
from middleware.api_key import require_api_key
from database import supabase
from handlers.articles import articles_module
from handlers.fillings import fillings_module

import logging

app = Flask(__name__)
app.register_blueprint(articles_module)
app.register_blueprint(fillings_module)

app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
app.config["UPLOAD_FOLDER"] = "/tmp"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@app.route("/logs", methods=["GET"])
@require_api_key
def get_logs():
    try:
        response = supabase.table("idx_news_logs").select("*").execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"status": "error", "message": e}), 500


if __name__ == "__main__":
    app.run(debug=False)
