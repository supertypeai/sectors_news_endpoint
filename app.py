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
from scripts.summary_filings import summarize_filing
from scripts.summary_news import summarize_news

dotenv.load_dotenv()

API_KEY = os.getenv("API_KEY")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), SUPABASE_KEY)

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

def sanitize_insert(data):
    new_article = sanitize_article(data)

    try:
        response = supabase.table('idx_news').insert(new_article).execute()
        return {"status": "success", "id": response.data[0]['id'], "status_code": 200}
    except Exception as e:
        return {"status": "error", "message": f"Insert failed! Exception: {e}", "status_code": 500}

def sanitize_update(data):
    new_article = sanitize_article(data)
    record_id = data.get('id')

    if not record_id:
        return jsonify({"error": "Record ID is required", "status_code": 400})
    
    try:
        response = supabase.table('idx_news').update(new_article).eq('id', record_id).execute()
        
        return {"message": "Record updated successfully from table idx_news", "data": response.data, "status_code": 200}
    except Exception as e:
        return {"error": str(e), "status_code": 500}

def sanitize_article(data):
    # Sanitization v1.0
    title = data.get('title').strip() if data.get('title') else None
    body = data.get('body').strip() if data.get('body') else None
    source = data.get('source').strip()
    timestamp_str = data.get('timestamp').strip()
    timestamp_str = timestamp_str.replace('T', ' ')
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    sub_sector = data.get('sub_sector').strip() if data.get('sub_sector') else data.get('subsector').strip()
    sector = sectors_data[sub_sector] if sub_sector in sectors_data.keys() else ""
    tags = data.get('tags', []) 
    tickers = data.get('tickers', [])

    for i, ticker in enumerate(tickers):
        split = ticker.split(".")
        if len(split) > 1:
            if split[1].upper() == "JK":
                pass
            else:
                split[1] = ".JK"
                tickers[i] = split[0] + split[1]
        else:
            tickers[i] += ".JK"
        tickers[i] = tickers[i].upper()
    
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

    new_title, new_body = summarize_news(new_article['source'])

    if len(new_body) > 0:
        new_article['body'] = new_body
    
    if len(new_title) > 0:
        new_article['title'] = new_title
    
    return new_article

def sanitize_filing(data):
    document_number = data.get('document_number').strip() if data.get('nomor_surat') else None
    company_name = data.get('company_name').strip()
    shareholder_name = data.get('shareholder_name').strip()
    source = data.get('source').strip()
    ticker = data.get('ticker').strip()
    category = data.get('category').strip()
    control_status = data.get('control_status').strip()
    holding_before = data.get('holding_before')
    holding_after = data.get('holding_after')
    sub_sector = data.get('sub_sector').strip() if data.get('sub_sector') else data.get('subsector').strip()
    purpose = data.get('purpose').strip()
    date_time = datetime.strptime(data.get('date_time'), '%Y-%m-%d %H:%M:%S')
    holder_type = data.get('holder_type')
    transaction_type = ('buy' if holding_before < holding_after else 'sell')
    amount_transaction = abs(holding_before - holding_after)

    ticker_list = ticker.split(".")
    if (len(ticker_list) > 1):
        if (ticker_list[1].upper() == "JK"):
            pass
        else:
            ticker_list[1] = ".JK"
            ticker = ticker_list[0] + ticker_list[1]
    else:
        ticker += ".JK"
    ticker = ticker.upper()

    new_article = {
        'title': f"Informasi insider trading {shareholder_name} dalam {company_name}",
        'body': f"{document_number} - {date_time} - Kategori {category} - {shareholder_name} dengan status kontrol {control_status} dalam saham {company_name} berubah dari {holding_before} menjadi {holding_after}",
        'source': source,
        'timestamp': str(date_time),
        'sector': sectors_data[sub_sector] if sub_sector in sectors_data.keys() else "",
        'sub_sector': sub_sector,
        'tags': ['insider-trading'],
        'tickers': [ticker],
        "transaction_type": transaction_type,
        "holder_type": holder_type,
        "holding_before": holding_before,
        "holding_after": holding_after,
        "amount_transaction": amount_transaction,
        "holder_name": shareholder_name
    }
    new_title, new_body = summarize_filing(new_article)

    if len(new_body) > 0:
        new_article['body'] = new_body
    
    if len(new_title) > 0:
        new_article['title'] = new_title

    return new_article

def sanitize_filing_article(data):
    title = data.get('title').strip() if data.get('title') else None
    body = data.get('body').strip() if data.get('body') else None
    source = data.get('source').strip()
    timestamp_str = data.get('timestamp').strip()
    timestamp_str = timestamp_str.replace('T', ' ')
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    sub_sector = data.get('sub_sector').strip() if data.get('sub_sector') else data.get('subsector').strip()
    sector = sectors_data[sub_sector] if sub_sector in sectors_data.keys() else ""
    tags = data.get('tags', []) 
    tickers = data.get('tickers', [])
    holding_before = data.get('holding_before')
    holding_after = data.get('holding_after')
    holder_type = data.get('holder_type')
    transaction_type = ('buy' if holding_before < holding_after else 'sell')
    amount_transaction = abs(holding_before - holding_after)
    holder_name = data.get('holder_name')

    new_article = {
        'title': title,
        'body': body,
        'source': source,
        'timestamp': timestamp.isoformat(),
        'sector': sector,
        'sub_sector': sub_sector,
        'tags': tags,
        'tickers': tickers,
        "transaction_type": transaction_type,
        "holder_type": holder_type,
        "holding_before": holding_before,
        "holding_after": holding_after,
        "amount_transaction": amount_transaction,
        "holder_name": holder_name,
    }

    new_title, new_body = summarize_filing(new_article)

    if len(new_body) > 0:
        new_article['body'] = new_body
    
    if len(new_title) > 0:
        new_article['title'] = new_title

    return new_article

def insert_insider_trading_supabase(data):
    new_article = sanitize_filing(data)
    
    try:
        response = supabase.table('idx_filings').insert(new_article).execute()
        return {"status": "success", "id": response.data[0]['id'], "status_code": 200}
    except Exception as e:
        return {"status": "error", "message": f"Insert failed! Exception: {e}", "status_code": 500}
    
def update_insider_trading_supabase(data):
    new_article = sanitize_filing_article(data)
    record_id = data.get('id')

    if not record_id:
        return jsonify({"error": "Record ID is required", "status_code": 400})
    try:
        response = supabase.table('idx_filings').update(new_article).eq('id', record_id).execute()
        
        return {"message": "Record updated successfully from table ifx_filings", "data": response.data, "status_code": 200}
    except Exception as e:
        return {"error": str(e), "status_code": 500}

def log_request_info(level, message):
    log_entry = {
        'timestamp': datetime.now().isoformat(),
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
        one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)
        print(datetime.now(), one_week_ago)
        to_be_deleted = []
        for log in logs.data:
            log_timestamp = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00')).astimezone(timezone.utc)
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
    result = sanitize_insert(input_data)
    return jsonify(result), result.get('status_code')

@app.route('/articles/list', methods=['POST'])
@require_api_key
def add_articles():
    log_request_info(logging.INFO, 'Received POST request to /articles/list')
    input_data = request.get_json()
    result_list = []
    for data in input_data:
        result = sanitize_insert(data)
        result_list.append(result)
    return jsonify(result_list)

@app.route('/articles', methods=['GET'])
def get_articles():
    log_request_info(logging.INFO, 'Received GET request to /articles')

    subsector = request.args.get('subsector')
    if not subsector:
        request.args.get('sub_sector')        
    try:
        query = supabase.table('idx_news').select('*')
        if subsector:
            query = query.eq('sub_sector', subsector)
        
        response = query.execute()
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

@app.route('/articles', methods=['PATCH'])
@require_api_key
def update_article():
    log_request_info(logging.INFO, 'Received PATCH request to /articles')
    input_data = request.get_json()
    result = sanitize_update(input_data)
    return jsonify(result), result.get('status_code')

@app.route('/logs', methods=['GET'])
@require_api_key
def get_logs():
    try:
        response = supabase.table('idx_news_logs').select('*').execute()
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
    
    source = request.form['source'] if 'source' in request.form else ''
    sub_sector = request.form['sub_sector'] if 'sub_sector' in request.form else request.form['subsector'] if 'subsector' in request.form else ''
    # Either Insider or Institution
    type = request.form['holder_type'] if 'holder_type' in request.form else ''
    type = type if type.lower() == 'insider' or type.lower() == 'insitution' else ''
    
    if file and file.filename.lower().endswith('.pdf'):
        file_path = save_file(file)
        text = extract_from_pdf(file_path)
        text = generate_article(source, sub_sector, type, text)
        os.remove(file_path)
        
        try:
            response = supabase.table('idx_filings').insert(text).execute()
        except Exception as e:
            return {"status": "error", "message": f"Insert failed! Exception: {e}"}

        return jsonify({"status": "success", "filename": file.filename, "response": response.data[0], "source": source, "sub_sector": sub_sector}), 200
    else:
        return jsonify({"status": "error", "message": "Invalid file type"}), 400

@app.route('/insider-trading', methods=['POST'])
@require_api_key
def add_insider_trading():
    log_request_info(logging.INFO, f'Received POST request to /insider-trading')
    input_data = request.get_json()
    result = insert_insider_trading_supabase(input_data)
    return jsonify(result), result.get('status_code')

@app.route('/insider-trading', methods=['GET'])
@require_api_key
def get_insider_trading():
    log_request_info(logging.INFO, f'Received GET request to /insider-trading')
    try:
        response = supabase.table('idx_filings').select('*').execute()
        return response.data
    except Exception as e:
        return jsonify({"status": "error", "message": e}), 500
    
@app.route('/insider-trading', methods=['DELETE'])
@require_api_key
def delete_insider_trading():
    log_request_info(logging.INFO, f'Received DELETE request to /insider-trading')
    input_data = request.get_json()
    id_list = input_data.get('id_list')
    list_result = []
    for id in id_list:
        try:
            supabase.table('idx_filings').delete().eq('id', id).execute()
            list_result.append({"status": "success", "message": f"Filing with id {id} deleted"})
        except Exception as e:
            list_result.append({"status": "error", "message": f"Error deleting filing with id {id}: {e}"})
    return jsonify(list_result)

@app.route('/insider-trading', methods=['PATCH'])
@require_api_key
def update_insider_trading():
    log_request_info(logging.INFO, f'Received PATCH request to /insider-trading')
    input_data = request.get_json()
    result = update_insider_trading_supabase(input_data)
    return jsonify(result), result.get('status_code')

def save_file(file):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    return file_path

if __name__ == '__main__':
    app.run(debug=False)
