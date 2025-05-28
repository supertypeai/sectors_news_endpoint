"""
Scripts package for news processing and analysis.

This package provides comprehensive functionality for:
- News article processing and classification
- PDF filing analysis
- Article scoring and metadata extraction
- Content summarization and enhancement
"""

# Core exports (maintain exact compatibility)
from .classifier import (
    get_tickers,
    get_tags_chat,
    get_subsector_chat,
    get_sentiment_chat,
    predict_dimension,
    load_company_data,
    load_subsector_data,
    load_tag_data,
    NewsClassifier,
)

from .generate_article import (
    generate_article_filings,
    extract_info,
    extract_datetime,
    extract_number,
    FilingArticleGenerator,
)

from .metadata import (
    extract_metadata,
    fetch,
)

from .pdf_reader import (
    extract_from_pdf,
)

from .scorer import (
    get_article_score,
)

from .summary_filings import (
    summarize_filing,
    summarize_llama,
    count_tokens,
    FilingsOutput,
)

from .summary_news import (
    summarize_news,
    get_article_body,
    preprocess_text,
    NewsOutput,
)

# Package metadata
__version__ = "1.0.0"
__author__ = "Sectors News Team"

# Public API (for type checking and documentation)
__all__ = [
    # Classifier functions
    "get_tickers",
    "get_tags_chat",
    "get_subsector_chat",
    "get_sentiment_chat",
    "predict_dimension",
    "load_company_data",
    "load_subsector_data",
    "load_tag_data",
    "NewsClassifier",
    # Article generation
    "generate_article_filings",
    "extract_info",
    "extract_datetime",
    "extract_number",
    "FilingArticleGenerator",
    # Metadata extraction
    "extract_metadata",
    "fetch",
    # PDF processing
    "extract_from_pdf",
    # Scoring
    "get_article_score",
    # Filing summarization
    "summarize_filing",
    "summarize_llama",
    "count_tokens",
    "FilingsOutput",
    # News summarization
    "summarize_news",
    "get_article_body",
    "preprocess_text",
    "NewsOutput",
]
