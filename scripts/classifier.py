'''
Script to classify the tags, subsector, tickers, and sentiment of the news aarticle
'''
import dotenv

from model.llm_collection import LLMCollection

dotenv.load_dotenv()

import json
from supabase import create_client, Client
import os
from datetime import datetime
from openai import OpenAI
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import string

from sklearn.metrics.pairwise import cosine_similarity

# OPTIONS
SUBSECTOR_LOAD = True
TAG_LOAD = True

# PREPARATION
nltk.data.path.append("./nltk_data")

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), SUPABASE_KEY)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)

llmcollection = LLMCollection()

# DATA LOADING
# Subsectors data
# @Private method
def load_subsector_data():
    if datetime.today().day in [1, 15]:
        response = (
            supabase.table("idx_subsector_metadata")
            .select("slug, description")
            .execute()
        )

        subsectors = {}

        for row in response.data:
            subsectors[row["slug"]] = row["description"]
        with open("./data/subsectors_data.json", "w") as f:
            f.write(json.dumps(subsectors))

        return subsectors
    else:
        with open("./data/subsectors_data.json", "r") as f:
            subsectors = json.load(f)
        return subsectors


# Tags data
# @Private method
def load_tag_data():
    # This tags is optimized for indonesia financial market
    tags = [
        # Economy
        "Inflation",
        "Recession",
        "Interest Rates",
        # Stock indexes
        "IDX30",
        "JII70",
        "LQ45",
        "SRIKEHATI",
        # Stock Market
        "IDX Composite",
        "Market Trends",
        "Market Sentiment",
        "IDX",
        "Bonds",
        "Debt",
        "Fintech",
        # Commodities
        "Energy Commodities",
        "Palm Oil",
        "Grains",
        "Timber",
        "Fertilizers",
        "Metals and Minerals",
        "Gold",
        # Company News
        "Earnings Report",
        "Mergers & Acquisitions",
        "IPO",
        "Stock Splits",
        "Dividends",
        "Executive Changes",
        "Buyback",
        # Market Analysis
        "Indicators",
        "Market Analysis",
        "Valuation",
        "Financial Ratios",
        "Balance Sheets",
        "Bullish",
        "Bearish",
        "Short Selling",
        # Events and Reports
        "Economic Reports",
        "Retail Sales",
        "Product Launch",
        "Conferences",
        # Investor Insights
        "Analyst Ratings",
        # Miscellaneous
        "ESG",
        "Clean Energy",
        "Sharia Economy",
        "Foreign Investor",
        # Technology Trends
        "Artificial Intelligence",
        "Blockchain",
    ]
    return tags


# Ticker and Company name data, renew in date 1, 15 from supabase
# @Private method
def load_company_data():
    if datetime.today().day in [1, 15]:
        response = (
            supabase.table("idx_company_report")
            .select("symbol, company_name, sub_sector")
            .execute()
        )

        company = {}

        for row in response.data:
            company[row["symbol"]] = {
                "symbol": row["symbol"],
                "name": row["company_name"],
                "sub_sector": row["sub_sector"],
            }

        # with open("./data/companies.json", "w") as f:
        #     f.write(json.dumps(company))
            
        # with open('./data/companies.json', 'r') as f:
        #     data = json.load(f)
        
        for i, attr in enumerate(company):
            company[attr]['sub_sector'] = company[attr]['sub_sector'].replace('&', '').replace(',', '').replace('  ', ' ').replace(' ', '-').lower()
            
        with open('./data/companies.json', 'w') as f:
            json.dump(company, f, indent=2)
            
        return company
    else:
        with open("./data/companies.json", "r") as f:
            company = json.loads(f.read())
        return company


# CLASSIFICATION

# Function to prompt using Groq's llama 3 model
# @Private method
def classify_llama(body, category):
    # Load data
    tags = load_tag_data()
    company = load_company_data()
    subsectors = load_subsector_data()

    # Prompts
    tags_prompt = f"""
    This is a list of available tags: {', '.join(tag for tag in tags)}
    ONLY USE TAGS THAT ARE MENTIONED HERE, DO NOT ADD TAGS THAT ARE NOT SPECIFIED.
    
    Identify AT MOST 5 most relevant tags based on the available tags that previously defined.
    It does not have to be 5 tags, it can be 1 tag, 2 tag, 3 tag, or 4 tag depending on ACTUAL RELEVANCE of the tags
    
    Only answer in the format: 'tag1, tag2, etc' and nothing else. 
    
    For `IPO` tag, only use for UPCOMING IPO, do not use for news that mention IPO in the past.
    Use `IDX` for news related to indonesia stock exchange or bursa efek indonesia
    Use `IDX Composite` for news that related to PRICE of IDX or indeks harga saham gabungan
    Use `Sharia Economy` for news that also mention sharia/ syariah company
    
    Article content: {body}
    """
    
    subsector_prompt = f"""
    This is a list of available subsectors: {', '.join(subsector for subsector in subsectors.keys())}
    ONLY USE SUBSECTORS THAT ARE MENTIONED HERE, DO NOT ADD SUBSECTORS THAT ARE NOT SPECIFIED.
    
    Identify the subsector of the article.
    Only answer in the format: 'subsector-name' and nothing else
    
    Article content: {body}.
    """

    prompt = {
        "tags": tags_prompt,
        "tickers": f"Tickers: {', '.join(ticker for ticker in company.keys())} and article: {body}. Identify all the tickers in the article, only answer in the format 'ticker1, ticker2, etc' and nothing else.",
        "subsectors": subsector_prompt,
        "sentiment": f"Classify the sentiment ('bullish', 'bearish', 'neutral') of the article according to the context (actionable by Indonesia's stock investor). Article: {body}. Answer in one word (bullish or bearish or neutral)."
    }

    # Prompt the LLM
    for llm in llmcollection.get_llms():
        try:
            outputs = llm.complete(prompt[category])
            # Clean output
            outputs = str(outputs).split(",")
            outputs = [out.strip() for out in outputs if out.strip()]

            # Filter output
            if category == "tags":
                outputs = [e for e in outputs if e in tags]
                
            print(category, outputs)
            return outputs
        except Exception as e:
            print(f"[ERROR] LLM failed with error: {e}")
    return ""

# Identify the companies in the article
# @Private method
def identify_company_names(body):
    # print(body)
    prompt_name = f"""Identify all the company names mentioned in the following article:
    {body}
    
    For each company, for example PT. Antara Business Service (ABS), write it as 'Antara Business Service'
    
    Answer in the format: 
    
    Company A, Company B, Company C, Company D, etc
    
    Say nothing else. (Do not add intro)"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that indentifies companies mentioned in a news article.",
            },
            {"role": "user", "content": prompt_name},
        ],
        max_tokens=150,
        temperature=0.5,
        stop=None,
        n=1,
    )

    company_names = response.choices[0].message.content.strip().split(",")
    # print("company names openai", company_names)
    company_names_list = [name.strip() for name in company_names if name.strip()]
    # print("company names list", company_names_list)
    
    for llm in llmcollection.get_llms():
        try:
            company_names = str(llm.complete(prompt_name)).split(",")
        except Exception as e:
            print(f"[ERROR] LLM failed: {e}")
    # print("company names groq", company_names)
    for name in company_names:
        if name not in company_names_list:
            company_names_list.append(name)
    print("final list", company_names_list)
    return company_names_list


# @Private method
def match_ticker_codes(company_names, company_data):
    matched_tickers = []
    for name in company_names:
        for ticker, info in company_data.items():
            if name.lower() in info["name"].lower() or name.lower() == ticker.split()[0].lower():
                if ticker not in matched_tickers:
                    matched_tickers.append(ticker)
    return matched_tickers


# @Private method
def preprocess_text(text):
    # Tokenize the text into words
    tokens = word_tokenize(text)

    # Convert to lowercase
    tokens = [word.lower() for word in tokens]

    # Remove punctuation
    table = str.maketrans("", "", string.punctuation)
    tokens = [word.translate(table) for word in tokens]

    # Remove non-alphabetic tokens
    tokens = [word for word in tokens if word.isalpha()]

    # Remove stop words
    stop_words = set(stopwords.words("english"))
    tokens = [word for word in tokens if word not in stop_words]

    # Lemmatize the words
    lemmatizer = WordNetLemmatizer()
    tokens = [lemmatizer.lemmatize(word) for word in tokens]

    # Join the tokens back into a single string
    processed_text = " ".join(tokens)

    return processed_text


# @Private method
def get_embedding(text):
    response = client.embeddings.create(model="text-embedding-ada-002", input=text)
    return response.data[0].embedding


# EMBEDDINGS LOAD
def load_subsector_embeddings():
    if SUBSECTOR_LOAD:
        with open("./data/subsector_embeddings.json", "r") as f:
            subsector_embeddings = json.load(f)
    else:
        subsectors = load_subsector_data()
        subsector_embeddings = {
            subsector: get_embedding(description)
            for subsector, description in subsectors.items()
        }
        with open("./data/subsector_embeddings.json", "w") as f:
            json.dump(subsector_embeddings, f)
    return subsector_embeddings


def load_tag_embeddings():
    if TAG_LOAD:
        with open("./data/tag_embeddings.json", "r") as f:
            tag_embeddings = json.load(f)
    else:
        # RENEW IF TAGS CHANGE
        tags = load_tag_data()
        tag_embeddings = {tag: get_embedding(tag) for tag in tags}
        with open("./data/tag_embeddings.json", "w") as f:
            json.dump(tag_embeddings, f)
    return tag_embeddings


# @Public method
def get_tickers(text):
    company_names = identify_company_names(text)
    company = load_company_data()
    return match_ticker_codes(company_names, company)


# @Public method
def get_tags_chat(text, preprocess=True):

    if preprocess:
        text = preprocess_text(text)

    # return classify_ai(text, "tags")
    return classify_llama(text, "tags")


# @Public method
def get_subsector_chat(text):
    text = preprocess_text(text)
    # return classify_ai(text, "subsectors")
    return classify_llama(text, "subsectors")


# @Public method
def get_sentiment_chat(text):
    text = preprocess_text(text)

    # return classify_ai(text, "sentiment")
    return classify_llama(text, "sentiment")


# @Public method
def get_tags_embeddings(text):
    text = preprocess_text(text)
    article_embedding = get_embedding(text)
    tag_embeddings = load_tag_embeddings()

    similarities = {
        tag: cosine_similarity([article_embedding], [embedding])[0][0]
        for tag, embedding in tag_embeddings.items()
    }

    top_5_tags = sorted(similarities, key=similarities.get, reverse=True)[:5]

    return top_5_tags


# @Public method
def get_subsector_embeddings(text):
    text = preprocess_text(text)
    article_embedding = get_embedding(text)
    subsector_embeddings = load_subsector_embeddings()

    similarities_subsector = {
        subsector: cosine_similarity([article_embedding], [embedding])[0][0]
        for subsector, embedding in subsector_embeddings.items()
    }

    most_relevant_subsector = max(
        similarities_subsector, key=similarities_subsector.get
    )

    return most_relevant_subsector

# @Public method
def predict_dimension(title: str, article: str):
    prompt = f"""
    This is a list of news classification: valuation, future, technical, financials, dividend, management, ownership, sustainability

    valuation -> Article must contain specific numeric impacts on company valuation metrics (P/E, EBITDA, etc.) or include events that directly affect company market capitalization by at least 2% in a single trading day.
    future -> Article should contain forward-looking statements with specific timelines or numeric projections, official company guidance updates, or analyst revisions that change growth/earnings estimates by at least 5%.
    technical -> News must result in abnormal trading volume (2x average) or price movement (±3% in a single session) with clear technical pattern implications or breakthrough of significant support/resistance levels.
    financials -> Article must discuss changes in financial metrics exceeding 5% year-over-year, unexpected earnings/revenue results, or material changes to the company's financial structure (debt, equity, assets).
    dividend -> News must relate to dividend policy changes, actual dividend announcements, changes in payout ratios exceeding 3%, or events directly impacting dividend sustainability (cash flow, earnings coverage).
    management -> Article must cover C-suite or board member changes, significant insider trading activity (>$1M), or major changes in executive compensation/corporate governance policies.
    ownership -> News must report ownership changes exceeding 1% of outstanding shares, significant institutional investor actions, or material changes in short interest (>20% change).
    sustainability -> Article must discuss quantifiable ESG impacts, formal sustainability initiative launches with specific goals, or changes in ESG ratings from major rating agencies.

    Article title: {title}
    Article content: {article}

    the value of classification is 0, 1, 2. 0 for not related, 1 for slightly related, 2 for highly related
    if the news mention about company financial sustainability, make the sustainability dimension value 0
    if the news mention about total amount of dividend or there is other classification that highly related, make the dividend dimension value 0
    
    answer in format:
    valuation: value
    peers: value
    ... etc

    do not add anything else
    """

    result = {
                "valuation": None,
                "future": None,
                "technical": None,
                "financials": None,
                "dividend": None,
                "management": None,
                "ownership": None,
                "sustainability": None,
            }
    for llm in llmcollection.get_llms():
        try:
            outputs = llm.complete(prompt)

            result = {
                "valuation": None,
                "future": None,
                "technical": None,
                "financials": None,
                "dividend": None,
                "management": None,
                "ownership": None,
                "sustainability": None,
            }

            for line in outputs.text.splitlines():
                item = line.split(":")
                key = item[0].strip()
                try:
                    value = int(item[1])

                    if key in result:
                        result[key] = value
                except:
                    pass

            return result
        except Exception as e:
            print(f"[ERROR] LLM failed with error: {e}")
    return result


# body = ["GoTo, a merger between Gojek and Tokopedia, has absorbed nearly 80% of its IPO funds, amounting to Rp10.76 trillion by the end of June 2024. The company has generated a net proceeds of Rp13.5 trillion during its IPO in 2022, leaving Rp2.81 trillion remaining for operational and strategic purposes, including investments in companies like Gopay and Velox Digital.",
# "PT. Bank Raya Indonesia Tbk has scheduled a share buyback with a budget of IDR 20 billion, pending approval from shareholders on August 21, 2024, aiming to increase employee engagement in the company without affecting business operations. The buyback will be funded from internal cash, and the number of shares to be repurchased has not been disclosed, projected to be below 10% of the issued paid-up capital.",
# "PT Bank Syariah Indonesia (BSI) has made it to the top 5 state-owned enterprises with the largest market capitalization in Indonesia, reaching Rp116 trillion in July 2024. BSI's success is attributed to its inclusive, modern, and digital approach, with positive financial performance including distributing Rp855.56 billion cash dividends in 2023 and achieving a Rp1.71 trillion profit in Q1 2024 driven by robust growth in third-party funds and mobile banking transactions.",
# "Hary Tanoesoedibjo has rescued MNC Asia Holding by acquiring 26 million shares at Rp50 each, investing a total of Rp1.3 billion. Following the purchase, Tanoesoedibjo's portfolio now holds 2.59 billion shares, a 3.1% increase from before the transaction.",
# "Stocks in LQ45 index like UNVR, MBMA, and SIDO dropped as the market rose. UNVR closed at Rp 2,800, down by 2.10%, with a total transaction value of Rp 43.30 billion and a P/E ratio of 18.82x. Similarly, MBMA saw a 2.29% decline, closing at Rp 640, and SIDO ended at Rp 725 per share, down by 2.03%."]

# for text in body:
#   print("TEXT:")
#   print(text)
#   print("CLASSIFIED TICKERS:")
#   print(get_tickers(text))
#   print("CLASSIFIED TAGS METHOD 1")
#   print(get_tags_chat(text))
#   print("CLASSIFIED SUBSECTOR METHOD 1")
#   print(get_subsector_chat(text))
#   # print("CLASSIFIED TAGS METHOD 2")
#   # print(get_tags_embeddings(text))
#   # print("CLASSIFIED SUBSECTOR METHOD 2")
#   # print(get_subsector_embeddings(text))
#   print("CLASSIFIED SENTIMENT")
#   print(get_sentiment_chat(text))
#   print("")

# Result
# Tickers belum konsisten
# tags method 1 kadang beda, method 2 selalu sama
# subsectors selalu sama di setiap method, walau antar method beda
# sentiment konsisten
