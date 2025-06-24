"""
Script to extract the title and body metadata from a news article page.

Supports extracting metadata from various Indonesian news sources including:
- IDN Financials, Detik, Tempo, CNBC, Okezone, Tribun, Liputan6
- Antaranews, CNN, Kompas, Yahoo Finance, TradingView, MorningStar
- Livemint, Financial Times, and more
"""

import ssl
import logging
from typing import Optional, Tuple
import os

import dotenv
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException, Timeout, ConnectionError
import concurrent.futures

# Load environment variables
dotenv.load_dotenv()

# Configure SSL context
ssl._create_default_https_context = ssl._create_unverified_context

# Configure logging
logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Enhanced metadata extractor with robust error handling and fallback strategies."""

    def __init__(self, timeout: int = 30):
        """
        Initialize metadata extractor.

        Args:
            timeout (int): Request timeout in seconds
        """
        self.timeout = timeout
        self.proxy = os.environ.get("PROXY_KEY")
        self.proxy_support = (
            {"http": self.proxy, "https": self.proxy} if self.proxy else None
        )

        # Default headers to avoid bot detection
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def fetch(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from URL with robust error handling, offloading blocking I/O to a thread pool.
        """
        if not url or not isinstance(url, str):
            logger.error("Invalid URL provided")
            return None

        def _do_request(use_proxy: bool):
            try:
                if use_proxy and self.proxy_support:
                    response = requests.get(
                        url,
                        proxies=self.proxy_support,
                        verify=False,
                        timeout=self.timeout,
                        headers=self.headers,
                    )
                    response.raise_for_status()
                    logger.info(f"Successfully fetched content from {url} (with proxy)")
                    return response.text
                else:
                    response = requests.get(
                        url, verify=False, timeout=self.timeout, headers=self.headers
                    )
                    response.raise_for_status()
                    logger.info(f"Successfully fetched content from {url} (direct)")
                    return response.text
            except (RequestException, Timeout, ConnectionError) as e:
                if use_proxy:
                    logger.warning(
                        f"Proxy request failed for {url}: {e}. Trying without proxy..."
                    )
                else:
                    logger.error(f"Request error fetching URL {url}: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error fetching URL {url}: {e}")
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future = None
            if self.proxy_support:
                # Try with proxy first
                future = executor.submit(_do_request, True)
                result = future.result()
                if result is not None:
                    return result
                # Fallback to direct
                future = executor.submit(_do_request, False)
                return future.result()
            else:
                future = executor.submit(_do_request, False)
                return future.result()

    def extract_metadata(self, url: str) -> Tuple[str, str]:
        """
        Extract title and description metadata from a news article URL.

        Uses multiple fallback strategies:
        1. Open Graph meta tags (og:title, og:description)
        2. Standard HTML title and meta description
        3. Twitter Card meta tags
        4. Schema.org metadata

        Args:
            url (str): URL of the news article

        Returns:
            Tuple[str, str]: (title, body/description)
        """
        if not url:
            logger.error("No URL provided")
            return "No title found", "No description found"

        html_content = self.fetch(url)
        if not html_content:
            logger.error(f"Failed to fetch content from {url}")
            return "No title found", "No description found"

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            title, body = self._extract_metadata_from_soup(soup)

            logger.info(f"Successfully extracted metadata from {url}")
            return title, body

        except Exception as e:
            logger.error(f"Error parsing HTML from {url}: {e}")
            return "No title found", "No description found"

    def _extract_metadata_from_soup(self, soup: BeautifulSoup) -> Tuple[str, str]:
        """
        Extract metadata from BeautifulSoup object using multiple strategies.

        Args:
            soup (BeautifulSoup): Parsed HTML content

        Returns:
            Tuple[str, str]: (title, description)
        """
        title = self._extract_title(soup)
        description = self._extract_description(soup)

        return title, description

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract title using multiple strategies."""
        strategies = [
            # Open Graph title
            lambda: self._get_meta_content(soup, "meta", {"property": "og:title"}),
            # Twitter Card title
            lambda: self._get_meta_content(soup, "meta", {"name": "twitter:title"}),
            # Schema.org title
            lambda: self._get_meta_content(soup, "meta", {"itemprop": "name"}),
            # Standard HTML title
            lambda: soup.find("title").get_text().strip()
            if soup.find("title")
            else None,
            # H1 tag as fallback
            lambda: soup.find("h1").get_text().strip() if soup.find("h1") else None,
        ]

        for strategy in strategies:
            try:
                title = strategy()
                if title and title.strip():
                    return title.strip()
            except (AttributeError, Exception):
                continue

        return "No title found"

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract description using multiple strategies."""
        strategies = [
            # Open Graph description
            lambda: self._get_meta_content(
                soup, "meta", {"property": "og:description"}
            ),
            # Twitter Card description
            lambda: self._get_meta_content(
                soup, "meta", {"name": "twitter:description"}
            ),
            # Standard meta description
            lambda: self._get_meta_content(soup, "meta", {"name": "description"}),
            # Schema.org description
            lambda: self._get_meta_content(soup, "meta", {"itemprop": "description"}),
            # Article excerpt or summary
            lambda: self._extract_article_excerpt(soup),
        ]

        for strategy in strategies:
            try:
                description = strategy()
                if description and description.strip():
                    return description.strip()
            except (AttributeError, Exception):
                continue

        return "No description found"

    def _get_meta_content(
        self, soup: BeautifulSoup, tag: str, attrs: dict
    ) -> Optional[str]:
        """Helper to get content from meta tags."""
        meta_tag = soup.find(tag, attrs)
        return meta_tag.get("content") if meta_tag else None

    def _extract_article_excerpt(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract excerpt from article content as fallback."""
        # Try common article content selectors
        content_selectors = [
            "article p:first-of-type",
            ".article-content p:first-of-type",
            ".content p:first-of-type",
            ".post-content p:first-of-type",
            "p:first-of-type",
        ]

        for selector in content_selectors:
            try:
                element = soup.select_one(selector)
                if element and element.get_text().strip():
                    text = element.get_text().strip()
                    # Return first 200 characters as excerpt
                    return text[:200] + "..." if len(text) > 200 else text
            except Exception:
                continue

        return None


# Global instance for backward compatibility
_extractor = MetadataExtractor()


# Backward compatible functions
def fetch(url: str) -> Optional[str]:
    """
    Fetch HTML content from URL.

    This function maintains backward compatibility with existing code.
    """
    return _extractor.fetch(url)


def extract_metadata(url: str) -> Tuple[str, str]:
    """
    Extract title and description metadata from a news article URL.

    This function maintains backward compatibility with existing code.
    """
    return _extractor.extract_metadata(url)


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
