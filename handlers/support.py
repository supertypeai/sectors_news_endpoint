from flask import request
from database import supabase
from datetime import datetime, timedelta, timezone

import re 

last_delete_logs_run = None
last_delete_news_run = None

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