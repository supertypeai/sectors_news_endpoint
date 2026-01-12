from __future__ import annotations

from flask import request
from deep_translator import GoogleTranslator
from database import supabase
from datetime import datetime, timedelta, timezone

import re 
import json 

last_delete_logs_run = None
last_delete_news_run = None

INHERIT = ["waris", "inheritance", "hibah", "grant", "bequest"]
MESOP = ["mesop", "msop", "esop", "program opsi saham", "employee stock option"]
FREEFLOAT = ["free float", "free-float", "freefloat", "pemenuhan porsi publik"]
TRANSFER = [
    "transfer", "pemindahan", "konversi", "conversion",
    "neutral", "tanpa perubahan", "alih", "pengalihan"
]

# Keyword banks for side-signals (parser may pass text here)
_KW_BUY = [
    "beli", "pembelian", "buy", "akumulasi", "investasi", "acquisition",
    "penambahan", "increase", "buyback", "buy back", "investment",
    "peningkatan", "akuisisi"
]
_KW_SELL = [
    "jual", "penjualan", "sell", "divestasi", "divestment", "pengurangan",
    "reduksi", "disposal"
]
_KW_TRANSFER = [
    "transfer", "pemindahan", "konversi", "conversion", "neutral",
    "tanpa perubahan", "alih", "pengalihan"
]
_KW_INHERIT = ["waris", "inheritance", "hibah", "grant", "bequest"]
_KW_MESOP = ["mesop", "msop", "esop", "program opsi saham", "employee stock option"]
_KW_FREEFLOAT = ["free float", "free-float", "freefloat", "pemenuhan porsi publik"]
_KW_RESTRUCTURING = ["restrukturisasi", "restructuring", "reorganisasi", "penyelesaian penurunan modal"]
_KW_REPURCHASE = ['repo', 'transaksi repurchase', 'transaksi repo']
_KW_PLACEMENT = ['penempatan saham revo', 'penempatan']


def translator(text: str) -> str:   
    try: 
        return GoogleTranslator(source='auto', target='en').translate(text) 
    except Exception as error: 
        print(f"GoogleTranslator failed: {error}. Returning original text.") 
        return text
    

def _any_kw(text_lower: str, banks: list[str]) -> bool:
    return any(bank in text_lower for bank in banks)


def _crosses_50(before_pp: float, after_pp: float) -> bool:
    try:
        b = float(before_pp)
        a = float(after_pp)
    except Exception:
        return False
    return (b < 50 <= a) or (b >= 50 > a)


def detect_tags_for_new_document(
    purpose: str,
    share_percentage_before: float,
    share_percentage_after: float,
    transaction_type: str,
    price_transaction: list[dict[str, any]]
) -> list[str]: 
    purpose = (purpose or '').lower()

    detect_tag = {
        "mesop": _any_kw(purpose, _KW_MESOP),
        "free-float-compliance": _any_kw(purpose, _KW_FREEFLOAT),
        "inheritance": _any_kw(purpose, _KW_INHERIT),
        "share-transfer": _any_kw(purpose, _KW_TRANSFER),
        'capital-restructuring': _any_kw(purpose, _KW_RESTRUCTURING),
        'investment': _any_kw(purpose, _KW_BUY),
        'divestment': _any_kw(purpose, _KW_SELL),
        'repurchase-agreement': _any_kw(purpose, _KW_REPURCHASE),
        'placement': _any_kw(purpose, _KW_PLACEMENT)
    }
    
    tags = set()

    type_mix = {transaction.get('type') for transaction in price_transaction}

    is_mixed = len(type_mix) > 1

    for tag, found in detect_tag.items(): 
        if found: 
            if is_mixed and tag in ('investment', 'divestment'):
                continue
            tags.add(tag)

    if is_mixed:
        tags.add('investment' if transaction_type == 'buy' else 'divestment')

    if _crosses_50(share_percentage_before, share_percentage_after):
        tags.add("takeover")

    tags = list(tags)
    return sorted(tags)


def delete_outdated_news():
    global last_delete_news_run

    now = datetime.now()

    if last_delete_news_run is not None and last_delete_news_run > now - timedelta(
        hours=6
    ):
        return

    try:
        supabase.table("idx_news").delete().lte(
            "created_at", datetime.now(timezone.utc) - timedelta(days=120)
        ).execute()
        last_delete_news_run = now
    except Exception as e:
        print(f"Failed to delete logs: {e}")


def delete_outdated_logs():
    global last_delete_logs_run

    now = datetime.now()

    if last_delete_logs_run is not None and last_delete_logs_run > now - timedelta(
        hours=6
    ):
        return

    try:
        supabase.table("idx_news_logs").delete().lte(
            "timestamp", datetime.now(timezone.utc) - timedelta(days=7)
        ).execute()
        last_delete_logs_run = now
    except Exception as e:
        print(f"Failed to delete logs: {e}")


def log_request_info(level, message):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
        "request_method": request.method,
        "request_url": request.url,
        "remote_addr": request.remote_addr,
    }
    try:
        supabase.table("idx_news_logs").insert(log_entry).execute()
    except Exception as e:
        print("Failed to insert log")

    delete_outdated_logs()
    # delete_outdated_news()


def safe_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
    
    
def safe_int(value):
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None
    

def clean_company_name(company_name: str) -> str:
    needs_cleaning = False

    upper_count = sum(1 for char in company_name if char.isupper())
    lower_count = sum(1 for char in company_name if char.islower())

    # Check if the string is mostly uppercase
    if upper_count > lower_count:
        needs_cleaning = True
    
    # Check if all words are capitalized
    words = company_name.split()
    if not needs_cleaning and not all(word[0].isupper() for word in words if word):
        needs_cleaning = True
    
    # Check if last letter of the last word capitalized
    if not needs_cleaning and words:
        last_word = words[-1]
        if last_word and last_word[-1].isalpha() and last_word[-1].isupper():
            needs_cleaning = True

    if needs_cleaning:
        cleaned_name = company_name.title()
        cleaned_name = re.sub(r'\bPt\.?\b', 'PT', cleaned_name)
        return cleaned_name.strip()
    else:
        return company_name


def get_subsector_by_ticker(ticker: str) -> str:
    try:
        with open("./data/companies.json", "r") as f:
            companies = json.load(f)

        if ticker:
            ticker = ticker.strip()
            if ticker in companies:
                sub_sector = companies[ticker]["sub_sector"]
                return sub_sector
            else:
                return None 
    except (FileNotFoundError, KeyError, IndexError) as e:
        print(
            f"Could not update sub_sector from companies data: {e}"
        )


def convert_price_transaction(price_transaction: dict) -> list[dict[str, any]]:
    list_of_dict = []

    for index in range(len(price_transaction.get('prices'))):
        transactions = {
            "price": price_transaction.get('prices')[index],
            "amount_transacted": price_transaction.get('amount_transacted')[index],
            "type": price_transaction.get('types')[index],
            "date": price_transaction.get('dates')[index],
        }
        list_of_dict.append(transactions)

    return list_of_dict


def add_sentiment_tag(share_percentage_before: float, share_percentage_after: float) -> str:
    if share_percentage_before is None or share_percentage_after is None:
        return None 
    
    if share_percentage_after > share_percentage_before:
        return "bullish"
    elif share_percentage_after < share_percentage_before:
        return "bearish"
    
    return None 