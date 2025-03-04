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
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import string


# OPTIONS
SUBSECTOR_LOAD = True
TAG_LOAD = True

# PREPARATION
nltk.data.path.append("./nltk_data")

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), SUPABASE_KEY)

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
    unique_tags = []

    with open('./data/unique_tags.json', 'r') as f:
        unique_tags = json.load(f)

    return unique_tags

# Ticker and Company name data, renew in date 1, 15 from supabase
# @Private method
def load_company_data():
    if datetime.today().day in [1, 15] or True:
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
    ### List of Available Tags:
    {', '.join(tag for tag in tags)}

    ONLY USE the tags listed above. DO NOT create, modify, or infer new tags that are not explicitly provided.

    ### **Tag Selection Rules:**
    - Identify **AT MOST** 5 relevant tags from the provided list.
    - The number of tags should be **based on actual relevance**, not forced to be 5.
    - If only **1, 2, 3, or 4 tags** are relevant, select accordingly.

    ### **Specific Tagging Instructions:**
    - **`IPO`** → Use **ONLY** for upcoming IPOs. DO NOT apply to past IPO mentions.
    - **`IDX`** → Use for news related to **Indonesia Stock Exchange (Bursa Efek Indonesia)**.
    - **`IDX Composite`** → Use **only** if the article discusses the **price or performance of IDX/Indeks Harga Saham Gabungan**.
    - **`Sharia Economy`** → Use if the article mentions **Sharia (Syariah) companies or economy**.

    ### **Response Format:**
    - Output the selected tags as a **comma-separated list** (e.g., `tag1, tag2, tag3`).
    - **Do NOT** include explanations, additional words, or formatting beyond the list.

    ---
    #### **Article Content:**
    {body}
    """
    
    ticker_prompt = f"""
    ### List of Available Tickers:
    {', '.join(ticker for ticker in company.keys())}

    ONLY USE the tickers listed above. DO NOT infer or create tickers that are not explicitly provided.

    ### **Ticker Extraction Rules:**
    - Identify **all tickers** present in the article.
    - If no tickers are found, return an **empty string ("")**.
    - **Do NOT** modify, infer, or abbreviate ticker symbols.

    ### **Response Format:**
    - Output the tickers as a **comma-separated list** (e.g., `TICKER1, TICKER2, TICKER3`).
    - If no tickers are found, return `""`.
    - **Do NOT** include explanations, additional words, or formatting beyond the ticker list.

    ---
    #### **Article Content:**
    {body}
    """
    
    subsector_prompt = f"""
    ### List of Available Subsectors:
    {', '.join(subsector for subsector in subsectors.keys())}

    ONLY USE the subsectors listed above. DO NOT create, modify, or infer new subsectors that are not explicitly provided.

    ### **Subsector Selection Rules:**
    - Identify **ONE** most relevant subsector based on the article content.
    - If multiple subsectors seem relevant, choose **the most specific and dominant** one.
    - If **no appropriate subsector applies, return an empty string ("")**.

    ### **Response Format:**
    - Output **only** the name of the selected subsector (e.g., `subsector-name`).
    - **Do NOT** include explanations, additional words, or formatting beyond the subsector name.

    ---
    #### **Article Content:**
    {body}
    """
    
    sentiment_prompt = f"""
    ### **Sentiment Classification (Bullish, Bearish, Neutral)**

    Classify the **sentiment** of the following article from the perspective of **Indonesia's stock investors**.

    ### **Sentiment Rules:**
    - Classify the article into one of **three** categories:
    - **"bullish"** → Indicates positive or optimistic sentiment toward stocks.
    - **"bearish"** → Indicates negative or pessimistic sentiment toward stocks.
    - **"neutral"** → Indicates a balanced or uncertain outlook.

    ### **Response Format:**
    - Output **ONLY** one word: `"bullish"`, `"bearish"`, or `"neutral"`.
    - **Do NOT** include explanations, additional words, or formatting.

    ---
    #### **Article Content:**
    {body}
        """

    prompt = {
        "tags": tags_prompt,
        "tickers": ticker_prompt,
        "subsectors": subsector_prompt,
        "sentiment": sentiment_prompt
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
                outputs = [e.lower() for e in outputs if e in tags]
                
            print(category, outputs)
            return outputs
        except Exception as e:
            print(f"[ERROR] LLM failed with error: {e}")
    return ""

# Identify the companies in the article
# @Private method
def identify_company_names(body):
    # print(body)
    prompt_name = f"""
    ### **Company Name Extraction**
    Identify all company names mentioned in the article.

    ### **Extraction Rules:**
    - Extract full company names without abbreviations.
    - If a company name includes **"PT."**, omit **"PT."** and return only the full company name.
    - If a company name includes **"Tbk"**, omit **"Tbk"** and return only the full company name.
    - Example: **PT. Antara Business Service Tbk (ABS)** → `"Antara Business Service"`
    - If no company names are found, return an **empty string ("")**.

    ### **Response Format:**
    - Output company names as a **comma-separated list** (e.g., `Company A, Company B, Company C`).
    - If no company names are found, return `""`.
    - **Do NOT** include explanations, additional words, or formatting.
    - **Do NOT** include string formats such as \\n or \\t.

    ---
    #### **Article Content:**
    {body}
    """

    # company_names = response.choices[0].message.content.strip().split(",")
    # # print("company names openai", company_names)
    # company_names_list = [name.strip() for name in company_names if name.strip()]
    # # print("company names list", company_names_list)
    
    company_names_list = []
    
    for llm in llmcollection.get_llms():
        try:
            company_names = str(llm.complete(prompt_name)).split(",")
        except Exception as e:
            print(f"[ERROR] LLM failed: {e}")
    # print("company names groq", company_names)
    for name in company_names:
        if name not in company_names_list:
            company_names_list.append(name.strip())
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
def predict_dimension(title: str, article: str):
    prompt = f"""
    ### **List of News Classifications:**
    valuation, future, technical, financials, dividend, management, ownership, sustainability

    ### **Classification Criteria:**
    - **valuation** → Must include **numeric impacts** on valuation metrics (**P/E, EBITDA, etc.**) or events causing **≥2% market cap change** in a **single trading day**.
    - **future** → Must contain **forward-looking statements** with **specific timelines**, numeric **projections**, **official company guidance**, or **analyst revisions** that **change growth/earnings estimates by ≥5%**.
    - **technical** → Must report **abnormal trading volume** (**≥2× average**) or **price movement (±3% in one session)** with **clear technical patterns** or **significant support/resistance breakthroughs**.
    - **financials** → Must discuss **financial metric changes** **≥5% year-over-year**, **unexpected earnings/revenue results**, or **material financial structure changes** (**debt, equity, assets**).
    - **dividend** → Must relate to **dividend policy changes**, **dividend announcements**, **payout ratio changes ≥3%**, or **events affecting dividend sustainability** (**cash flow, earnings coverage**).
    - **management** → Must cover **C-suite/board changes**, **significant insider trading (> $1M)**, or **major executive compensation/governance policy shifts**.
    - **ownership** → Must report **ownership changes exceeding 1% of outstanding shares**, **significant institutional investor actions**, or **material short interest changes (>20%)**.
    - **sustainability** → Must discuss **quantifiable ESG impacts**, **formal sustainability initiatives** with **specific goals**, or **ESG rating changes from major agencies**.

    ---
    ### **Classification Rules:**
    - **Assign a classification value (0, 1, 2) for each category:**
    - **0** → Not related.
    - **1** → Slightly related.
    - **2** → Highly related.

    - **Special Conditions:**
    - If the news mentions **company financial sustainability**, set **sustainability = 0**.
    - If the news mentions **total dividend amount** OR if another classification is **highly related**, set **dividend = 0**.

    ---
    ### **Response Format:**
    valuation: value 
    future: value 
    technical: value 
    financials: value 
    dividend: value 
    management: value 
    ownership: value 
    sustainability: value

    - **Do NOT** add explanations, extra words, or formatting beyond the structured response.

    ---
    ### **Article Details:**
    **Title:** {title}  
    **Content:** {article}
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
