'''
Script to summarize a filing into an article
'''
import dotenv
from pydantic import BaseModel
dotenv.load_dotenv()

import os
import tiktoken
import json
from llama_index.llms.groq import Groq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.chat_models import init_chat_model

llm = init_chat_model("llama3-70b-8192", model_provider="groq")

# Model Creation
# llm = Groq(
#     model="llama3-70b-8192",
#     api_key=os.getenv('GROQ_API_KEY'),
# )

def count_tokens(text):
    enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = enc.encode(text)
    return len(tokens)

class FilingsOutput(BaseModel):
    title: str
    body: str

def summarize_llama(filings_text):
    
    parser = JsonOutputParser(pydantic_object=FilingsOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a financial analyst. Provide direct, concise summaries without any additional commentary or prefixes. Output must be in JSON format with 'title' and 'body' fields."),
        ("user", """Analyze this filing transaction and provide:
        1. A title following this structure: (Shareholder name) (Transaction type) Transaction of (Company) (buyer/seller if applicable)
        2. A one-paragraph summary (max 150 tokens) focusing on: entities involved, transaction type, ownership changes, purpose, and significance

        Filing: {text}
        {format_instructions}""")
    ])

    chain = prompt | llm | parser

    response = chain.invoke({
        "text": filings_text,
        "format_instructions": parser.get_format_instructions()
    })

    return response

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
    response = summarize_llama(news_text)

    return response["title"], response["body"]