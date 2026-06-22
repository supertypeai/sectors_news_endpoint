"""
Script to summarize a filing into an article.

Provides comprehensive summarization of financial filings with:
- Structured data extraction and processing
- LLM-based title and body generation
- Token counting and optimization
- Error handling and validation
"""

import json
import logging
import os
from typing import Dict, Any, Tuple, Optional

import dotenv
import tiktoken
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# Load environment variables
dotenv.load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class FilingsOutput(BaseModel):
    """Model for filing summarization output."""

    title: str = Field(description="Concise title for the filing summary")
    body: str = Field(description="Detailed body text for the filing summary")


class FilingSummarizer:
    """Enhanced filing summarizer with robust error handling and optimization."""

    def __init__(
        self, 
        model_name: str = "llama-3.3-70b-versatile", 
        model_provider: str = "groq",
        source: str = 'idx'
    ):
        """
        Initialize filing summarizer.

        Args:
            model_name (str): Name of the LLM model to use
            model_provider (str): Provider of the LLM model
        """
        try:
            self.llm = init_chat_model(model_name, model_provider=model_provider)
            logger.info(f"Initialized LLM: {model_name} from {model_provider}")
        
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise
        
        self.source = source 
        self.parser = JsonOutputParser(pydantic_object=FilingsOutput)
        self._prompt_template = self._create_prompt_template()
        self._prompt_sgx_template = self._create_prompt_sgx_template()

    def _create_prompt_template(self) -> ChatPromptTemplate:
        """Create the prompt template for filing summarization."""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You are a financial analyst. Provide direct, concise summaries without any additional commentary or prefixes. 
                    Output must be in JSON format with 'title' and 'body' fields.
                    Focus on accuracy, clarity, and relevance to Indonesian stock market investors.
                    """,
                ),
                (
                    "user",
                    """
                    Analyze this filing transaction and provide:
                    1. A title following this structure: 
                        - if transaction type is sell or buy:
                            (Shareholder name) (Transaction type) Shares of (Company)
                        - if transaction type is others: 
                            (Company) Shareholder (holder_name) Reports New Transaction

                    2. A one-paragraph summary (max 150 tokens) focusing on: entities involved, transaction type, ownership changes, purpose, and significance

                    Filing: {text}

                    Note: 
                        - CRITICAL: If the transaction type is classified as 'others', do NOT state "described as others" or mention the category name. 
                            Instead, describe the specific underlying action as the transaction type.
                        - Keep it factual, don't speculate.
                        - Currency: IDR.
                        - Use thousands separator with comma (e.g., 83,420,100) and use dot for decimal separator.
                        - If prices exist, show one representative price like "IDR 490 per share".
                        - If holdings_before/after exist, show the transition and delta if clear.
                    
                    Return with the following structure:
                    {format_instructions}
                    """,
                ),
            ]
        )

    def _create_prompt_sgx_template(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You are a financial news writer expert covering the Singapore stock market (SGX).
                    Your job is to write a concise, factual news entry for a Form insider filing transaction.
                    You will be given only the current filing data. Write solely based on what is provided.
                    Write in English. Be direct and specific. Do not use generic filler phrases.
                    """,
                ),
                (
                    "user",
                    """
                    Write a professional financial news entry for the following SGX insider filing transaction.

                    Current filing:
                    {text}

                    Title format. Use data from the current filing only:
                    - If transaction type is buy or sell:
                        (Holder name) (Transaction Type) Shares of (Company name)
                    - If transaction type is award:
                        (Holder name) Reports Share Award Distribution in (Company name)
                    - If transaction type is others:
                        (Company name) Insider (Holder name) Reports Shareholding Change

                    Body instructions:
                    - Maximum two to four sentences.
                    - Written from the perspective of a financial journalist covering SGX insider transactions.
                    - Lead with the most significant aspect of the transaction: size, ownership impact, or price.
                    - price_per_share and transaction_value may be null. When they are null, omit all monetary
                    figures entirely. Quantify using share count and ownership percentage before and after only.
                    Do not estimate, infer, or approximate a value.
                    - Quantify where possible given available fields: share count, transaction value if not null,
                    ownership percentage before and after, price per share if not null.
                    Do not enumerate individual transaction blocks.
                    - Do not restate the same fact twice in different phrasing.
                    - Currency: SGD. Comma as thousands separator. Dot for decimals.
                    - Ownership percentage fields are stored as decimals on a 0-1 scale. Multiply by 100 to
                    get the display percentage, then round to two decimal places
                    (e.g. 0.0699 displays as 6.99%, not 0.07%).
                    - If both the before and after display percentages are identical after rounding,
                    omit the percentage figures entirely and rely on share counts only.
                    - If transaction type is award, one sentence describing the share count change and
                    ownership impact is sufficient. Do not add interpretive statements about the
                    nature of the award beyond what the data explicitly states.
                    - If transaction type is others, identify and describe the specific corporate action
                    (e.g. rights issue, private placement, transfer) rather than labeling it as others.
                    - tags provides context labels for the nature of the transaction. Use these only to
                    inform the framing and word choice of the body — do not invent details not present
                    in the other fields.
                    - circumstances contains the filer's own free-text description of why the transaction
                    occurred. If present and not '-', use it to add specific context to the body. Quote or paraphrase it faithfully — do not
                    contradict or expand beyond what it states.
                    - Do not speculate. Do not editorialize. Do not use filler phrases like
                    "it is worth noting" or "this is significant because".
                    - Do not use informal shorthands like 'the buy' or 'the sell'.
                    Use 'the purchase', 'the acquisition', or 'the disposal' instead
                    - Do not reference the source document. Never use phrases like "According to the filing",
                    "The filing shows", "As per the disclosure", or any similar meta-references.
                    State facts directly as news.
                    
                    Ensure return in the following JSON format.
                    {format_instructions}
                    """,
                ),
            ]
        )
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text for optimization purposes.

        Args:
            text (str): Text to count tokens for

        Returns:
            int: Number of tokens
        """
        try:
            enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
            tokens = enc.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            # Fallback: rough estimation (1 token ≈ 4 characters)
            return len(text) // 4

    def summarize_llama(self, filings_text: str) -> Dict[str, str]:
        """
        Summarize filing text using LLM.

        Args:
            filings_text (str): Raw filing text to summarize

        Returns:
            Dict[str, str]: Dictionary containing 'title' and 'body'
        """
        if not filings_text or not filings_text.strip():
            logger.warning("Empty filing text provided")
            return {"title": "", "body": ""}

        try:
            logger.info(
                f"Summarizing filing ({self.count_tokens(filings_text)} tokens)"
            )

            prompt = self._prompt_template if self.source == 'idx' else self._prompt_sgx_template

            chain = prompt | self.llm | self.parser

            response = chain.invoke(
                {
                    "text": filings_text,
                    "format_instructions": self.parser.get_format_instructions(),
                }
            )

            # Validate response
            if not isinstance(response, dict):
                logger.error(f"Invalid response type: {type(response)}")
                return {"title": "", "body": ""}

            title = response.get("title", "").strip()
            body = response.get("body", "").strip()

            if not title or not body:
                logger.warning("Incomplete response from LLM")
                return {
                    "title": title or "Filing Summary",
                    "body": body or "Filing transaction processed.",
                }

            logger.info("Successfully generated filing summary")
            return {"title": title, "body": body}

        except Exception as e:
            logger.error(f"Error summarizing filing: {e}")
            return {
                "title": "Filing Summary",
                "body": "Error processing filing transaction.",
            }

    def summarize_filing(self, data: Dict[str, Any]) -> Tuple[str, str]:
        """
        Generate summary from structured filing data.

        Args:
            data (Dict[str, Any]): Structured filing data

        Returns:
            Tuple[str, str]: (title, body) summary
        """
        if not data or not isinstance(data, dict):
            logger.error("Invalid filing data provided")
            return "", ""

        try:
            # Extract and structure relevant data
            if self.source == 'idx':
                news_text = self._extract_filing_data(data)
            
            else: 
                news_text = data 

            news_text_json = json.dumps(news_text, indent=2)

            logger.debug(
                f"Structured filing data: {self.count_tokens(news_text_json)} tokens"
            )

            # Generate summary
            response = self.summarize_llama(news_text_json)

            return response["title"], response["body"]

        except Exception as e:
            logger.error(f"Error in summarize_filing: {e}")
            return "", ""

    def summarize_filing_manual(
        self,
        holder_name: str,
        company_name: str,
        tx_type: str,
        amount: Optional[int],
        holding_before: Optional[int],
        holding_after: Optional[int],
        purpose_en: str,
    ) -> tuple[str, str]:
        """
        Human-friendly title/body with minimal grammar rules.
        """
        action_title = tx_type.replace("-", " ")
        if tx_type == "buy":
            action_verb = "bought"
            title = f"{holder_name} buys shares of {company_name}"
        elif tx_type == "sell":
            action_verb = "sold"
            title = f"{holder_name} sells shares of {company_name}"
        elif tx_type == "share-transfer":
            action_verb = "transferred"
            title = f"{holder_name} transfers shares of {company_name}"
        elif tx_type == "award":
            action_verb = "was awarded"
            title = f"{holder_name} was awarded shares of {company_name}"
        elif tx_type == "inheritance":
            action_verb = "inherited"
            title = f"{holder_name} inherits shares of {company_name}"
        elif tx_type == "others": 
            action_verb = "executed a transaction for"
            title = f"Change in {holder_name}'s position in {company_name}"
        else:
            action_verb = "executed a transaction for"
            title = f"{holder_name} {action_title} transaction of {company_name}"

        amount_str = f"{amount:,} shares" if amount is not None else "shares"
        body = f"{holder_name} {action_verb} {amount_str} of {company_name}."

        if holding_before is not None and holding_after is not None:
            hb_str, ha_str = f"{holding_before:,}", f"{holding_after:,}"
            if holding_after > holding_before:
                body += f" This increases their holdings from {hb_str} to {ha_str} shares."
            elif holding_after < holding_before:
                body += f" This decreases their holdings from {hb_str} to {ha_str} shares."
            else:
                body += f" Their holdings remain at {ha_str} shares."

        if purpose_en:
            body += f" The stated purpose of the transaction was {purpose_en.lower()}."
        return title, body
    
    def _extract_filing_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant data from filing for summarization.

        Args:
            data (Dict[str, Any]): Raw filing data

        Returns:
            Dict[str, Any]: Structured data for summarization
        """
        return {
            "amount_transaction": data.get("amount_transaction", 0),
            "holder_type": data.get("holder_type", ""),
            "holding_after": data.get("holding_after", 0),
            "holding_before": data.get("holding_before", 0),
            "sector": data.get("sector", ""),
            "sub_sector": data.get("sub_sector", ""),
            "timestamp": data.get("timestamp", ""),
            "title": data.get("title", ""),
            "transaction_type": data.get("transaction_type", ""),
            "purpose": data.get("purpose", ""),
            "transactions": data.get("price_transaction", {}),
            "ticker": data.get("tickers", [""])[0] if data.get("tickers") else "",
            "company_name": self._extract_company_name(data.get("title", "")),
            "holder_name": data.get("holder_name", ""),
        }

    def _extract_company_name(self, title: str) -> str:
        """
        Extract company name from title.

        Args:
            title (str): Title containing company information

        Returns:
            str: Extracted company name
        """
        if not title:
            return ""

        # Look for patterns like "PT [Company Name]" or company names in title
        if "PT " in title:
            parts = title.split("PT ")[1].split(" ")
            # Take first few words as company name
            return "PT " + " ".join(parts[:3])

        return title


# Global instance for backward compatibility
_summarizer = FilingSummarizer()


# Backward compatible functions
def count_tokens(text: str) -> int:
    """
    Count tokens in text.

    This function maintains backward compatibility with existing code.
    """
    return _summarizer.count_tokens(text)


def summarize_llama(filings_text: str) -> Dict[str, str]:
    """
    Summarize filing text using LLM.

    This function maintains backward compatibility with existing code.
    """
    return _summarizer.summarize_llama(filings_text)


def summarize_filing(data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Generate summary from structured filing data.

    This function maintains backward compatibility with existing code.
    """
    return _summarizer.summarize_filing(data)


def summarize_filing_manual(
    holder_name: str,
    company_name: str,
    tx_type: str,
    amount: Optional[int],
    holding_before: Optional[int],
    holding_after: Optional[int],
    purpose_en: str,
) -> tuple[str, str]:
    return _summarizer.summarize_filing_manual(
        holder_name, company_name, tx_type, amount,
        holding_before, holding_after, purpose_en
    )
