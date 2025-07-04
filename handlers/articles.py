import json
import re
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
    NewsClassifier,
)
from model.news_model import News
import pytz
import asyncio
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor

timezone = pytz.timezone("Asia/Bangkok")

COMPANY_DATA = load_company_data()
SECTORS_DATA = sectors_data

# Initialize the classifier
classifier = NewsClassifier()

# In-memory store for batch tasks and thread pool
batch_tasks = {}
executor = ThreadPoolExecutor(max_workers=4)
batch_task_lock = threading.Lock()

articles_module = Blueprint("articles", __name__)


@articles_module.route("/articles", methods=["POST"])
@require_api_key
def add_article():
    """
    @API-function
    @brief Insert news article.

    @request-args
    news-data: JSON

    @return JSON response of insertion status.
    """
    input_data = request.get_json()
    result = sanitize_insert(input_data)
    return jsonify(result), result.get("status_code")


@articles_module.route("/articles/list", methods=["POST"])
@require_api_key
def add_articles():
    """
    @API-function
    @brief Insert news article in list form.

    @request-args
    news-data: List of JSON

    @return List of JSON response of insertion status.
    """
    input_data = request.get_json()
    result_list = []
    for data in input_data:
        result = sanitize_insert(data)
        result_list.append(result)
    return jsonify(result_list)


@articles_module.route("/articles", methods=["GET"])
def get_articles():
    """
    @API-function
    @brief Get news articles.

    @request-args
    subsector: str, optional
    sub_sector: str, optional
    id: int, optional

    @return JSON of response data.
    """
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
    """
    @API-function
    @brief Delete news article.

    @request-args
    input-data: JSON
    id: list of int

    @return JSON response of deletion status.
    """
    input_data = request.get_json()
    id_list = input_data.get("id_list")
    supabase.table("idx_news").delete().in_("id", id_list).execute()
    return jsonify({"status": "success", "message": f"Deleted"}), 200


@articles_module.route("/articles", methods=["PATCH"])
@require_api_key
def update_article():
    """
    @API-function
    @brief Update news articles.

    @request-args
    news-data: JSON

    @return JSON response of update status.
    """
    input_data = request.get_json()
    result = sanitize_update(input_data)
    return jsonify(result), result.get("status_code")


@articles_module.route("/url-article", methods=["POST"])
@require_api_key
def get_article_from_url():
    """
    @API-function
    @brief Inference news articles from URL.

    @request-args
    input-data: JSON

    @return JSON response of the inferenced article.
    """
    try:
        input_data = request.get_json()
        data = generate_article(input_data)
        return data.to_json(), 200
    except Exception as e:
        print(f"[ERROR] Failed to generate article: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@articles_module.route("/url-articles/batch", methods=["POST"])
@require_api_key
def post_articles_from_urls_batch():
    """
    @API-function
    @brief Post a batch of news articles from URLs for asynchronous processing.

    @request-args
    news-data: List of JSON objects, each with 'source' and 'timestamp'

    @return JSON response with a task ID.
    """
    input_data = request.get_json()
    if not isinstance(input_data, list):
        return (
            jsonify({"status": "error", "message": "Input must be a list of articles"}),
            400,
        )

    task_id = str(uuid.uuid4())
    with batch_task_lock:
        batch_tasks[task_id] = {"status": "pending", "result": None}

    # Run processing in a background thread using asyncio
    thread = threading.Thread(target=run_async_processor, args=(task_id, input_data))
    thread.start()

    return jsonify({"status": "processing", "task_id": task_id}), 202


@articles_module.route("/url-articles/batch/<task_id>", methods=["GET"])
@require_api_key
def get_batch_articles_status(task_id):
    """
    @API-function
    @brief Get the status and result of a batch article processing task.

    @request-args
    task_id: str

    @return JSON response with status and results if completed.
    """
    with batch_task_lock:
        task = batch_tasks.get(task_id)

    if not task:
        return jsonify({"status": "error", "message": "Task not found"}), 404

    if task["status"] == "completed":
        return jsonify({"status": "completed", "result": task["result"]}), 200
    else:
        return jsonify({"status": "not ready"}), 202


@articles_module.route("/url-article/post", methods=["POST"])
@require_api_key
def post_article_from_url():
    """
    @API-function
    @brief Post inferenced news articles.

    @request-args
    news-data: JSON

    @return JSON response of insertion status.
    """
    input_data = request.get_json()
    result = sanitize_insert(input_data, generate=False)
    return jsonify(result), result.get("status_code")


@articles_module.route("/evaluate-article", methods=["POST"])
@require_api_key
def evaluate_article():
    """
    @API-function
    @brief Get score of news article.

    @request-args
    article: JSON

    @return JSON response of score.
    """
    article = request.get_json()
    body = article.get("body")
    fp_gate = filter_fp(article)
    if fp_gate:
        return jsonify({"score": str(get_article_score(body))})
    else:
        return jsonify({"score": str(0)})


@articles_module.route("/stock-split", methods=["POST"])
@require_api_key
def insert_stock_split():
    """
    @API-function
    @brief Insert stock split news.

    @request-args
    stock-split-data: JSON

    @return JSON response of insertion status.
    """
    input_data = request.get_json()
    result = generate_stock_split_article(input_data)
    return result


@articles_module.route("/dividend", methods=["POST"])
@require_api_key
def insert_dividend():
    """
    @API-function
    @brief Insert dividend news.

    @request-args
    dividend-data: JSON

    @return JSON response of insertion status.
    """
    input_data = request.get_json()
    result = generate_dividend_article(input_data)
    return result


def filter_fp(article):
    """
    @helper-function
    @brief Filter false-positives for news.

    @param article Article to be filtered.

    @return JSON response of insertion status.
    """
    # article title
    body = (
        article["body"]
        .upper()
        .replace(",", " ")
        .replace(".", " ")
        .replace("-", " ")
        .replace("'", " ")
        .split(" ")
    )
    title = (
        article["title"]
        .upper()
        .replace(",", " ")
        .replace(".", " ")
        .replace("-", " ")
        .replace("'", " ")
        .split(" ")
    )
    text = [*title, *body]

    # Indonesia relevancy indicator with keywords
    indo_indicator = [
        "INDONESIA",
        "INDONESIAN",
        "NUSANTARA",
        "JAVA",
        "JAKARTA",
        "JAWA",
        "IHSG",
        "IDR",
        "PT",
        "IDX",
        "TBK",
        "OJK",
    ]

    # Get top 300 market cap companies
    top300 = top300_data

    symbols = [record["symbol"] for record in top300]

    # Combine the filter
    filter = [*indo_indicator, *symbols]

    # Indonesia's Indicator filter, or ticker filter (top 300 market cap)
    condition_1_2 = False
    for word in text:
        if word in filter:
            condition_1_2 = True
            break

    # If it has ticker
    cond3 = len(article["tickers"]) > 0
    result = condition_1_2 | cond3
    # True pass, False is not high quality
    return result


def sanitize_insert(data, generate=True):
    """
    @database-function
    @brief Insert news articles.

    @param data Article to be inserted.

    @return JSON response of insertion status.
    """
    new_article: News = News.sanitize_article(data, generate)
    # Redundancy check, ignore article that has the same URL
    all_articles_db = (
        supabase.table("idx_news")
        .select("*")
        .eq("source", new_article.source)
        .execute()
    )
    links = {}
    for article_db in all_articles_db.data:
        if article_db.get("source") not in links.keys():
            links[article_db.get("source")] = article_db.get("id")

    if new_article.source in links.keys():
        return {
            "status": "restricted",
            "message": f"Insert failed! Duplicate source",
            "status_code": 400,
            "id_duplicate": links[new_article.source],
        }

    # Insert new article
    print(new_article.to_dict())
    response = supabase.table("idx_news").insert(new_article.to_dict()).execute()
    try:
        print(response, response.data)
        return {"status": "success", "id": response.data[0]["id"], "status_code": 200}
    except Exception as e:
        if len(response.data) == 0:
            return {"status": "failed", "error": "Empty response", "status_code": 500}
        return {"status": "failed", "error": str(e), "status_code": 500}


def sanitize_update(data):
    """
    @database-function
    @brief Update news articles.

    @param data Updated article.

    @return JSON response of update status.
    """
    new_article: News = News.sanitize_article(data, generate=False)
    record_id = data.get("id")

    if not record_id:
        return jsonify({"error": "Record ID is required", "status_code": 400})

    response = (
        supabase.table("idx_news")
        .update(new_article.to_dict())
        .eq("id", record_id)
        .execute()
    )

    return {
        "message": "Record updated successfully from table idx_news",
        "data": response.data,
        "status_code": 200,
    }


def run_async_processor(task_id, articles_data):
    """Helper to run the async processor in a new event loop."""
    asyncio.run(process_batch_articles_async(task_id, articles_data))


async def process_batch_articles_async(task_id, articles_data):
    """
    Processes a batch of articles from URLs asynchronously.
    """
    tasks = [generate_article_async(data) for data in articles_data]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            source_url = articles_data[i].get("source", "unknown")
            print(f"[ERROR] Failed to generate article for {source_url}: {result}")
            processed_results.append({"source": source_url, "error": str(result)})
        else:
            processed_results.append(result.to_json())

    with batch_task_lock:
        batch_tasks[task_id]["status"] = "completed"
        batch_tasks[task_id]["result"] = processed_results


async def generate_article_async(data):
    """
    @helper-function
    @brief Generate article from URL asynchronously.
    @param data source URL and timestamp.
    @return Generated article in News model.
    """
    loop = asyncio.get_running_loop()
    source = data.get("source").strip()

    try:
        timestamp_str = data.get("timestamp").strip()
        timestamp_str = timestamp_str.replace("T", " ")
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

        new_article = News(
            title="",
            body="",
            source=source,
            timestamp=timestamp.isoformat(),
            sector="",
            sub_sector=[],
            tags=[],
            tickers=[],
            dimension=None,
            score=None,
        )

        # Run synchronous summarize_news in a thread pool
        title, body = await loop.run_in_executor(executor, summarize_news, source)

        if len(body) > 0:
            (
                tags,
                tickers,
                sub_sector_result,
                sentiment,
                dimension,
            ) = await classifier.classify_article_async(title, body)

            if sentiment and len(sentiment) > 0:
                tags.append(sentiment[0])

            checked_tickers = []
            valid_tickers = [COMPANY_DATA[ticker]["symbol"] for ticker in COMPANY_DATA]
            for ticker in tickers:
                if ticker in valid_tickers or f"{ticker}.JK" in valid_tickers:
                    checked_tickers.append(ticker)
            tickers = checked_tickers

            if len(tickers) == 0 and sub_sector_result and len(sub_sector_result) > 0:
                sub_sector = [sub_sector_result[0].lower()]
            else:
                sub_sector = [
                    COMPANY_DATA[ticker]["sub_sector"]
                    for ticker in tickers
                    if ticker in COMPANY_DATA
                ]

            sector = ""
            for e in sub_sector:
                if e in sectors_data:
                    sector = sectors_data[e]
                    break

            new_article.title = title
            new_article.body = body
            new_article.sector = sector
            new_article.sub_sector = sub_sector
            new_article.tags = tags
            new_article.tickers = tickers
            new_article.dimension = dimension
            new_article.score = int(get_article_score(body))

        return new_article
    except Exception as e:
        print(f"[ERROR] Error in generate_article_async for source {source}: {e}")
        return News(
            title="Error processing article",
            body=f"Failed to process article content from {source}",
            source=source,
            timestamp=datetime.now().isoformat(),
            sector="",
            sub_sector=[],
            tags=[],
            tickers=[],
            dimension=None,
            score=0,
        )


def generate_article(data):
    """
    @helper-function
    @brief Generate article from URL.

    @param data source URL and timestamp.

    @return Generated article in News model.
    """
    return asyncio.run(generate_article_async(data))


def generate_stock_split_article(data_list):
    """
    @helper-function
    @brief Generate stock split articles.

    @param data_list List of stock split data.

    @return List of JSON response of insertion status.
    """
    response_list = []
    for data in data_list:
        ticker = data.get("symbol").strip()
        date = data.get("date").strip()
        split_ratio = data.get("split_ratio")
        updated_on = data.get("updated_on").strip()
        applied_on = data.get("applied_on").strip()

        new_article = {
            "title": convert_dates_to_long_format(
                f"{ticker} Announces Stock Split by Ratio {split_ratio}x: Effective from {date}"
            ),
            "body": convert_dates_to_long_format(
                f"{ticker} has announced a stock split with a ratio of {split_ratio} to adjust its share structure. The split will be effective starting on {date}. The announcement was last updated on {updated_on} and applied in sectors at {applied_on}."
            ),
            "source": "https://sahamidx.com/?view=Stock.Split&path=Stock&field_sort=split_date&sort_by=DESC&page=1",
            "timestamp": datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S"),
            "sector": SECTORS_DATA[COMPANY_DATA[ticker]["sub_sector"]],
            "sub_sector": [COMPANY_DATA[ticker]["sub_sector"]],
            "tags": ["Stock split", "Corporate action"],
            "tickers": [ticker],
            "dimension": None,
            "score": None,
        }

        new_article["dimension"] = predict_dimension(
            new_article["title"], new_article["body"]
        )

        # Insert new article
        try:
            response = supabase.table("idx_news").insert(new_article).execute()
            response_list.append({"status": "success", "id": response.data[0]["id"]})
        except Exception as e:
            response_list.append({"status": "failed", "error": str(e)})
    return response_list


def generate_dividend_article(data_list):
    """
    @helper-function
    @brief Generate dividend articles.

    @param data_list List of dividend data.

    @return List of JSON response of insertion status.
    """
    response_list = []
    for data in data_list:
        ticker = data.get("symbol").strip()
        dividend_amount = data.get("dividend_amount")
        ex_date = data.get("ex_date").strip()
        updated_on = data.get("updated_on").strip()
        payment_date = data.get("payment_date").strip()

        new_article = {
            "title": convert_dates_to_long_format(
                f"{ticker} Announces Dividend of {dividend_amount} IDR, Ex-Date on {ex_date}"
            ),
            "body": convert_dates_to_long_format(
                f"{ticker} has declared a dividend of {dividend_amount} IDR per share, with an ex-dividend date set for {ex_date}. The payment is scheduled to be made on {payment_date}. This update was last confirmed on {updated_on}."
            ),
            "source": "https://sahamidx.com/?view=Stock.Cash.Dividend&path=Stock&field_sort=rg_ng_ex_date&sort_by=DESC&page=1",
            "timestamp": datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S"),
            "sector": SECTORS_DATA[COMPANY_DATA[ticker]["sub_sector"]],
            "sub_sector": [COMPANY_DATA[ticker]["sub_sector"]],
            "tags": ["Dividend", "Corporate action"],
            "tickers": [ticker],
            "dimension": None,
            "score": None,
        }

        new_article["dimension"] = predict_dimension(
            new_article["title"], new_article["body"]
        )

        # Insert new article
        try:
            response = supabase.table("idx_news").insert(new_article).execute()
            response_list.append({"status": "success", "id": response.data[0]["id"]})
        except Exception as e:
            response_list.append({"status": "failed", "error": str(e)})
    return response_list


def convert_dates_to_long_format(text):
    """
    Converts all datetime formats in the given text to "Month Date, Year".

    @param text: The input text containing datetime strings.
    @return: The text with all datetime strings converted to "Month Date, Year".
    """
    # Define the regex pattern to match datetime strings
    date_pattern = re.compile(
        r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\+\d{2}:\d{2})?)?"
    )

    def replace_date(match):
        # Parse the matched date string to a datetime object
        date_str = match.group(0)
        date_obj = datetime.fromisoformat(date_str)
        # Convert the datetime object to the desired format
        return date_obj.strftime("%B %d, %Y")

    # Replace all matched date strings in the text
    return date_pattern.sub(replace_date, text)
