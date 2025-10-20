"""
This script extracts the docs file into a string.
The docs file is a google doc, so we need to use the id from the dotenv to get the content using the google docs api.
"""

import litellm
from dotenv import load_dotenv
import json
import os
from typing import TypedDict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

DOC_ID = os.getenv('DOC_ID')

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']


class TestScenario(TypedDict):
    """Type definition for test scenario data"""
    case_number: int
    name: str
    description: str
    expected_diagnosis: str | None


def get_google_docs_service():
    """
    Authenticate and return a Google Docs API service object.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "credentials.json not found. Please:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Enable Google Docs API\n"
                    "3. Create OAuth 2.0 credentials (Desktop app)\n"
                    "4. Download and save as 'credentials.json'"
                )
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)  # Use fixed port
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('docs', 'v1', credentials=creds)


def get_document_body_text(doc_id: str) -> str:
    """
    Retrieve the body text from a Google Doc and clean up formatting.
    """
    import re
    
    service = get_google_docs_service()
    
    document = service.documents().get(documentId=doc_id).execute()
    
    body_content = document.get('body', {}).get('content', [])
    text_parts = []
    
    for element in body_content:
        if 'paragraph' in element:
            paragraph = element['paragraph']
            for elem in paragraph.get('elements', []):
                if 'textRun' in elem:
                    text_parts.append(elem['textRun'].get('content', ''))
    
    full_text = ''.join(text_parts)
    

    full_text = full_text.replace('\x0b', '')
    
    full_text = re.sub(r' +', ' ', full_text)
    
    lines = full_text.split('\n')
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    
    return '\n'.join(cleaned_lines)


def extract_case_separated_docs() -> str:
    """
    Extracts the docs file into a JSON file.
    """
    doc_text = get_document_body_text(DOC_ID)
    case_separated = doc_text.split("Case ")
    return case_separated

if __name__ == "__main__":
    extract_case_separated_docs()
