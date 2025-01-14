'''
Script to filter news from False Positives
'''
from supabase import create_client, Client
import os
import dotenv
import json

dotenv.load_dotenv()

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase key and URL must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def filter_fp(article):
  # article title
  body = article['body'].upper().replace(',', ' ').replace('.', ' ').replace('-', ' ').replace("'", ' ').split(' ')
  title = article['title'].upper().replace(',', ' ').replace('.', ' ').replace('-', ' ').replace("'", ' ').split(' ')
  text = [*title, *body]

  # Indonesia relevancy indicator with keywords
  indo_indicator = ['INDONESIA', 'INDONESIAN', 'NUSANTARA', 'JAVA', 'JAKARTA', 'JAWA', 'IHSG', 'IDR', 'PT', 'IDX', 'TBK', 'OJK']
  
  # Get top 300 market cap companies
  with open("./data/top300.json", "r") as f:
    top300_data = json.load(f)
  
  symbols = [record['symbol'] for record in top300_data]

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

def delete_filtered_records(table_name, ids):
  for record_id in ids:
    # Delete the record where id matches record_id
    response = supabase.table(table_name).delete().eq("id", record_id).execute()

    print(response)

if __name__ == "__main__":
  # Get all news
  news = supabase.table('idx_news').select('*').execute().data
  to_delete = []
  to_delete_id = []
  to_delete_id_yahoo = []

  # print(news)

  count_yahoo = 0
  count_yahoo_deleted = 0

  for article in news:
    source = article['source'].split('/')
    if 'finance.yahoo.com' in source:
      count_yahoo += 1
    if filter_fp(article):
      # Pass filter, move to scoring
      print(article)
    else:
      # Delete from database
      to_delete.append(article)
      to_delete_id.append(article['id'])
      if 'finance.yahoo.com' in source:
        count_yahoo_deleted += 1
        to_delete_id_yahoo.append(article['id'])
      
  # print(news)
  print("to delete:", to_delete, len(to_delete), len(news))

  with open('./data/to_delete1.json', 'w') as f:
    f.write(json.dumps(to_delete))

  print(to_delete_id)
  print("total yahoo", count_yahoo)
  print("total yahoo deleted", count_yahoo_deleted)
  

  delete_filtered_records('idx_news', to_delete_id)