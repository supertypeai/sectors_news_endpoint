import json

with open('./data/sectors_data.json', 'r') as f:
    sectors_data = json.load(f)

def extract_info(text):
  lines = text.split('\n')
  article_info = {
    "document_number": "",
    "company_name": "",
    "shareholder_name": "",
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
    elif "Nama Perusahaan" in line:
      article_info["company_name"] = lines[i-1]
    elif "Nama Pemegang Saham" in line:
      article_info["shareholder_name"] = ' '.join(line.split()[3:])
    elif "Kode Emiten" in line:
      article_info["ticker"] = lines[i-1]
    elif "Kategori" in line:
      article_info["category"] = ' '.join(line.split()[1:])
    elif "Status Pengedali" in line or "Status Pengendali" in line:
      article_info["control_status"] = ' '.join(line.split()[2:])
    elif "Jumlah Saham Sebelum Transaksi" in line:
      article_info["shareholding_before"] = line.split()[-1]
    elif "Jumlah Saham Setelah Transaksi" in line:
      article_info["shareholding_after"] = line.split()[-1]
    if "Tujuan Transaksi" in line:
      word = get_first_word(line.split()[2]).lower()
      article_info["purpose"] = word if word == 'investasi (penambahan aset)' or word == 'divestasi (pengurangan aset)' else 'lainnya'
    elif "Tanggal dan Waktu" in line or "Date and Time" in line:
      article_info["date_time"] = ' '.join(line.split()[3:])
  return article_info

def generate_article(pdf_url, sub_sector, data):
  # Handle for POST pdf
  article = {
    "title": "",
    "body": "",
    "source": pdf_url,
    "timestamp": "",
    "sub_sector": sub_sector,
    "sector": sectors_data[sub_sector],
    "tags": ["insider-trading"],
    "tickers": []
  }

  pdf_text = data

  article_info = extract_info(pdf_text)

  article['title'] = f"Informasi insider trading {article_info['shareholder_name']} dalam {article_info['company_name']}"
  article['body'] = f"{article_info['document_number']} - {article_info['date_time']} - Kategori {article_info['category']} - {article_info['shareholder_name']} dengan status kontrol {article_info['control_status']} dalam saham {article_info['company_name']} berubah dari {article_info['shareholding_before']} menjadi {article_info['shareholding_after']} dengan tujuan {article_info['purpose']}"
  article['tickers'] = [article_info['ticker']]
  article['timestamp'] = article_info['date_time'] + ":00"

  return article

def get_first_word(s):
    for i in range(1, len(s)):
        if s[i].isupper():
            return s[:i]
    return s