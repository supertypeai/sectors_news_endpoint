from flask import Blueprint, request, jsonify, current_app
from handlers.articles import sanitize_insert
from middleware.api_key import require_api_key
from database import supabase, sectors_data
from datetime import datetime
from model.filings_model import Filing
from model.news_model import News
from model.price_transaction import PriceTransaction
from scripts.pdf_reader import extract_from_pdf
from scripts.generate_article import generate_article_filings
from scripts.summary_filings import summarize_filing
from scripts.classifier import (
    get_tickers,
)
from handlers.support import (
    safe_float, safe_int, clean_company_name, add_sentiment_tag,
    convert_price_transaction, get_subsector_by_ticker,
    INHERIT, MESOP, FREEFLOAT, TRANSFER
)
import os

filings_module = Blueprint("filings", __name__)


@filings_module.route("/pdf", methods=["POST"])
@require_api_key
def add_pdf_article():
    """
    @API-function
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

    uid = (
        request.form["uid"]
        if "uid" in request.form
        else request.form["UID"] if "UID" in request.form else None
    )

    purpose = request.form["purpose"] if "source" in request.form else ""

    if file and file.filename.lower().endswith(".pdf"):
        file_path = save_file(file, current_app.config["UPLOAD_FOLDER"])
        text = extract_from_pdf(file_path)
        text = generate_article_filings(source, purpose, sub_sector, type, text, uid)
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
    @API-function
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
    @API-function
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
    @API-function
    @brief Retrieves insider trading data from the database.

    @return JSON response containing the insider trading data.
    """
    response = supabase.table("idx_filings").select("*").execute()
    return response.data


@filings_module.route("/insider-trading", methods=["DELETE"])
@require_api_key
def delete_insider_trading():
    """
    @API-function
    @brief Deletes insider trading data based on the provided ID list.

    @return JSON response indicating success or failure.
    """
    input_data = request.get_json()
    id_list = input_data.get("id_list")
    response = (
        supabase.table("idx_filings")
        .select("UID")
        .in_("id", id_list)
        .not_.is_("UID", None)
        .execute()
    )
    if response.data:
        uids = [row["UID"] for row in response.data if row["UID"]]
        if uids:
            supabase.table("idx_filings").delete().in_("UID", uids).execute()
    supabase.table("idx_filings").delete().in_("id", id_list).execute()
    return jsonify({"status": "success", "message": "Deleted"}), 200


@filings_module.route("/insider-trading", methods=["PATCH"])
@require_api_key
def update_insider_trading():
    """
    @API-function
    @brief Updates insider trading data based on the provided input JSON data.

    @return JSON response indicating success or failure.
    """
    input_data = request.get_json()
    result = update_insider_trading_supabase(input_data, True)
    return jsonify(result), result.get("status_code")


def sanitize_filing(data):
    """
    @middleware-function
    @brief Sanitizes the filing data and generates a new article dictionary.

    @param data Dictionary containing the filing data.

    @return Dictionary containing the sanitized article data.
    """
    document_number = (
        data.get("document_number").strip() if data.get("document_number") else ""
    )
    company_name = data.get("company_name").strip() if data.get("company_name") else ""
    holder_name = (
        data.get("holder_name").strip()
        if data.get("holder_name")
        else (
            data.get("shareholder_name").strip() if data.get("shareholder_name") else ""
        )
    )
    holder_name = clean_company_name(holder_name)

    source = data.get("source").strip() if data.get("source") else ""
    ticker = data.get("ticker").strip() if data.get("ticker") else ""
    # category = data.get("category").strip()
    control_status = (
        data.get("control_status").strip() if data.get("control_status") else ""
    )

    share_percentage_before = safe_float(data.get("share_percentage_before"))
    share_percentage_after = safe_float(data.get("share_percentage_after"))
    
    if share_percentage_before is not None and share_percentage_after is not None:
        share_percentage_transaction = abs(share_percentage_before - share_percentage_after)
        share_percentage_transaction = float(f"{share_percentage_transaction:.4f}")
    else: 
        share_percentage_transaction = None 

    if not data.get('sub_sector'):
        sub_sector = get_subsector_by_ticker(ticker)
    else: 
        sub_sector = (
            data.get("sub_sector").strip()
            if data.get("sub_sector")
            else data.get("subsector").strip()
        )
         
    # purpose = data.get("purpose").strip()
    date_time = datetime.strptime(data.get("date_time"), "%Y-%m-%d %H:%M:%S")
    holder_type = data.get("holder_type")
    
    holding_before = safe_int(data.get("holding_before"))
    holding_after = safe_int(data.get("holding_after"))

    if holding_before is not None and holding_after is not None:
        # transaction_type = "buy" if holding_before < holding_after else "sell"
        amount_transaction = abs(holding_before - holding_after)
    else:
        # transaction_type = data.get("transaction_type").lower()
        amount_transaction = None

    # calculate price and types
    price_transactions = data.get("price_transaction")

    for key, value in price_transactions.items():
        if key == 'dates':
            formatted_dates = []
            for date in value:
                try:
                    parsed_date = date 
                    if not isinstance(date, str):
                        parsed_date = datetime.strftime(date, "%Y-%m-%d")
                    formatted_dates.append(parsed_date)
                except ValueError:
                    formatted_dates.append(None)
            price_transactions[key] = formatted_dates

    price_calculation = PriceTransaction(
        price_transactions.get("amount_transacted"), 
        price_transactions.get("prices"), 
        price_transactions.get("types")
    )
    unique_types = len(set(price_transactions.get("types")))
    if unique_types > 1:
        price, transaction_value, transaction_type = price_calculation.get_price_transaction_value_two_values() 
    else:
        price, transaction_value = price_calculation.get_price_transaction_value()
        transaction_type = (
            "buy" if holding_before < holding_after else "sell"
        )

    uid = (
        data.get("uid")
        if data.get("uid")
        else data.get("UID") if data.get("UID") else None
    )

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

    # Get purpose
    purpose = data.get('purpose', None)

    # Convert to list of dict
    price_transactions = convert_price_transaction(price_transactions)

    new_article = {
        "title": f"Informasi insider trading {holder_name} dalam {company_name}",
        "body": f"{document_number} - {date_time} - {holder_name} dengan status kontrol {control_status} dalam saham {company_name} berubah dari {holding_before} menjadi {holding_after}",
        "source": source,
        "purpose": purpose,
        "timestamp": str(date_time),
        "sector": sectors_data[sub_sector] if sub_sector in sectors_data.keys() else "",
        "sub_sector": sub_sector,
        "tags": [],
        "tickers": [ticker],
        "transaction_type": transaction_type,
        "holder_type": holder_type,
        "holding_before": holding_before,
        "holding_after": holding_after,
        "share_percentage_before": share_percentage_before,
        "share_percentage_after": share_percentage_after,
        "share_percentage_transaction": share_percentage_transaction,
        "amount_transaction": amount_transaction,
        "holder_name": holder_name,
        "price_transaction": price_transactions,
        "price": price,
        "transaction_value": transaction_value,
        "UID": uid,
    }

    # Prepare tags
    tags_from_input = data.get('tags')
    tag_list = [tags.strip() for tags in tags_from_input.split(',') if tags.strip()]
    sorted_tags = sorted(tag_list)
    new_article['tags'] = sorted_tags
    
    if not data.get('tags') or data.get('tags') == "":
        # Sentiment tag
        # sentiment_tag = add_sentiment_tag(share_percentage_before, share_percentage_after)

        # Buy Sell tag
        # if transaction_type == "buy":
        #     new_article["tags"].extend(['investment', sentiment_tag])
        # elif transaction_type == 'sell':
        #     new_article["tags"].extend(['divestment', sentiment_tag])

        # Prepare take over tag rule 
        if share_percentage_before is not None and share_percentage_after is not None:
            if (share_percentage_before < 50 <= share_percentage_after) or (share_percentage_before >= 50 > share_percentage_after):
                new_article["tags"].append("takeover")
        
        # Others tag 
        flag_checks = {
            "inheritance": INHERIT,
            "MESOP": MESOP,
            "free_float_requirement": FREEFLOAT,
            "share-transfer": TRANSFER
        }
        flag_tag = next(
            (flag for flag, values in flag_checks.items() if any(purpose.lower() in value for value in values)),
            None
        )

        if flag_tag:
            new_article["tags"].append(flag_tag)

        tags_sorted = sorted([tag for tag in new_article['tags'] if tag])
        new_article["tags"] = tags_sorted

    new_title, new_body = summarize_filing(new_article)

    if len(new_body) > 0:
        new_article["body"] = new_body

        # tickers = get_tickers(new_body)
        # tags = get_tags_chat(new_body)
        # sentiment = get_sentiment_chat(new_body)
        # sub_sector = get_subsector_chat(new_body)
        # tags.append(sentiment[0])

        # tags = get_tags(new_article) # causing nested array problem, adding the whole list into the final list
        # new_article["tags"].append(tags)

        # new_article["tags"] = get_tags(
        #     new_article
        # )  # instead of append, it replace the whole tags column
        # for ticker in tickers:
        #     if ticker not in new_article["tickers"]:
        #         new_article["tickers"].append(ticker)

    if len(new_title) > 0:
        new_article["title"] = new_title

    new_article["tags"] = list(set(new_article["tags"]))  # remove duplicates if any

    return new_article


def sanitize_filing_article(data, generate=True):
    """
    @middleware-function
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

    tickers = data.get("tickers", [])

    holding_before = safe_int(data.get("holding_before"))
    holding_after = safe_int(data.get("holding_after"))
    share_percentage_before = safe_float(data.get("share_percentage_before"))
    share_percentage_after = safe_float(data.get("share_percentage_after"))

    # Calculate values only if have valid data
    if share_percentage_before is not None and share_percentage_after is not None:
        share_percentage_transaction = abs(share_percentage_before - share_percentage_after)
        share_percentage_transaction = float(f"{share_percentage_transaction:.4f}")
    else:
        share_percentage_transaction = None
    
    if holding_before is not None and holding_after is not None:
        # transaction_type = "buy" if holding_before < holding_after else "sell"
        amount_transaction = abs(holding_before - holding_after)
    else: 
        # transaction_type = data.get("transaction_type").lower() if data.get("transaction_type") else None
        amount_transaction = None
    
    holder_type = data.get("holder_type")
    holder_name = data.get("holder_name")
    holder_name = clean_company_name(holder_name)

    # calculate price and types
    price_transactions = data.get("price_transaction")
    for key, value in price_transactions.items():
        if key == 'dates':
            formatted_dates = []
            for date in value:
                try:
                    if isinstance(date, str):
                        formatted_dates.append(date)
                    elif hasattr(date, 'strftime'):
                        parsed_date = datetime.strftime(date, "%Y-%m-%d")
                        formatted_dates.append(parsed_date)
                except ValueError:
                    formatted_dates.append(None)
            price_transactions[key] = formatted_dates
            
    price_calculation = PriceTransaction(
        price_transactions.get("amount_transacted"), 
        price_transactions.get("prices"), 
        price_transactions.get("types")
    )
    unique_types = len(set(price_transactions.get("types")))
    if unique_types > 1:
        price, transaction_value, transaction_type = price_calculation.get_price_transaction_value_two_values() 
    else:
        price, transaction_value = price_calculation.get_price_transaction_value()
        transaction_type = (
            "buy" if holding_before < holding_after else "sell"
        )

    uid = (
        data.get("uid")
        if data.get("uid")
        else data.get("UID") if data.get("UID") else None
    )

    # Build tags list 
    tags = []

    # sentiment_tag = add_sentiment_tag(share_percentage_before, share_percentage_after)
    # if sentiment_tag:
    #     tags.append(sentiment_tag)

    flag_tag = data.get('flag_tags')
    if flag_tag:
        tags.append(flag_tag)

    # if transaction_type == 'buy':
    #     tags.append('investment')
    # elif transaction_type == 'sell':
    #     tags.append('divestment')

    # Prepare take over tag rule 
    if share_percentage_before is not None and share_percentage_after is not None:
        if (share_percentage_before < 50 <= share_percentage_after) or (share_percentage_before >= 50 > share_percentage_after):
            tags.append('takeover')

    tags = sorted(set(tags))

    price_transactions = convert_price_transaction(price_transactions)
    
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
        "share_percentage_before": share_percentage_before,
        "share_percentage_after": share_percentage_after,
        "share_percentage_transaction": share_percentage_transaction,
        "amount_transaction": amount_transaction,
        "holder_name": holder_name,
        "price": price,
        "transaction_value": transaction_value,
        "price_transaction": price_transactions,
        "UID": uid,
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
    @database-function
    @brief Inserts insider trading data into the Supabase database.

    @param data Dictionary containing the insider trading data.
    @param format Boolean indicating whether to format the data.

    @return Dictionary containing the status and inserted record ID.
    """
    # format : needs formatting
    if format:
        new_article = sanitize_filing(data=data)
    else:
        new_article = sanitize_filing_article(data=data, generate=False)

    news = True

    # Check if UID already exists
    if new_article.get("UID"):
        existing = (
            supabase.table("idx_filings")
            .select("*")
            .eq("UID", new_article["UID"])
            .execute()
        )
        if existing.data:
            news = False

    if news:
        new_article_for_news = new_article.copy()

        new_tags = []
        old_tags = new_article_for_news.get('tags', [])

        # if 'investment' in old_tags: 
        #     new_tags.append('buy')
        # elif 'divestment' in old_tags:
        #     new_tags.append('sell') 
        
        new_tags.append('insider-trading')
        new_article_for_news['tags'] = sorted(set(new_tags))

        news_article = News.from_filing(Filing(**new_article_for_news))
        response_news = (
            supabase.table("idx_news").insert(news_article.__dict__).execute()
        )
    
    inserted_filing = new_article.copy()
    if inserted_filing["tickers"]:
        inserted_filing["symbol"] = inserted_filing["tickers"][0]
    else:
        inserted_filing["symbol"] = None

    inserted_filing.pop("tickers", None)

    response = supabase.table("idx_filings").insert(inserted_filing).execute()

    if news:
        return {
            "status": "success",
            "id_filings": response.data[0]["id"],
            "id_news": response_news.data[0]["id"],
            "status_code": 200,
        }
    else:
        return {
            "status": "success",
            "id_filings": response.data[0]["id"],
            "status_code": 200,
        }


def update_insider_trading_supabase(data, is_generate: bool = False):
    """
    @database-function
    @brief Updates insider trading data in the Supabase database.

    @param data Dictionary containing the insider trading data.

    @return Dictionary containing the status and updated record data.
    """
    old_article = (
        supabase.table("idx_filings").select("*").eq("id", data.get("id")).execute()
    )
    new_article = sanitize_filing_article(data, generate=is_generate)
    record_id = data.get("id")
    if not record_id:
        return jsonify({"error": "Record ID is required", "status_code": 400})

    # Compare old and new article data
    if old_article.data:
        old_data = old_article.data[0]
        changes = {}

        for key in ["price_transaction"]:
            if old_data.get(key) != new_article.get(key):
                changes[key] = {"old": old_data.get(key), "new": new_article.get(key)}
        if changes:
            print(f"Data changes detected: {changes}")

    # Check for UID and price_transaction changes
    if new_article.get("UID") and "price_transaction" in changes:
        # Get paired data with same UID
        paired_data = (
            supabase.table("idx_filings")
            .select("*")
            .eq("UID", new_article["UID"])
            .execute()
        )

        if len(paired_data.data) == 2:  # Ensure exactly two records exist
            # Update price_transaction for both records
            for record in paired_data.data:
                if record["id"] != record_id:  # Update the paired record
                    other_article = record.copy()
            
                    other_article["price_transaction"] = new_article[
                        "price_transaction"
                    ]
                    other_holding_before = other_article['holding_before']
                    other_holding_after = other_article['holding_after']

                    other_price_transactions = other_article['price_transaction']
                    price_calculation = PriceTransaction(
                        other_price_transactions.get("amount_transacted"), 
                        other_price_transactions.get("prices"), 
                        other_price_transactions.get("types")
                    )
                    # Calculation price for the other data that have a matching uid
                    unique_types = len(set(other_price_transactions.get("types")))
                    if unique_types > 1:
                        price, transaction_value, transaction_type = price_calculation.get_price_transaction_value_two_values() 
                    else:
                        price, transaction_value = price_calculation.get_price_transaction_value()
                        transaction_type = (
                            "buy" if other_holding_before < other_holding_after else "sell"
                        )

                    other_article["price"] = price
                    other_article["transaction_value"] = transaction_value
                    other_article['transaction_type'] = transaction_type
                    other_article["amount_transaction"] = new_article[
                        "amount_transaction"
                    ]

                    supabase.table("idx_filings").update(other_article).eq(
                        "id", record["id"]
                    ).execute()

            # Recalculate price and transaction_value for current record
            # price, transaction_value = PriceTransaction(
            #     new_article["price_transaction"]["amount_transacted"],
            #     new_article["price_transaction"]["prices"],
            # ).get_price_transaction_value()
            # new_article["price"] = price
            # new_article["transaction_value"] = transaction_value

    response = (
        supabase.table("idx_filings").update(new_article).eq("id", record_id).execute()
    )

    return {
        "message": "Record updated successfully from table idx_filings",
        "data": response.data,
        "status_code": 200,
    }


def get_tags(filing):
    """
    @helper-function
    @brief Extracts and add tags from the filing data.

    @param filing Dictionary containing the filing data.

    @return List containing the extracted tags.
    """
    tags = []
    tags.append("insider-trading")
    tags.append("IDX")
    tags.append("Ownership Changes")
    tags.append("Bullish" if filing["transaction_type"].upper() == "BUY" else "Bearish")

    # Purpose is skipped
    return tags


def save_file(file, upload_folder):
    """
    @helper-function
    @brief Saves the uploaded file to the specified upload folder.

    @param file File object to be saved.
    @param upload_folder String specifying the upload folder path.

    @return String containing the file path of the saved file.
    """
    file_path = os.path.join(upload_folder, file.filename)
    file.save(file_path)
    return file_path
