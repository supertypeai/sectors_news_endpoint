import json
from flask import Blueprint, request, jsonify
from middleware.api_key import require_api_key
from scripts.metadata import extract_metadata
from database import supabase, sectors_data, top300_data
from datetime import datetime
from scripts.scorer import get_article_score
from scripts.summary_news import summarize_news
from scripts.classifier import (
    get_tickers,
    get_tags_chat,
    get_subsector_chat,
    load_company_data,
    predict_dimension,
    get_sentiment_chat,
)

COMPANY_DATA = load_company_data()

articles_module = Blueprint('articles', __name__)


@articles_module.route("/articles", methods=["POST"])
@require_api_key
def add_article():
    input_data = request.get_json()
    result = sanitize_insert(input_data)
    return jsonify(result), result.get("status_code")


@articles_module.route("/articles/list", methods=["POST"])
@require_api_key
def add_articles():
    input_data = request.get_json()
    result_list = []
    for data in input_data:
        result = sanitize_insert(data)
        result_list.append(result)
    return jsonify(result_list)


@articles_module.route("/articles", methods=["GET"])
def get_articles():
    subsector = request.args.get("subsector")
    if not subsector:
        request.args.get("sub_sector")

    id = request.args.get("id")

    query = supabase.table("idx_news").select("*")
    if subsector:
        query = query.eq("sub_sector", subsector)

    if id:
        query = query.eq("id", id)

    response = query.execute()
    return jsonify(response.data), 200


@articles_module.route("/articles", methods=["DELETE"])
@require_api_key
def delete_article():
    input_data = request.get_json()
    id_list = input_data.get("id_list")
    supabase.table("idx_news").delete().in_("id", id_list).execute()
    return jsonify({"status": "success", "message": f"Deleted"}), 200



@articles_module.route("/articles", methods=["PATCH"])
@require_api_key
def update_article():
    input_data = request.get_json()
    result = sanitize_update(input_data)
    return jsonify(result), result.get("status_code")


@articles_module.route("/url-article", methods=["POST"])
@require_api_key
def get_article_from_url():
    input_data = request.get_json()
    data = generate_article(input_data)
    return data, 200


@articles_module.route("/url-article/post", methods=["POST"])
@require_api_key
def post_article_from_url():
    input_data = request.get_json()
    result = sanitize_insert(input_data, generate=False)
    return jsonify(result), result.get("status_code")


@articles_module.route("/evaluate-article", methods=["POST"])
@require_api_key
def evaluate_article():
    article = request.get_json()
    body = article.get("body")
    fp_gate = filter_fp(article)
    if fp_gate:
        return jsonify({"score": str(get_article_score(body))})
    else:
        return jsonify({"score": str(0)})
    
def filter_fp(article):
    # article title
    body = article['body'].upper().replace(',', ' ').replace('.', ' ').replace('-', ' ').replace("'", ' ').split(' ')
    title = article['title'].upper().replace(',', ' ').replace('.', ' ').replace('-', ' ').replace("'", ' ').split(' ')
    text = [*title, *body]
    
    # Indonesia relevancy indicator with keywords
    indo_indicator = ['INDONESIA', 'INDONESIAN', 'NUSANTARA', 'JAVA', 'JAKARTA', 'JAWA', 'IHSG', 'IDR', 'PT', 'IDX', 'TBK', 'OJK']
    
    # Get top 300 market cap companies
    top300 = top300_data
    
    symbols = [record['symbol'] for record in top300]

    # Combine the filter  
    filter = [*indo_indicator, *symbols]

    
    # Indonesia's Indicator filter, or ticker filter (top 300 market cap)
    condition_1_2 = False
    for word in text:
        if word in filter:
            condition_1_2 = True
            break
    
    # If it has ticker
    cond3 = len(article['tickers']) > 0
    result = condition_1_2 | cond3
    # True pass, False is not high quality
    return result

def sanitize_insert(data, generate=True):
    new_article = sanitize_article(data, generate)
    # Redundancy check, ignore article that has the same URL
    all_articles_db = supabase.table("idx_news").select("*").eq("source", new_article.get("source")).execute()
    links = {}
    for article_db in all_articles_db.data:
        if article_db.get("source") not in links.keys():
            links[article_db.get("source")] = article_db.get("id")

    if new_article.get("source") in links.keys():
        return {
            "status": "restricted",
            "message": f"Insert failed! Duplicate source",
            "status_code": 400,
            "id_duplicate": links[new_article.get("source")],
        }

    # Insert new article
    response = supabase.table("idx_news").insert(new_article).execute()
    return {"status": "success", "id": response.data[0]["id"], "status_code": 200}


def sanitize_update(data):
    new_article = sanitize_article(data, generate=False)
    record_id = data.get("id")

    if not record_id:
        return jsonify({"error": "Record ID is required", "status_code": 400})

    response = (
        supabase.table("idx_news").update(new_article).eq("id", record_id).execute()
    )

    return {
        "message": "Record updated successfully from table idx_news",
        "data": response.data,
        "status_code": 200,
    }

def sanitize_article(data, generate=True):
    # Sanitization v1.0
    title = data.get("title").strip() if data.get("title") else None
    body = data.get("body").strip() if data.get("body") else None
    source = data.get("source").strip()
    timestamp_str = data.get("timestamp").strip()
    timestamp_str = timestamp_str.replace("T", " ")
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    score = int(data.get("score").strip()) if data.get("score") else None

    sub_sector = []

    # Handle get subsector (subsector, sub_sector) (string, list, empty)
    if "sub_sector" in data and isinstance(data.get("sub_sector"), str) and data.get("sub_sector").strip() != "":
        sub_sector.append(data.get("sub_sector").strip())
    elif "subsector" in data and isinstance(data.get("subsector"), str) and data.get("subsector").strip() != "":
        sub_sector.append(data.get("subsector").strip())
    elif "sub_sector" in data and isinstance(data.get("sub_sector"), list):
        sub_sector = data.get("sub_sector")
    elif "subsector" in data and isinstance(data.get("subsector"), list):
        sub_sector = data.get("subsector")

    sector = ""

    # Get sector if already exists, if not, generate with dictionary
    if "sector" in data and isinstance(data.get("sector"), str):
        sector = data.get("sector").strip()
    else:
        if len(sub_sector) != 0 and sub_sector[0] in sectors_data.keys():
            sector = sectors_data[sub_sector[0]]
        else:
            sector = ""

    tags = data.get("tags", [])
    tickers = data.get("tickers", [])
    dimension = data.get("dimension", None)

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

    if title == "" or body == "":
        generated_title, generated_body = extract_metadata(source)
        if title == "":
            title = generated_title
        if body == "":
            body = generated_body

    new_article = {
        "title": title,
        "body": body,
        "source": source,
        "timestamp": timestamp.isoformat(),
        "sector": sector,
        "sub_sector": sub_sector,
        "tags": tags,
        "tickers": tickers,
        "dimension": dimension,
        "score": score
    }

    if generate:
        new_title, new_body = summarize_news(new_article["source"])

        if len(new_body) > 0:
            new_article["body"] = new_body

        if len(new_title) > 0:
            new_article["title"] = new_title

    return new_article


def generate_article(data):
    source = data.get("source").strip()
    timestamp_str = data.get("timestamp").strip()
    timestamp_str = timestamp_str.replace("T", " ")
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

    new_article = {
        "title": "",
        "body": "",
        "source": source,
        "timestamp": timestamp.isoformat(),
        "sector": "",
        "sub_sector": [],
        "tags": [],
        "tickers": [],
        "dimension": None,
        "score": None
    }

    title, body = summarize_news(source)
    # print(title, body)
    if len(body) > 0:
        # Generate the metadata for the new article
        tickers = get_tickers(body)
        tags = get_tags_chat(body, preprocess=False)
        sub_sector_result = get_subsector_chat(body)
        sentiment = get_sentiment_chat(body)
        tags.append(sentiment[0])
        
        # Check generated tickers
        checked_tickers = []
        # valid_tickers = supabase.rpc("get_tickers").execute().data['data']
        valid_tickers = [COMPANY_DATA[ticker]['symbol'] for ticker in COMPANY_DATA]
        for ticker in tickers:
            if ticker in valid_tickers or ticker + ".JK" in valid_tickers:
                checked_tickers.append(ticker)
        tickers = checked_tickers

        # If no ticker detected, use generated subsector
        if len(tickers) == 0:
            sub_sector = [sub_sector_result[0].lower()]
        # If ticker detected, get the company's subsector
        else:
            sub_sector = [COMPANY_DATA[ticker]['sub_sector'] for ticker in tickers if ticker in COMPANY_DATA]

        sector = ""

        for e in sub_sector:
            if e in sectors_data.keys():
                sector = sectors_data[e]
                break

        new_article["title"] = title
        new_article["body"] = body
        new_article["sector"] = sector
        new_article["sub_sector"] = sub_sector
        new_article["tags"] = tags
        new_article["tickers"] = tickers
        new_article["dimension"] = predict_dimension(title, body)
        new_article["score"] = int(get_article_score(body))

        return new_article
    else:
        return new_article
