from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone
import os
import logging
import json
import dotenv
from supabase import create_client, Client
from functools import wraps
from scripts.metadata import extract_metadata
from scripts.pdf_reader import extract_from_pdf
from scripts.generate_article import generate_article
import pytz

gmt_plus_7 = pytz.timezone('Asia/Bangkok')

dotenv.load_dotenv()

API_KEY = os.getenv("API_KEY")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB
app.config['UPLOAD_FOLDER'] = '/tmp'
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

with open('./data/sectors_data.json', 'r') as f:
    sectors_data = json.load(f)

def sanitize_and_insert(data):
    # Sanitization v1.0
    title = data.get('title').strip() if data.get('title') else None
    body = data.get('body').strip() if data.get('body') else None
    source = data.get('source').strip()
    timestamp_str = data.get('timestamp').strip()
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    sub_sector = data.get('sub_sector').strip() if data.get('sub_sector') else data.get('subsector').strip()
    sector = sectors_data[sub_sector] if sub_sector in sectors_data.keys() else ""
    tags = data.get('tags', []) 
    tickers = data.get('tickers', [])
    
    if not title or not body:
        generated_title, generated_body = extract_metadata(source)
        if not title:
            title = generated_title
        if not body:
            body = generated_body
    
    if title == '' or body == '':
        generated_title, generated_body = extract_metadata(source)
        if title == '':
            title = generated_title
        if body == '':
            body = generated_body

    new_article = {
        'title': title,
        'body': body,
        'source': source,
        'timestamp': timestamp.isoformat(),
        'sector': sector,
        'sub_sector': sub_sector,
        'tags': tags,
        'tickers': tickers
    }

    try:
        response = supabase.table('idx_news').insert(new_article).execute()
        return {"status": "success", "id": response.data[0]['id']}
    except Exception as e:
        return {"status": "error", "message": f"Insert failed! Exception: {e}"}


def log_request_info(level, message):
    log_entry = {
        'timestamp': datetime.now(gmt_plus_7).isoformat(),
        'level': level,
        'message': message,
        'request_method': request.method,
        'request_url': request.url,
        'remote_addr': request.remote_addr
    }
    try:
        supabase.table('idx_news_logs').insert(log_entry).execute()
    except Exception as e:
        print("Failed to insert log")
    
    delete_outdated_logs()
    
def delete_outdated_logs():
    logs = supabase.table('idx_news_logs').select('*').execute() 
    if len(logs.data) > 100:
        one_week_ago = datetime.now(gmt_plus_7) - timedelta(weeks=1)
        print(datetime.now(gmt_plus_7), one_week_ago)
        to_be_deleted = []
        for log in logs.data:
            log_timestamp = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00')).astimezone(gmt_plus_7)
            if log_timestamp < one_week_ago:
                to_be_deleted.append(log['id'])
        
        if to_be_deleted:
            try:
                for log_id in to_be_deleted:
                    response = supabase.table('idx_news_logs').delete().eq('id', log_id).execute()
                    print(f"Deleted log ID: {log_id}, {response}")
            except Exception as e:
                print(f"Failed to delete logs: {e}")


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
    try:
        response = supabase.table('idx_news').select('*').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"status": "error", "message": {e.message}}), 500

@app.route('/articles', methods=['DELETE'])
@require_api_key
def delete_article():
    input_data = request.get_json()
    id_list = input_data.get('id_list')
    log_request_info(logging.INFO, f'Received DELETE request to /articles')
    list_result = []
    for id in id_list:
        try:
            supabase.table('idx_news').delete().eq('id', id).execute()
            list_result.append({"status": "success", "message": f"Article with id {id} deleted"})
        except Exception as e:
            list_result.append({"status": "error", "message": f"Error deleting article with id {id}: {e}"})
    return jsonify(list_result)     

@app.route('/logs', methods=['GET'])
@require_api_key
def get_logs():
    try:
        response = supabase.table('idx_news_logs').select('*').order('timestamp', desc=True).execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"status": "error", "message": e}), 500
    
@app.route('/pdf', methods=['POST'])
@require_api_key
def add_pdf_article():
    log_request_info(logging.INFO, f'Received POST request to /pdf')
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    
    file = request.files['file']

    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    
    source = request.form.get('source', '')
    sub_sector = request.form.get('sub_sector', '')
    
    if file and file.filename.lower().endswith('.pdf'):
        file_path = save_file(file)
        text = extract_from_pdf(file_path)
        text = generate_article(source, sub_sector, text)
        os.remove(file_path)
        
        try:
            response = supabase.table('idx_news').insert(text).execute()
        except Exception as e:
            return {"status": "error", "message": f"Insert failed! Exception: {e}"}

        return jsonify({"status": "success", "filename": file.filename, "response": response.data[0], "source": source, "sub_sector": sub_sector}), 200
    else:
        return jsonify({"status": "error", "message": "Invalid file type"}), 400

def save_file(file):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    return file_path

if __name__ == '__main__':
    app.run(debug=False)
