'''
Script to summarize a filing into an article
'''
import dotenv
dotenv.load_dotenv()

import os
import tiktoken
import json
from llama_index.llms.groq import Groq


# Model Creation
llm = Groq(
    model="llama3-70b-8192",
    api_key=os.getenv('GROQ_API_KEY'),
)

def count_tokens(text):
    enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = enc.encode(text)
    return len(tokens)

def summarize_llama(filings_text, category):
    prompt = {
        "body": ("Please analyze and summarize the following filing transaction into one paragraph with maximum 150 tokens, focusing on the key details such as the entities involved, the type of transaction, "
        "the change in ownership, the purpose of the transaction, and any potential implications or significance of this transaction:\n\n"
        f"\"{filings_text}\"\n\n"
        "Summary and Analysis:"),
        "title": ("Provide a one sentence title for the transaction filing. Use this structure: (Shareholder name) (Transaction type) Transaction of (Company in transaction) (if any, include who the buyer/seller is)."
        f"\"{filings_text}\"\n\n"
        "Title is (without quotation marks):")
        }
    
    output = str(llm.complete(prompt[category])).split('\n')[-1]

    return output

def summarize_filing(data):
    news_text = {
            "amount_transaction": data['amount_transaction'],
            "holder_type": data['holder_type'],
            "holding_after": data['holding_after'],
            "holding_before": data['holding_before'],
            "sector": data['sector'],
            "sub_sector": data['sub_sector'],
            "timestamp": data['timestamp'],
            "title": data['title'],
            "transaction_type": data['transaction_type'],
            "purpose": data['purpose'] if data.get('purpose') else "",
            "transactions": data['price_transaction']
        }

    news_text = json.dumps(news_text, indent = 2)

    # print(news_text, count_tokens(news_text))
    summary = summarize_llama(news_text, "body")
    # print(summary)
    title = summarize_llama(news_text, "title")

    return title, summary