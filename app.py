from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import os
import logging
import json
# import dotenv
from functools import wraps
from scripts.metadata import extract_metadata

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
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:////tmp/data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

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

class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime)
    level = db.Column(db.String(50))
    message = db.Column(db.Text)
    request_method = db.Column(db.String(10))
    request_url = db.Column(db.String(255))
    remote_addr = db.Column(db.String(50))

with app.app_context():
    db.create_all()

def sanitize_and_insert(data):
    # Sanitization v1.0
    title = data.get('title').strip() if data.get('title') else None
    body = data.get('body').strip() if data.get('body') else None
    source = data.get('source').strip()
    timestamp_str = data.get('timestamp').strip()
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    subsector = data.get('subsector').strip()
    sector = sectors_data[subsector] if subsector in sectors_data.keys() else ""
    tags = data.get('tags', []) 
    tickers = data.get('tickers', [])
    
    if not title or not body:
        generated_title, generated_body = extract_metadata(source)
        if not title:
            title = generated_title
        if not body:
            body = generated_body

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

def log_request_info(level, message):
    log_entry = LogEntry(
        level=level,
        message=message,
        request_method=request.method,
        request_url=request.url,
        remote_addr=request.remote_addr,
        timestamp=datetime.now()
    )
    db.session.add(log_entry)
    db.session.commit()
    
    # logger.log(level, f"{message} - Method: {request.method}, URL: {request.url}, Remote Addr: {request.remote_addr}, Body: {request.data.decode('utf-8') if request.data else ''}")

@app.route('/articles', methods=['POST'])
@require_api_key
def add_article():
    log_request_info(logging.INFO, 'Received POST request to /articles')
    input_data = request.get_json()
    result = sanitize_and_insert(input_data)
    return jsonify(result)

@app.route('/articles/list', methods=['POST'])
@require_api_key
def add_articles():
    log_request_info(logging.INFO, 'Received POST request to /articles/list')
    input_data = request.get_json()
    result_list = []
    for data in input_data:
        result = sanitize_and_insert(data)
        result_list.append(result)
    return jsonify(result_list)

@app.route('/articles', methods=['GET'])
def get_articles():
    log_request_info(logging.INFO, 'Received GET request to /articles')
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
    log_request_info(logging.INFO, f'Received DELETE request to /articles/{id}')
    article = Article.query.get(id)
    if article is None:
        return jsonify({"status": "error", "message": "Article not found"}), 404
    db.session.delete(article)
    db.session.commit()
    return jsonify({"status": "success", "message": f"Article with id {id} deleted"})

@app.route('/articles/delete_n/<int:n>', methods=['DELETE'])
@require_api_key
def delete_first_n_articles(n):
    log_request_info(logging.INFO, f'Received DELETE request to /articles/delete_n/{n}')
    articles_to_delete = Article.query.order_by(Article.id).limit(n).all()
    if not articles_to_delete:
        return jsonify({"status": "error", "message": "No articles to delete"}), 404
    for article in articles_to_delete:
        db.session.delete(article)
    db.session.commit()
    return jsonify({"status": "success", "message": f"{n} articles deleted"})

@app.route('/logs', methods=['GET'])
@require_api_key
def get_logs():
    logs = LogEntry.query.order_by(LogEntry.timestamp.desc()).all()
    logs_list = [{
        'id': log.id,
        'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'level': log.level,
        'message': log.message,
        'request_method': log.request_method,
        'request_url': log.request_url,
        'remote_addr': log.remote_addr
    } for log in logs]
    return jsonify(logs_list)

if __name__ == '__main__':
    app.run(debug=False)
