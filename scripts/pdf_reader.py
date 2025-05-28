"""
Script to read PDF filings with IDX Format.

Provides robust PDF text extraction with comprehensive error handling
and support for various PDF formats and structures.
"""

import logging
from pathlib import Path
from typing import Optional, List
import tempfile
import os

import pdfplumber

# Configure logging
logger = logging.getLogger(__name__)


class PDFReader:
    """Enhanced PDF reader with robust error handling and multiple extraction strategies."""

    def __init__(self):
        """Initialize PDF reader."""
        pass

    def extract_from_pdf(self, filename: str) -> str:
        """
        Extract text from a PDF file with comprehensive error handling.

        Args:
            filename (str): Path to the PDF file

        Returns:
            str: Extracted text from the PDF file or error message
        """
        if not filename:
            logger.error("No filename provided")
            return "Error: No filename provided"

        # Validate file exists
        file_path = Path(filename)
        if not file_path.exists():
            logger.error(f"PDF file not found: {filename}")
            return f"Error: PDF file not found: {filename}"

        if not file_path.suffix.lower() == ".pdf":
            logger.error(f"File is not a PDF: {filename}")
            return f"Error: File is not a PDF: {filename}"

        try:
            logger.info(f"Extracting text from PDF: {filename}")
            text = self._extract_with_pdfplumber(filename)

            if not text.strip():
                logger.warning(f"No text extracted from {filename}")
                return "Warning: No text content found in PDF"

            logger.info(
                f"Successfully extracted {len(text)} characters from {filename}"
            )
            return text

        except Exception as e:
            error_msg = f"Error extracting text from PDF {filename}: {e}"
            logger.error(error_msg)
            return error_msg

    def _extract_with_pdfplumber(self, filename: str) -> str:
        """
        Extract text using pdfplumber with page-by-page processing.

        Args:
            filename (str): Path to PDF file

        Returns:
            str: Extracted text
        """
        text = ""
        pages_processed = 0

        try:
            with pdfplumber.open(filename) as pdf:
                total_pages = len(pdf.pages)
                logger.debug(f"PDF has {total_pages} pages")

                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text
                            text += "\n"  # Add page separator
                            pages_processed += 1
                        else:
                            logger.debug(f"No text found on page {page_num}")
                    except Exception as e:
                        logger.warning(
                            f"Error extracting text from page {page_num}: {e}"
                        )
                        continue

                logger.info(
                    f"Processed {pages_processed}/{total_pages} pages successfully"
                )

        except Exception as e:
            logger.error(f"Error opening PDF with pdfplumber: {e}")
            raise

        return text.strip()

    def extract_from_bytes(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF bytes data.

        Args:
            pdf_bytes (bytes): PDF file content as bytes

        Returns:
            str: Extracted text or error message
        """
        if not pdf_bytes:
            logger.error("No PDF bytes data provided")
            return "Error: No PDF bytes data provided"

        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(pdf_bytes)
                temp_filename = temp_file.name

            # Extract text from temporary file
            text = self.extract_from_pdf(temp_filename)

            # Clean up temporary file
            try:
                os.unlink(temp_filename)
            except OSError:
                logger.warning(f"Could not delete temporary file: {temp_filename}")

            return text

        except Exception as e:
            error_msg = f"Error extracting text from PDF bytes: {e}"
            logger.error(error_msg)
            return error_msg

    def get_pdf_info(self, filename: str) -> dict:
        """
        Get basic information about the PDF file.

        Args:
            filename (str): Path to PDF file

        Returns:
            dict: PDF information including page count, metadata, etc.
        """
        info = {"page_count": 0, "file_size": 0, "metadata": {}, "error": None}

        try:
            file_path = Path(filename)
            if not file_path.exists():
                info["error"] = f"File not found: {filename}"
                return info

            info["file_size"] = file_path.stat().st_size

            with pdfplumber.open(filename) as pdf:
                info["page_count"] = len(pdf.pages)

                # Extract metadata if available
                if hasattr(pdf, "metadata") and pdf.metadata:
                    info["metadata"] = dict(pdf.metadata)

        except Exception as e:
            info["error"] = str(e)
            logger.error(f"Error getting PDF info: {e}")

        return info


# Global instance for backward compatibility
_reader = PDFReader()


# Backward compatible function
def extract_from_pdf(filename: str) -> str:
    """
    Extract text from a PDF file.

    This function maintains backward compatibility with existing code.

    Args:
        filename (str): The path to the PDF file

    Returns:
        str: A string containing the extracted text from the PDF file
    """
    return _reader.extract_from_pdf(filename)
