'''
Script to reclassify all the tags of the news in the current database
'''
import dotenv
import os
from supabase import create_client, Client
from classifier import get_tags_chat, classify_llama

if __name__ == "__main__":
    dotenv.load_dotenv()

    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    supabase: Client = create_client(os.getenv("SUPABASE_URL"), SUPABASE_KEY)

    all_news = supabase.table('idx_news').select('*').execute().data

    for news in all_news:
        print("\n")
        print(f"ID {news['id']}")

        print("Title")
        print(news["title"])
        print("Body")
        print(news["body"])
        print("Old Tags")
        print(news['tags'])
        print("New Tags")
        new_tags = classify_llama(news['body'], "tags")
        print(new_tags)

        print("\n")

        supabase.table("idx_news").update({
            "tags": new_tags
        }).eq("id", news["id"]).execute()