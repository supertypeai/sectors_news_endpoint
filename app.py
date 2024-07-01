from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import os
import logging
import json
# import dotenv
from functools import wraps

# dotenv.load_dotenv()

API_KEY = os.getenv("API_KEY")

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'Authorization' not in request.headers:
            return jsonify({"status": "error", "message": "API key required"}), 403
        
        auth_header = request.headers.get('Authorization')
        if auth_header != f"Bearer {API_KEY}":
            return jsonify({"status": "error", "message": "Invalid API key"}), 403

        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

with open('./data/sectors_data.json', 'r') as f:
    sectors_data = json.load(f)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    sector = db.Column(db.String(100), nullable=False)
    subsector = db.Column(db.String(100), nullable=False)
    tags = db.Column(db.JSON, nullable=False)  # Array of String
    tickers = db.Column(db.JSON, nullable=False)

with app.app_context():
    db.create_all()

def sanitize_and_insert(data):
    # Sanitization v1.0
    title = data.get('title').strip()
    body = data.get('body').strip()
    source = data.get('source').strip()
    timestamp_str = data.get('timestamp').strip()
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    subsector = data.get('subsector').strip()
    sector = sectors_data[subsector] if subsector in sectors_data.keys() else ""
    tags = data.get('tags', []) 
    tickers = data.get('tickers', [])

    new_article = Article(
        title=title,
        body=body,
        source=source,
        timestamp=timestamp,
        sector=sector,
        subsector=subsector,
        tags=tags,
        tickers=tickers
    )

    try:
        db.session.add(new_article)
        db.session.commit()
        return {"status": "success", "id": new_article.id}
    except IntegrityError:
        db.session.rollback()
        return {"status": "error", "message": "Integrity error, possibly duplicate data"}

@app.route('/articles', methods=['POST'])
@require_api_key
def add_article():
    input_data = request.get_json()
    result = sanitize_and_insert(input_data)
    return jsonify(result)

@app.route('/articles', methods=['GET'])
def get_articles():
    articles = Article.query.all()
    articles_list = [{
        'id': article.id,
        'title': article.title,
        'body': article.body,
        'source': article.source,
        'timestamp': article.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'sector': article.sector,
        'subsector': article.subsector,
        'tags': article.tags,  
        'tickers': article.tickers
    } for article in articles]
    return jsonify(articles_list)

@app.route('/articles/<int:id>', methods=['DELETE'])
@require_api_key
def delete_article(id):
    article = Article.query.get(id)
    if article is None:
        return jsonify({"status": "error", "message": "Article not found"}), 404
    db.session.delete(article)
    db.session.commit()
    return jsonify({"status": "success", "message": f"Article with id {id} deleted"})

@app.route('/articles/delete_n/<int:n>', methods=['DELETE'])
@require_api_key
def delete_first_n_articles(n):
    articles_to_delete = Article.query.order_by(Article.id).limit(n).all()
    if not articles_to_delete:
        return jsonify({"status": "error", "message": "No articles to delete"}), 404
    for article in articles_to_delete:
        db.session.delete(article)
    db.session.commit()
    return jsonify({"status": "success", "message": f"{n} articles deleted"})

if __name__ == '__main__':
    app.run(debug=False)
