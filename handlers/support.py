from flask import request
from database import supabase
from datetime import datetime, timedelta, timezone

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
