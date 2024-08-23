import dotenv
import os
from supabase import create_client, Client
from classifier import predict_dimension

if __name__ == "__main__":
    dotenv.load_dotenv()

    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    supabase: Client = create_client(os.getenv("SUPABASE_URL"), SUPABASE_KEY)

    all_news = supabase.table("idx_news").select("*").execute().data

    for news in all_news:
        print("\n")
        print(f"ID {news['id']}")

        print("Title")
        print(news["title"])
        print("Body")
        print(news["body"])
        dimension = predict_dimension(news["title"], news["body"])
        print(dimension)

        print("\n")

        supabase.table("idx_news").update({"dimension": dimension}).eq(
            "id", news["id"]
        ).execute()
