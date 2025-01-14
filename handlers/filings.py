from flask import Blueprint, request, jsonify, current_app
from middleware.api_key import require_api_key
from database import supabase, sectors_data
from datetime import datetime
from model.price_transaction import PriceTransaction
from scripts.pdf_reader import extract_from_pdf
from scripts.generate_article import generate_article_filings
from scripts.summary_filings import summarize_filing
from scripts.classifier import (
    get_tickers,
    get_tags_chat,
    get_sentiment_chat,
)
import os

filings_module = Blueprint('filings', __name__)


@filings_module.route("/pdf", methods=["POST"])
@require_api_key
def add_pdf_article():
    """
    @brief Processes a PDF file with the IDX Format.

    @return JSON response of the processed PDF.
    """
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"status": "error", "message": "No selected file"}), 400

    source = request.form["source"] if "source" in request.form else ""
    sub_sector = (
        request.form["sub_sector"]
        if "sub_sector" in request.form
        else request.form["subsector"] if "subsector" in request.form else ""
    )
    # Either Insider or Institution
    type = request.form["holder_type"] if "holder_type" in request.form else ""
    type = type if type.lower() == "insider" or type.lower() == "insitution" else ""

    if file and file.filename.lower().endswith(".pdf"):
        file_path = save_file(file, current_app.config["UPLOAD_FOLDER"])
        text = extract_from_pdf(file_path)
        text = generate_article_filings(source, sub_sector, type, text)
        os.remove(file_path)

        try:
            return jsonify(text), 200
        except Exception as e:
            return {"status": "error", "message": f"Insert failed! Exception: {e}"}

    else:
        return jsonify({"status": "error", "message": "Invalid file type"}), 400


@filings_module.route("/pdf/post", methods=["POST"])
def add_filing_from_pdf():
    """
    @brief Insert filings from previous PDF inference.

    @return JSON response indicating success or failure.
    """
    input_data = request.get_json()
    result = insert_insider_trading_supabase(input_data, format=False)
    return jsonify(result), result.get("status_code")


@filings_module.route("/insider-trading", methods=["POST"])
@require_api_key
def add_insider_trading():
    """
    @brief Adds insider trading data by processing the input JSON data.

    @return JSON response indicating success or failure.
    """
    input_data = request.get_json()
    result = insert_insider_trading_supabase(input_data)
    return jsonify(result), result.get("status_code")


@filings_module.route("/insider-trading", methods=["GET"])
@require_api_key
def get_insider_trading():
    """
    @brief Retrieves insider trading data from the database.

    @return JSON response containing the insider trading data.
    """
    response = supabase.table("idx_filings").select("*").execute()
    return response.data


@filings_module.route("/insider-trading", methods=["DELETE"])
@require_api_key
def delete_insider_trading():
    """
    @brief Deletes insider trading data based on the provided ID list.

    @return JSON response indicating success or failure.
    """
    input_data = request.get_json()
    id_list = input_data.get("id_list")
    supabase.table("idx_filings").delete().in_("id", id_list).execute()
    return jsonify({"status": "success", "message": "Deleted"}), 200


@filings_module.route("/insider-trading", methods=["PATCH"])
@require_api_key
def update_insider_trading():
    """
    @brief Updates insider trading data based on the provided input JSON data.

    @return JSON response indicating success or failure.
    """
    input_data = request.get_json()
    result = update_insider_trading_supabase(input_data)
    return jsonify(result), result.get("status_code")


def sanitize_filing(data):
    """
    @brief Sanitizes the filing data and generates a new article dictionary.

    @param data Dictionary containing the filing data.

    @return Dictionary containing the sanitized article data.
    """
    document_number = (
        data.get("document_number").strip() if data.get("document_number") else ""
    )
    company_name = data.get("company_name").strip() if data.get("company_name") else ""
    holder_name = data.get("holder_name").strip() if data.get("holder_name") else data.get("shareholder_name").strip() if data.get("shareholder_name") else ""
    source = data.get("source").strip()
    ticker = data.get("ticker").strip() if data.get("ticker") else ''
    # category = data.get("category").strip()
    control_status = data.get("control_status").strip() if data.get("control_status") else ""
    holding_before = data.get("holding_before")
    holding_after = data.get("holding_after")
    sub_sector = (
        data.get("sub_sector").strip()
        if data.get("sub_sector")
        else data.get("subsector").strip()
    )
    # purpose = data.get("purpose").strip()
    date_time = datetime.strptime(data.get("date_time"), "%Y-%m-%d %H:%M:%S")
    holder_type = data.get("holder_type")
    transaction_type = "buy" if holding_before < holding_after else "sell"
    amount_transaction = abs(holding_before - holding_after)
    price_transaction = data.get("price_transaction")
    price, transaction_value = PriceTransaction(price_transaction['amount_transacted'], price_transaction['prices']).get_price_transaction_value()

    ticker_list = ticker.split(".")
    if len(ticker_list) > 1:
        if ticker_list[1].upper() == "JK":
            pass
        else:
            ticker_list[1] = ".JK"
            ticker = ticker_list[0] + ticker_list[1]
    else:
        ticker += ".JK"
    ticker = ticker.upper()

    new_article = {
        "title": f"Informasi insider trading {holder_name} dalam {company_name}",
        "body": f"{document_number} - {date_time} - {holder_name} dengan status kontrol {control_status} dalam saham {company_name} berubah dari {holding_before} menjadi {holding_after}",
        "source": source,
        "timestamp": str(date_time),
        "sector": sectors_data[sub_sector] if sub_sector in sectors_data.keys() else "",
        "sub_sector": sub_sector,
        "tags": ["insider-trading"],
        "tickers": [ticker],
        "transaction_type": transaction_type,
        "holder_type": holder_type,
        "holding_before": holding_before,
        "holding_after": holding_after,
        "amount_transaction": amount_transaction,
        "holder_name": holder_name,
        "price_transaction": price_transaction,
        "price": price,
        "transaction_value": transaction_value 
    }
    new_title, new_body = summarize_filing(new_article)

    if len(new_body) > 0:
        new_article["body"] = new_body
        tickers = get_tickers(new_body)
        tags = get_tags_chat(new_body)
        sentiment = get_sentiment_chat(new_body)
        # sub_sector = get_subsector_chat(new_body)
        tags.append(sentiment[0])
        new_article["tags"].append(tags)
        for ticker in tickers:
            if ticker not in new_article["tickers"]:
                new_article["tickers"].append(ticker)

    if len(new_title) > 0:
        new_article["title"] = new_title

    return new_article


def sanitize_filing_article(data, generate=True):
    """
    @brief Sanitizes the filing article data and generates a new article dictionary.

    @param data Dictionary containing the filing article data.
    @param generate Boolean indicating whether to generate a new title and body.

    @return Dictionary containing the sanitized article data.
    """
    title = data.get("title").strip() if data.get("title") else None
    body = data.get("body").strip() if data.get("body") else None
    source = data.get("source").strip()
    timestamp_str = data.get("timestamp").strip()
    timestamp_str = timestamp_str.replace("T", " ")
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    sub_sector = (
        data.get("sub_sector").strip()
        if data.get("sub_sector")
        else data.get("subsector").strip()
    )
    sector = sectors_data[sub_sector] if sub_sector in sectors_data.keys() else ""
    tags = data.get("tags", [])
    tickers = data.get("tickers", [])
    holding_before = data.get("holding_before")
    holding_after = data.get("holding_after")
    holder_type = data.get("holder_type")
    transaction_type = "buy" if holding_before < holding_after else "sell"
    amount_transaction = abs(holding_before - holding_after)
    holder_name = data.get("holder_name")
    price_transaction = data.get("price_transaction")
    
    price, transaction_value = PriceTransaction(price_transaction['amount_transacted'], price_transaction['prices']).get_price_transaction_value()

    new_article = {
        "title": title,
        "body": body,
        "source": source,
        "timestamp": timestamp.isoformat(),
        "sector": sector,
        "sub_sector": sub_sector,
        "tags": tags,
        "tickers": tickers,
        "transaction_type": transaction_type,
        "holder_type": holder_type,
        "holding_before": holding_before,
        "holding_after": holding_after,
        "amount_transaction": amount_transaction,
        "holder_name": holder_name,
        "price": price,
        "transaction_value": transaction_value,
        "price_transaction": price_transaction
    }

    if generate:
        new_title, new_body = summarize_filing(new_article)

        if len(new_body) > 0:
            new_article["body"] = new_body

        if len(new_title) > 0:
            new_article["title"] = new_title

    if "purpose" in new_article:
        del new_article["purpose"]

    return new_article


def insert_insider_trading_supabase(data, format=True):
    """
    @brief Inserts insider trading data into the Supabase database.

    @param data Dictionary containing the insider trading data.
    @param format Boolean indicating whether to format the data.

    @return Dictionary containing the status and inserted record ID.
    """
    # format : needs formatting
    if format:
        new_article = sanitize_filing(data)
    else:
        new_article = sanitize_filing_article(data, generate=False)

    response = supabase.table("idx_filings").insert(new_article).execute()
    return {"status": "success", "id": response.data[0]["id"], "status_code": 200}


def update_insider_trading_supabase(data):
    """
    @brief Updates insider trading data in the Supabase database.

    @param data Dictionary containing the insider trading data.

    @return Dictionary containing the status and updated record data.
    """
    new_article = sanitize_filing_article(data, generate=False)
    record_id = data.get("id")

    if not record_id:
        return jsonify({"error": "Record ID is required", "status_code": 400})

    response = (
        supabase.table("idx_filings")
        .update(new_article)
        .eq("id", record_id)
        .execute()
    )

    return {
        "message": "Record updated successfully from table idx_filings",
        "data": response.data,
        "status_code": 200,
    }


def save_file(file, upload_folder):
    """
    @brief Saves the uploaded file to the specified upload folder.

    @param file File object to be saved.
    @param upload_folder String specifying the upload folder path.

    @return String containing the file path of the saved file.
    """
    file_path = os.path.join(upload_folder, file.filename)
    file.save(file_path)
    return file_path
