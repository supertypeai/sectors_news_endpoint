'''
Script to extract the title and body metadata from a news article page
'''
import ssl
import dotenv
import os
import urllib.request
from bs4 import BeautifulSoup
import requests
from requests.exceptions import RequestException

dotenv.load_dotenv()

ssl._create_default_https_context = ssl._create_unverified_context

def fetch(url):
  proxy = os.environ.get("PROXY_KEY")

  proxy_support = {'http': proxy,'https': proxy}

  try:
    response = requests.get(url, proxies=proxy_support, verify=False)
    response.raise_for_status()
    return response.text
  except RequestException as e:
    print(f"Error fetching URL {url}: {e}")
    return None

def extract_metadata(url):
  data = fetch(url)
  soup = BeautifulSoup(data, 'html.parser')

  og_title = soup.find('meta', property='og:title')
  og_description = soup.find('meta', property='og:description')

  title = og_title['content'] if og_title else 'No title found'
  body = og_description['content'] if og_description else 'No description found'

  if title == 'No title found':
    title = soup.find('title').text
  if body == 'No description found':
    body = soup.find('meta', {"name": "description"})['content']

  return title, body

# Example usage
# Have been tested (per 2 June 2024)
# IDN Financials, Detik, Tempo, CNBC, Okezone, Tribun, Liputan6, Antaranews, CNN, Kompas, Yahoo Finance, Whitecase. TradingView, MorningStar, Livemint, Financial Times

# Cannot be retrieved
# IDX
# url = "https://www.idnfinancials.com/news/50210/central-banks-complete-nexus-project-blueprint"
# url = "https://health.detik.com/berita-detikhealth/d-7418889/netizen-sebut-membungkuk-jadi-penyebab-kolapsnya-zhang-zhi-jie-benarkah"
# url = "https://www.ft.com/content/b19ea5ae-38a7-41ab-b2d8-2e694b06b5b1"

# title, body = extract_metadata(url)

# print("title", title)
# print("body", body)