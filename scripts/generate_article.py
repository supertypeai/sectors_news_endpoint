'''
Script to generate an article from pdf reader for filings
'''
import json
from datetime import datetime

from model.price_transaction import PriceTransaction
from scripts.classifier import get_sentiment_chat, get_tags_chat
from scripts.summary_filings import summarize_filing
import re

with open('./data/sectors_data.json', 'r') as f:
    sectors_data = json.load(f)
    
def extract_datetime(text):
  # Define the regex pattern to match the date and time
  pattern = r'\d{2}-\d{2}-\d{4} \d{2}:\d{2}(?::\d{2})?'
  
  # Search for the pattern in the string
  match = re.search(pattern, text)
  
  # If a match is found, return it
  if match:
      return match.group(0)
  return ""
  
def extract_number(input_string):
  """
  Extracts the numeric part from the input string.

  @param input_string String containing the number and other characters.

  @return Integer representing the extracted number.
  """
  match = re.search(r'\d+', input_string.replace('.', ''))
  return int(match.group()) if match else None


def extract_info(text):
  lines = text.split('\n')
  article_info = {
    "document_number": "",
    "company_name": "",
    "holder_name": "",
    "ticker": "",
    "category": "",
    "control_status": "",
    "transactions": [],
    "shareholding_before": "",
    "shareholding_after": "",
    "share_percentage_before": "",
    "share_percentage_after": "",
    "share_percentage_transaction": "",
    "purpose": "",
    "date_time": "",
    "price": 0,
    "price_transaction": {
      "prices": [],
      "amount_transacted": []
    }
  }

  for i, line in enumerate(lines):
    if "Nomor Surat" in line:
      article_info["document_number"] = lines[i-1]
    if "Nama Perusahaan" in line:
      article_info["company_name"] = lines[i-1]
    if "Nama Pemegang Saham" in line:
      article_info["holder_name"] = ' '.join(line.split()[3:])
    if "Kode Emiten" in line:
      article_info["ticker"] = lines[i-1]
    if "Kategori" in line:
      article_info["category"] = ' '.join(line.split()[1:])
    if "Status Pengedali" in line or "Status Pengendali" in line:
      article_info["control_status"] = ' '.join(line.split()[2:])
    if "Jumlah Saham Sebelum Transaksi" in line:
      article_info["shareholding_before"] = line.split()[-1]
    if "Jumlah Saham Setelah Transaksi" in line:
      article_info["shareholding_after"] = line.split()[-1]
    if "Persentase Saham Sebelum Transaksi" in line:
      article_info["share_percentage_before"] = line.split()[-1]
    if "Persentase Saham Sesudah Transaksi" in line:
      article_info["share_percentage_after"] = line.split()[-1]
    if "Persentase Saham yang ditransaksi" in line:
      article_info["share_percentage_transaction"] = line.split()[-1]
    if "Tujuan Transaksi" in line:
      article_info["purpose"] = " ".join(line.split()[2:])
    if "Tanggal dan Waktu" in line or "Date and Time" in line:
      date_time_str = ' '.join(line.split()[3:])
      date_time_str = extract_datetime(date_time_str)
      print(date_time_str)
      try:
        parsed_date = datetime.strptime(date_time_str, "%Y %d %m")
        formatted_date = parsed_date.strftime("%Y-%m-%d")
        article_info["date_time"] = formatted_date
      except ValueError:
        article_info["date_time"] = date_time_str
    if "Jenis Transaksi Harga Transaksi" in line:
      # Get the price of the transaction
      article_info["price"] = extract_number(lines[i+2].split(" ")[1])
      # Get all the price and number of transacted shares
      price_transaction = []
      amount_transacted = []
      for j in range(i+2, len(lines)):
        if not (lines[j].split(" ")[0] == "Pembelian" or lines[j].split(" ")[0] == "Penjualan"):
          break
        price_transaction.append(extract_number(lines[j].split(" ")[1]))
        amount_transacted.append(extract_number(lines[j].split(" ")[5]))
      article_info["price_transaction"]["prices"] = price_transaction
      article_info["price_transaction"]["amount_transacted"] = amount_transacted
  return article_info

def generate_article_filings(pdf_url, sub_sector, holder_type, data, uid=None):
  # Handle for POST pdf
  article = {
    "title": "",
    "body": "",
    "source": pdf_url,
    "timestamp": "",
    "sub_sector": sub_sector,
    "sector": sectors_data[sub_sector] if sub_sector in sectors_data.keys() else "",
    "tags": ["insider-trading"],
    "tickers": [],
    "transaction_type": '',
    "holder_type": holder_type,
    "holding_before": 0,
    "holding_after": 0,
    "share_percentage_before": 0,
    "share_percentage_after": 0,
    "share_percentage_transaction": 0,
    "amount_transaction": 0,
    "holder_name": "",
    "purpose": "",
    "price": 0,
    "transaction_value": 0,
    "price_transaction": {
      "prices": [],
      "amount_transacted": []
    },
    "UID": uid
  }

  pdf_text = data

  article_info = extract_info(pdf_text)
  print(article_info)


  article['title'] = f"Informasi insider trading {article_info['holder_name']} dalam {article_info['company_name']}"
  article['body'] = f"{article_info['document_number']} - {article_info['date_time']} - Kategori {article_info['category']} - Transaksi {article_info['holder_name']} dalam saham {article_info['company_name']} berubah dari {article_info['shareholding_before']} menjadi {article_info['shareholding_after']}"
  article['tickers'] = [article_info['ticker'].upper() + ".JK"]
  article['timestamp'] = article_info['date_time'] + ":00"
  article['timestamp']  = datetime.strptime(article['timestamp'], "%d-%m-%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
  article['holding_before'] = int("".join(article_info['shareholding_before'].split(".")))
  article['holding_after'] = int("".join(article_info['shareholding_after'].split(".")))
  article['share_percentage_before'] = float(article_info['share_percentage_before'].replace(",", ".").replace("%", "")) if len(article_info['share_percentage_before']) > 0 else 0.0
  article['share_percentage_after'] = float(article_info['share_percentage_after'].replace(",", ".").replace("%", "")) if len(article_info['share_percentage_after']) > 0 else 0.0
  article['share_percentage_transaction'] = float(article_info['share_percentage_transaction'].replace(",", ".").replace("%", ""))
  article['transaction_type'] = ('buy' if article['holding_before'] < article['holding_after'] else 'sell')
  article['amount_transaction'] = abs(article['holding_before'] - article['holding_after'])
  article['holder_name'] = article_info['holder_name']
  article['purpose'] = article_info['purpose']
  article['price_transaction'] = article_info['price_transaction']
  
  price_transaction = PriceTransaction(amount_transacted=article['price_transaction']['amount_transacted'], prices=article['price_transaction']['prices'])
  article['price'], article['transaction_value'] = price_transaction.get_price_transaction_value()
  

  # print(f"[ORIGINAL FILINGS ARTICLE]")
  # for key, value in article.items():
  #   print(f"{key}: {value}")
  new_title, new_body = summarize_filing(article)

  if len(new_body) > 0:
      article['body'] = new_body
      tags = get_tags_chat(new_body)
      sentiment = get_sentiment_chat(new_body)
      tags.append(sentiment[0])
      tags.append(article['tags'][0])
      article['tags'] = tags
  
  if len(new_title) > 0:
      article['title'] = new_title
  # print(f"[GENERATED FILINGS ARTICLE]")
  # for key, value in article.items():
  #   print(f"{key}: {value}")
  
  # with open('./generated.json', 'w') as f:
  #   json.dump(article, f, indent=2)
    
  if "purpose" in article:
    del article["purpose"]
  return article

def get_first_word(s):
    for i in range(1, len(s)):
        if s[i].isupper():
            return s[:i]
    return s