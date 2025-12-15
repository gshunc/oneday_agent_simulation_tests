"""
This script extracts the docs file into a string.
The docs file is a public Google Doc, fetched via the export URL (no OAuth required).
"""

from dotenv import load_dotenv
import os
import re
from typing import TypedDict
import requests

load_dotenv()

DOC_ID = os.getenv('DOC_ID')


class Scenario(TypedDict):
    """Type definition for test scenario data"""
    case_number: int
    name: str
    description: str
    expected_diagnosis: str | None


def extract_doc_id(url_or_id: str) -> str:
    """Extract doc ID from various Google Docs URL formats or return as-is if already an ID."""
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id)
    return match.group(1) if match else url_or_id


def get_document_body_text(doc_id: str) -> str:
    """
    Fetch Google Doc as plain text via public export URL.
    The doc must be shared as "Anyone with the link can view".
    """
    doc_id = extract_doc_id(doc_id)
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    response = requests.get(url)
    response.raise_for_status()

    full_text = response.text

    # Clean up formatting
    full_text = full_text.replace('\x0b', '')
    full_text = re.sub(r' +', ' ', full_text)

    lines = full_text.split('\n')
    cleaned_lines = [line.strip() for line in lines if line.strip()]

    return '\n'.join(cleaned_lines).lower()


def extract_case_separated_docs() -> list[tuple[int, str]]:
    """
    Extracts the docs file and returns a list of tuples (case_number, case_text).
    Splits on 'case' followed by a number to avoid splitting on the word 'case' in descriptions.
    """
    doc_text = get_document_body_text(DOC_ID)
    
    # Split by "case" followed by whitespace and a number (case-insensitive)
    # The pattern captures the number so we can use it
    parts = re.split(r'(?i)\bcase\s+(\d+)', doc_text)
    
    # parts[0] is text before first case (usually empty or header)
    # parts[1] is the first case number, parts[2] is the first case text
    # parts[3] is second case number, parts[4] is second case text, etc.
    
    case_separated = []
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            case_num = int(parts[i])
            case_text = parts[i + 1].strip()
            case_separated.append((case_num, case_text))
        
    return case_separated

if __name__ == "__main__":
    print(extract_case_separated_docs())
