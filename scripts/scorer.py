'''
Script to generate the score of article
'''
import dotenv

dotenv.load_dotenv()

import os
from llama_index.llms.groq import Groq

llm = Groq(
    model="llama3-70b-8192",
    api_key=os.getenv("GROQ_API_KEY"),
)

criteria = '''
News Article Scoring Criteria (0-100)

1. Timeliness (0-10):
   - Is the article recent and relevant to current market conditions?
   - Score: 0 (Outdated) to 10 (Very timely and relevant).

2. Source Credibility (0-10):
   - Is the article from a reliable and authoritative source?
   - Score: 0 (Unverified/unknown source) to 10 (Top-tier, highly credible source).

3. Clarity and Structure (0-10):
   - Is the article well-organized with a clear headline, lead, and body?
   - Score: 0 (Disorganized and unclear) to 10 (Well-structured and easy to read).

4. Relevance to the Indonesia Stock Market (0-10):
   - Does the article focus on topics or events directly affecting the IDX or listed companies?
   - Score: 0 (Unrelated) to 10 (Directly related to key market drivers, sectors, or companies).

5. Depth of Analysis (0-10):
   - Does the article provide detailed insights, analysis, and data to support its points?
   - Score: 0 (Superficial coverage) to 10 (Comprehensive analysis with relevant data and expert opinions).

6. Financial Data Inclusion (0-10):
   - Does the article include relevant financial data such as earnings, stock prices, or ratios?
   - Score: 0 (No financial data) to 10 (Rich in financial details and metrics).

7. Balanced Reporting (0-10):
   - Does the article present multiple perspectives or both positive and negative aspects?
   - Score: 0 (Biased/one-sided) to 10 (Well-balanced, presenting various viewpoints).

8. Sector and Industry Focus (0-10):
   - Is the article specific to relevant sectors or industries within the Indonesian market?
   - Score: 0 (Vague sector focus) to 10 (Highly specific, focused on key sectors or industries).

9. Market Impact Relevance (0-10):
   - Does the article convey the potential impact of the news on the market, stock prices, or investor sentiment?
   - Score: 0 (No discussion of market impact) to 10 (Strong focus on market movements and investor decisions).

10. Forward-Looking Statements (0-10):
    - Does the article offer insights into future expectations, trends, or strategic moves?
    - Score: 0 (No discussion of future outlook) to 10 (Well-informed projections and strategic insights).

Bonus Criteria for High-Quality News (Additional Points)

1. Primary CTA (Up to 5 Points Each):
   - Does the article mention any of the following?
     - Dividend rate + cum date (+5 points)
     - Policy/Bill Passing (especially if it’s eyeball-catching) (+5 points)
     - Insider trading (especially if it’s eyeball-catching) (+5 points)
     - Acquisition/Merging (+5 points)
     - Launching of a new company business plan (new project/income source/new partner/new contract) (+5 points)
     - Earnings Report (+5 points)

2. Secondary CTA (Up to 2 Points Each):
   - Does the article mention any of the following?
     - IDX performance against the US market (+2 points)
     - Rupiah performance (+2 points)
     - Net foreign buy and sell (+2 points)
     - Recommended stocks (stock watchlist) (+2 points)
     - Global commodities prices (+2 points)

Total Score:

- Base Score: Up to 100 points based on the 10 main criteria.
- Bonus Score: Additional points based on Primary and Secondary CTA criteria.
'''

def get_article_score(body):
  
  prompt = f"""Given the scoring criteria of a news article with relevance to the Indonesia Stock Market. 
  {criteria} 
  
  Give the following article a score
  {body}
  
  Answer only with the score, example: 75"""

  outputs = llm.complete(prompt)

  return outputs

print(get_article_score("Thai investor Siam Kraft Industry Company Limited acquired 55.24% ownership of PT Fajar Surya Wisesa Tbk, purchasing over 1.36 billion shares, while other investors made notable transactions, including Low Tuck Kwong increasing his stake in PT Bayan Resources Tbk to 62.15%. Meanwhile, foreign investor Chemical Asia Corporation Pte Ltd reduced its shares in PT Victoria Investama Tbk, and other investors sold shares in various companies, including PT Platinum Wahab Nusantara Tbk and PT Sinar Mas Multiartha Tbk."))