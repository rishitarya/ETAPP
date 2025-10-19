import os, json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None

    # Try local file
    if os.path.exists('service_token.json'):
        creds = Credentials.from_authorized_user_file('service_token.json', SCOPES)

    # Try environment variable (for cloud)
    elif os.getenv("GMAIL_TOKEN_JSON"):
        token_data = json.loads(os.getenv("GMAIL_TOKEN_JSON"))
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # If no creds available, start interactive login
    if not creds:
        if not os.path.exists('credentials.json'):
            raise Exception("Missing credentials.json for local OAuth setup")
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')

        # Save refreshable credentials
        with open('service_token.json', 'w') as token:
            token.write(creds.to_json())

    # Refresh if needed
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save back updated credentials
            with open('service_token.json', 'w') as token:
                token.write(creds.to_json())

    # Return Gmail service
    service = build('gmail', 'v1', credentials=creds)
    return service
