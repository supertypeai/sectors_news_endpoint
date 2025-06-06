"""
Script to generate an article from PDF reader for filings.
Handles extraction and processing of insider trading documents.
"""

import json
import re
from datetime import datetime
from typing import Dict, Optional, Any
import logging

from model.price_transaction import PriceTransaction
from scripts.classifier import get_sentiment_chat, get_tags_chat
from scripts.summary_filings import summarize_filing

# Configure logging
logger = logging.getLogger(__name__)


class FilingArticleGenerator:
    """Class to handle generation of articles from filing PDFs."""

    def __init__(self):
        """Initialize the generator with sector data."""
        try:
            with open("./data/sectors_data.json", "r") as f:
                self.sectors_data = json.load(f)
        except FileNotFoundError:
            logger.error("sectors_data.json not found")
            self.sectors_data = {}
        except json.JSONDecodeError:
            logger.error("Invalid JSON in sectors_data.json")
            self.sectors_data = {}

    @staticmethod
    def extract_datetime(text: str) -> str:
        """
        Extract datetime from text using regex pattern.

        Args:
            text (str): Text containing datetime information

        Returns:
            str: Extracted datetime string or empty string if not found
        """
        pattern = r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}(?::\d{2})?"
        match = re.search(pattern, text)
        return match.group(0) if match else ""

    @staticmethod
    def extract_number(input_string: str) -> Optional[int]:
        """
        Extract numeric part from input string.

        Args:
            input_string (str): String containing number and other characters

        Returns:
            Optional[int]: Extracted number or None if not found
        """
        try:
            cleaned = input_string.replace(".", "")
            match = re.search(r"\d+", cleaned)
            return int(match.group()) if match else None
        except (ValueError, AttributeError):
            logger.warning(f"Could not extract number from: {input_string}")
            return None

    def extract_info(self, text: str) -> Dict[str, Any]:
        """
        Extract filing information from PDF text.

        Args:
            text (str): Raw PDF text content

        Returns:
            Dict[str, Any]: Extracted filing information
        """
        lines = text.split("\n")

        # Initialize article info with default values
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
            "share_percentage_before": "",
            "share_percentage_after": "",
            "share_percentage_transaction": "",
            "purpose": "",
            "date_time": "",
            "price": 0,
            "price_transaction": {"prices": [], "amount_transacted": []},
        }

        # Extraction patterns for different fields
        extraction_patterns = {
            "document_number": "Nomor Surat",
            "company_name": "Nama Perusahaan",
            "ticker": "Kode Emiten",
        }

        try:
            for i, line in enumerate(lines):
                # Extract basic information
                for field, pattern in extraction_patterns.items():
                    if pattern in line and i > 0:
                        article_info[field] = lines[i - 1].strip()

                # Extract holder name (special case)
                if "Nama Pemegang Saham" in line:
                    article_info["holder_name"] = " ".join(line.split()[3:])

                # Extract category
                if "Kategori" in line:
                    article_info["category"] = " ".join(line.split()[1:])

                # Extract control status
                if "Status Pengedali" in line or "Status Pengendali" in line:
                    article_info["control_status"] = " ".join(line.split()[2:])

                # Extract shareholding information
                shareholding_fields = {
                    "Jumlah Saham Sebelum Transaksi": "shareholding_before",
                    "Jumlah Saham Setelah Transaksi": "shareholding_after",
                    "Persentase Saham Sebelum Transaksi": "share_percentage_before",
                    "Persentase Saham Sesudah Transaksi": "share_percentage_after",
                    "Persentase Saham yang ditransaksi": "share_percentage_transaction",
                }

                for pattern, field in shareholding_fields.items():
                    if pattern in line:
                        article_info[field] = line.split()[-1]

                # Extract purpose
                if "Tujuan Transaksi" in line:
                    article_info["purpose"] = " ".join(line.split()[2:])

                # Extract datetime
                if "Tanggal dan Waktu" in line or "Date and Time" in line:
                    date_time_str = " ".join(line.split()[3:])
                    date_time_str = self.extract_datetime(date_time_str)

                    if date_time_str:
                        try:
                            parsed_date = datetime.strptime(
                                date_time_str, "%d-%m-%Y %H:%M"
                            )
                            article_info["date_time"] = parsed_date.strftime(
                                "%d-%m-%Y %H:%M"
                            )
                        except ValueError:
                            logger.warning(f"Could not parse date: {date_time_str}")
                            article_info["date_time"] = date_time_str

                # Extract transaction prices
                if "Jenis Transaksi Harga Transaksi" in line and i + 2 < len(lines):
                    try:
                        # Get the main transaction price
                        price_line = lines[i + 2].split(" ")
                        if len(price_line) > 1:
                            article_info["price"] = (
                                self.extract_number(price_line[1]) or 0
                            )

                        # Extract all price transactions
                        price_transactions = []
                        amounts_transacted = []

                        for j in range(i + 2, len(lines)):
                            line_parts = lines[j].split(" ")
                            if len(line_parts) == 0:
                                break

                            transaction_type = line_parts[0]
                            if transaction_type not in ["Pembelian", "Penjualan"]:
                                break

                            if len(line_parts) > 1:
                                price = self.extract_number(line_parts[1])
                                if price is not None:
                                    price_transactions.append(price)

                            if len(line_parts) > 5:
                                amount = self.extract_number(line_parts[5])
                                if amount is not None:
                                    amounts_transacted.append(amount)

                        article_info["price_transaction"]["prices"] = price_transactions
                        article_info["price_transaction"]["amount_transacted"] = (
                            amounts_transacted
                        )

                    except (IndexError, ValueError) as e:
                        logger.warning(f"Error extracting transaction prices: {e}")

        except Exception as e:
            logger.error(f"Error extracting filing information: {e}")

        return article_info

    def generate_article_filings(
        self,
        pdf_url: str,
        sub_sector: str,
        holder_type: str,
        data: str,
        uid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate article from PDF filing data.

        Args:
            pdf_url (str): URL of the PDF source
            sub_sector (str): Sub-sector classification
            holder_type (str): Type of holder (insider/institution)
            data (str): Raw PDF text content
            uid (Optional[str]): Unique identifier for the filing

        Returns:
            Dict[str, Any]: Generated article data
        """
        logger.info(f"Generating article from PDF: {pdf_url}")

        # Initialize article structure
        article = self._initialize_article_structure(
            pdf_url, sub_sector, holder_type, uid
        )

        try:
            # Extract information from PDF text
            article_info = self.extract_info(data)
            logger.debug(f"Extracted article info: {article_info}")

            # Populate article with extracted information
            self._populate_article_data(article, article_info)

            # Generate title and body using LLM
            article = self._generate_title_and_body(article)

            # Update sector information if missing
            article = self._update_sector_information(article)

            # Clean up article (remove purpose if exists)
            if "purpose" in article:
                del article["purpose"]

            logger.info(
                f"Successfully generated article for {article_info.get('company_name', 'Unknown')}"
            )
            return article

        except Exception as e:
            logger.error(f"Error generating article: {e}")
            # Return minimal article structure on error
            return article

    def _initialize_article_structure(
        self, pdf_url: str, sub_sector: str, holder_type: str, uid: Optional[str]
    ) -> Dict[str, Any]:
        """Initialize basic article structure."""
        return {
            "title": "",
            "body": "",
            "source": pdf_url,
            "timestamp": "",
            "sub_sector": sub_sector,
            "sector": self.sectors_data.get(sub_sector, ""),
            "tags": ["insider-trading"],
            "tickers": [],
            "transaction_type": "",
            "holder_type": holder_type,
            "holding_before": 0,
            "holding_after": 0,
            "share_percentage_before": 0.0,
            "share_percentage_after": 0.0,
            "share_percentage_transaction": 0.0,
            "amount_transaction": 0,
            "holder_name": "",
            "purpose": "",
            "price": 0,
            "transaction_value": 0,
            "price_transaction": {"prices": [], "amount_transacted": []},
            "UID": uid,
        }

    def _populate_article_data(
        self, article: Dict[str, Any], article_info: Dict[str, Any]
    ) -> None:
        """Populate article with extracted information."""
        try:
            # Basic information
            article["title"] = (
                f"Informasi insider trading {article_info['holder_name']} dalam {article_info['company_name']}"
            )
            article["body"] = (
                f"{article_info['document_number']} - {article_info['date_time']} - "
                f"Kategori {article_info['category']} - Transaksi {article_info['holder_name']} "
                f"dalam saham {article_info['company_name']} berubah dari "
                f"{article_info['shareholding_before']} menjadi {article_info['shareholding_after']}"
            )

            # Ticker information
            ticker = article_info["ticker"].upper()
            if not ticker.endswith(".JK"):
                ticker += ".JK"
            article["tickers"] = [ticker]

            # Timestamp handling
            date_time = article_info["date_time"]
            if date_time:
                try:
                    if not date_time.endswith(":00"):
                        date_time += ":00"
                    parsed_timestamp = datetime.strptime(date_time, "%d-%m-%Y %H:%M:%S")
                    article["timestamp"] = parsed_timestamp.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError as e:
                    logger.warning(f"Error parsing timestamp {date_time}: {e}")
                    article["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Financial data
            self._populate_financial_data(article, article_info)

            # Transaction value calculation
            if (
                article_info["price_transaction"]["amount_transacted"]
                and article_info["price_transaction"]["prices"]
            ):
                price_transaction = PriceTransaction(
                    amount_transacted=article_info["price_transaction"][
                        "amount_transacted"
                    ],
                    prices=article_info["price_transaction"]["prices"],
                )
                article["price"], article["transaction_value"] = (
                    price_transaction.get_price_transaction_value()
                )

        except Exception as e:
            logger.error(f"Error populating article data: {e}")

    def _populate_financial_data(
        self, article: Dict[str, Any], article_info: Dict[str, Any]
    ) -> None:
        """Populate financial data with proper error handling."""
        try:
            # Holdings
            holding_before_str = article_info["shareholding_before"].replace(".", "")
            holding_after_str = article_info["shareholding_after"].replace(".", "")

            article["holding_before"] = (
                int(holding_before_str) if holding_before_str.isdigit() else 0
            )
            article["holding_after"] = (
                int(holding_after_str) if holding_after_str.isdigit() else 0
            )

            # Percentages
            for field in [
                "share_percentage_before",
                "share_percentage_after",
                "share_percentage_transaction",
            ]:
                value_str = article_info[field].replace(",", ".").replace("%", "")
                try:
                    article[field] = float(value_str) if value_str else 0.0
                except ValueError:
                    article[field] = 0.0

            # Transaction details
            article["transaction_type"] = (
                "buy"
                if article["holding_before"] < article["holding_after"]
                else "sell"
            )
            article["amount_transaction"] = abs(
                article["holding_before"] - article["holding_after"]
            )
            article["holder_name"] = article_info["holder_name"]
            article["purpose"] = article_info["purpose"]
            article["price_transaction"] = article_info["price_transaction"]

        except Exception as e:
            logger.error(f"Error populating financial data: {e}")

    def _generate_title_and_body(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Generate enhanced title and body using LLM."""
        try:
            new_title, new_body = summarize_filing(article)

            if new_body:
                article["body"] = new_body

                # Get tags and sentiment
                tags = get_tags_chat(new_body)
                sentiment = get_sentiment_chat(new_body)

                # Combine tags
                if sentiment:
                    tags.append(sentiment[0])
                tags.append(article["tags"][0])  # Keep original "insider-trading" tag
                article["tags"] = tags

            if new_title:
                article["title"] = new_title

        except Exception as e:
            logger.error(f"Error generating title and body: {e}")

        return article

    def _update_sector_information(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Update sector information if missing."""
        try:
            if not article.get("sub_sector"):
                # Try to get sub_sector from companies data
                try:
                    with open("./data/companies.json", "r") as f:
                        companies = json.load(f)

                    if article["tickers"]:
                        ticker = article["tickers"][0].replace(".JK", "")
                        if ticker in companies:
                            article["sub_sector"] = companies[ticker]["sub_sector"]

                except (FileNotFoundError, KeyError, IndexError) as e:
                    logger.warning(
                        f"Could not update sub_sector from companies data: {e}"
                    )

            # Update sector if missing
            if (
                not article.get("sector")
                and article.get("sub_sector") in self.sectors_data
            ):
                article["sector"] = self.sectors_data[article["sub_sector"]]

        except Exception as e:
            logger.error(f"Error updating sector information: {e}")

        return article


# Global instance for backward compatibility
_generator = FilingArticleGenerator()


# Export functions for backward compatibility
def generate_article_filings(
    pdf_url: str,
    sub_sector: str,
    holder_type: str,
    data: str,
    uid: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate article from PDF filing data.

    This function maintains backward compatibility with the existing API.
    """
    return _generator.generate_article_filings(
        pdf_url, sub_sector, holder_type, data, uid
    )


def extract_info(text: str) -> Dict[str, Any]:
    """Extract filing information from PDF text (backward compatibility)."""
    return _generator.extract_info(text)


def extract_datetime(text: str) -> str:
    """Extract datetime from text (backward compatibility)."""
    return FilingArticleGenerator.extract_datetime(text)


def extract_number(input_string: str) -> Optional[int]:
    """Extract number from string (backward compatibility)."""
    return FilingArticleGenerator.extract_number(input_string)
