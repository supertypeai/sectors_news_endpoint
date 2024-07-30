from openai import OpenAI
import os
import dotenv
import re
from nltk.tokenize import sent_tokenize, word_tokenize
import nltk
import tiktoken
from goose3 import Goose

# NLTK download
# nltk.download('punkt')
nltk.data.path.append('./nltk_data')

dotenv.load_dotenv()

# Model Creation
client = OpenAI(
  api_key=os.getenv('OPENAI_API_KEY'),  
)

def count_tokens(text):
    enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = enc.encode(text)
    return len(tokens)

def summarize_ai(news_text, category):
    prompt = {
        "body": "Provide a concise, easily readable, maximum 2 sentences 150 tokens summary of the news article, highlighting the main points, key events, and any significant outcomes that focuses on financial metrics, excluding unnecessary details, filtering noises in article. Do not start with 'summary:' or 'in summary' etc.",
        "title": "Provide a one sentence title for the news article, that is not misleading and should give a general understanding of the article. (Give title without quotation mark)"}

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes the news articles to be displayed for stock traders."},
            {"role": "user", "content": prompt[category] + "\n\nNews: " + news_text}
        ],
        max_tokens=150
    )
    return response.choices[0].message.content

def preprocess_text(news_text):
    # Remove parenthesis
    news_text = re.sub(r'\(.*?\)', '', news_text)

    # Tokenize into sentences
    sentences = sent_tokenize(news_text)
    
    # Tokenize into words, remove stopwords, and convert to lowercase
    stop_words = {'a', 'an', 'the', 'with', 'of', 'to', 'and', 'in', 'on', 'for', 'as', 'by'}
    words = [word_tokenize(sentence) for sentence in sentences]
    words = [[word.lower() for word in sentence if word.lower() not in stop_words] for sentence in words]
    
    # Combine words back into sentences
    processed_sentences = [' '.join(sentence) for sentence in words]
    
    # Combine sentences back into a single string
    processed_text = ' '.join(processed_sentences)

    # Remove spaces before punctuation
    processed_text = re.sub(r'\s+([?.!,"])', r'\1', processed_text)
    # Remove multiple spaces
    processed_text = re.sub(r'\s+', ' ', processed_text)
    
    return processed_text

def get_article_body(url):
    try:
        g = Goose()
        article = g.extract(url=url)
        return article.cleaned_text
    except Exception as e:
        print(f"Goose3 failed with error: {e}")
        return ""

def summarize_news(url):
    news_text = get_article_body(url)
    if len(news_text) > 0:
        news_text = preprocess_text(news_text)
        summary = summarize_ai(news_text, "body")
        title = summarize_ai(news_text, "title")

        return title, summary
    else:
        return "", ""
    
# urls = [
#     "https://www.idnfinancials.com/news/50366/boosting-growth-tpma-acquires-worth-us",
#     "https://www.idnfinancials.com/news/50438/consistent-profit-dividend-ptba-rakes-indeks-categories",
#     "https://www.idnfinancials.com/news/50433/smdr-listed-dividend-category-indeks-tempo-idnfinancials",
#     "https://www.idnfinancials.com/news/50431/declining-market-cap-sido-listed-categories-indeks"
# ]

# for url in urls:
#     title, body = summarize_news(url)
#     print(title)
#     print(body)