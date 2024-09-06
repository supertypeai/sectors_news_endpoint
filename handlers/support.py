from flask import request
from database import supabase
from datetime import datetime, timedelta, timezone


def delete_outdated_news():
    news = (
        supabase.table("idx_news").select("*").order("timestamp", desc=False).execute()
    )
    outdated_news = datetime.now(timezone.utc) - timedelta(days=120)
    print(datetime.now(), outdated_news)
    to_be_deleted = []
    for article in news.data:
        log_timestamp = datetime.fromisoformat(
            article["timestamp"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        if log_timestamp < outdated_news:
            to_be_deleted.append(article["id"])

    if to_be_deleted:
        try:
            for article_id in to_be_deleted:
                response = (
                    supabase.table("idx_news").delete().eq("id", article_id).execute()
                )
                print(f"Deleted news ID: {article_id}, {len(to_be_deleted)}")
        except Exception as e:
            print(f"Failed to delete news: {e}")


def delete_outdated_logs():
    logs = supabase.table("idx_news_logs").select("*").execute()
    if len(logs.data) > 50:
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        print(datetime.now(), two_days_ago)
        to_be_deleted = []
        for log in logs.data:
            log_timestamp = datetime.fromisoformat(
                log["timestamp"].replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            if log_timestamp < two_days_ago:
                to_be_deleted.append(log["id"])

        if to_be_deleted:
            try:
                for log_id in to_be_deleted:
                    response = (
                        supabase.table("idx_news_logs")
                        .delete()
                        .eq("id", log_id)
                        .execute()
                    )
                    print(f"Deleted log ID: {log_id}")
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
    delete_outdated_news()
