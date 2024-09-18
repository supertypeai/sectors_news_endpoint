'''
Script to generate an article from pdf reader for filings
'''
import json
from datetime import datetime

from scripts.classifier import get_sentiment_chat, get_tags_chat
from scripts.summary_filings import summarize_filing

with open('./data/sectors_data.json', 'r') as f:
    sectors_data = json.load(f)

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
    "purpose": "",
    "date_time": "",
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
    if "Tujuan Transaksi" in line:
      word = get_first_word(line.split()[2]).lower()
      article_info["purpose"] = word if word == 'investasi' or word == 'divestasi' else ''
      article_info["purpose"] += " (penambahan aset)" if word == 'investasi' else " (pengurangan aset)" if word == 'divestasi' else ""
    if "Tanggal dan Waktu" in line or "Date and Time" in line:
      date_time_str = ' '.join(line.split()[3:])
      try:
        parsed_date = datetime.strptime(date_time_str, "%Y %d %m")
        formatted_date = parsed_date.strftime("%Y-%m-%d")
        article_info["date_time"] = formatted_date
      except ValueError:
        article_info["date_time"] = date_time_str
  return article_info

def generate_article_filings(pdf_url, sub_sector, holder_type, data):
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
    "amount_transaction": 0,
    "holder_name": ""
  }

  pdf_text = data

  article_info = extract_info(pdf_text)

  article['title'] = f"Informasi insider trading {article_info['holder_name']} dalam {article_info['company_name']}"
  article['body'] = f"{article_info['document_number']} - {article_info['date_time']} - Kategori {article_info['category']} - {article_info['holder_name']} dengan status kontrol {article_info['control_status']} dalam saham {article_info['company_name']} berubah dari {article_info['shareholding_before']} menjadi {article_info['shareholding_after']}"
  article['tickers'] = [article_info['ticker'].upper() + ".JK"]
  article['timestamp'] = article_info['date_time'] + ":00"
  article['timestamp']  = datetime.strptime(article['timestamp'], "%d-%m-%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
  article['holding_before'] = int("".join(article_info['shareholding_before'].split(".")))
  article['holding_after'] = int("".join(article_info['shareholding_after'].split(".")))
  article['transaction_type'] = ('buy' if article['holding_before'] < article['holding_after'] else 'sell')
  article['amount_transaction'] = abs(article['holding_before'] - article['holding_after'])
  article['holder_name'] = article_info['holder_name']

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
  return article

def get_first_word(s):
    for i in range(1, len(s)):
        if s[i].isupper():
            return s[:i]
    return s