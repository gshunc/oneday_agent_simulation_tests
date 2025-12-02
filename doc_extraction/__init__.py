"""
Doc extraction module for OneDay agent simulation tests.
Handles extracting test scenarios from Google Docs.
"""

from doc_extraction.doc_extraction import (
    extract_case_separated_docs,
    get_document_body_text,
    get_google_docs_service,
)

__all__ = [
    "extract_case_separated_docs",
    "get_document_body_text",
    "get_google_docs_service",
]

