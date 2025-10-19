from __future__ import print_function
import os
import os.path
from rapidfuzz import fuzz
from datetime import datetime, timedelta
import base64
import re
import pandas as pd
import numpy as np
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials as sac

SERVICE_ACCOUNT_JSON = os.environ.get("SERVICE_ACCOUNT_FILE")
SERVICE_ACCOUNT_FILE = "service_account.json"

if SERVICE_ACCOUNT_JSON:
    with open(SERVICE_ACCOUNT_FILE, "w") as f:
        f.write(SERVICE_ACCOUNT_JSON)

SHEETS_SAC_JSON = os.environ.get("SHEETS_SAC_FILE")
SHEETS_SAC_FILE = "sheets_sac.json"

if SHEETS_SAC_JSON:
    with open(SHEETS_SAC_FILE, "w") as f:
        f.write(SHEETS_SAC_JSON)

from gmail_auth import get_gmail_service

service = get_gmail_service()

def get_msgs(bank,days):
    creds = Credentials.from_authorized_user_file(SERVICE_ACCOUNT_FILE, ['https://www.googleapis.com/auth/gmail.readonly'])
    
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
    
    service = build('gmail', 'v1', credentials=creds)

    from_email = {'axis':'alerts@axisbank.com','axiscc':'alerts@axisbank.com','hdfc':'alerts@hdfcbank.net','mahb':'mahaalert@mahabank.co.in'}
    date_30_days_ago = (datetime.utcnow() - timedelta(days=days)).strftime("%Y/%m/%d")
    # date_30_days_ag = (datetime.utcnow() - timedelta(days=47)).strftime("%Y/%m/%d")
    query = f'from:{from_email[bank]} after:{date_30_days_ago} (debited)'
    if bank == 'axiscc':
        query = f'from:{from_email[bank]} after:{date_30_days_ago} ("Credit Card Transaction")'
        print(query)
    
    print(f"🔍 Fetching Gmail messages since {date_30_days_ago} with query: {query}")
    
    # Step 3: Fetch matching messages
    results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
    messages = results.get('messages', [])

    alerts = pd.DataFrame([],columns = ['date','msg'])
    
    if not messages:
        print(f"No debit-related emails found in the {days} days.")
    else:
        print(f"Found {len(messages)} matching emails.\n")
    
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            headers = msg_data['payload']['headers']
    
            msg_from = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            msg_subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            msg_date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
            # print(msg_data['payload'])
            # Extract plain text from parts
            text = ''
            snippet = msg_data['snippet']
            # print(msg_data['payload']['parts'][0]['body'])
            if msg_data['payload']['parts'][0]['mimeType'] in ['text/html','text/plain']:
                data = msg_data['payload']['parts'][0]['body']['data']
                decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                soup = BeautifulSoup(decoded, 'html.parser')
                text += soup.get_text(separator=' ', strip=True)
                # print('text',text)
            # Clean body a bit
            body_cleaned = re.sub(r'\s+', ' ', text)
            alert = {'date':msg_date,'msg':body_cleaned}
            alerts = pd.concat([alerts,pd.DataFrame([alert])],ignore_index = True)

    return alerts
            

def classify(df,to_column = 'to'):
    
    CATEGORY_KEYWORDS = None
    try:
        with open("expense_keywords_structured.json", "r", encoding="utf-8") as f:
            CATEGORY_KEYWORDS = json.load(f)
    except Exception as e:
        print(e,'keyword json not found buddy find where it is or ask chat gpt to make one')
        
    if CATEGORY_KEYWORDS:
        df["to_lower"] = df[to_column].astype(str).str.lower()

        def find_category(to_value):
            best_match = ("Others", 0)
            for category, keywords in CATEGORY_KEYWORDS.items():
                for keyword in keywords:
                    to_value_ = to_value.replace('&','and')
                    keyword_ = keyword.replace('&','and')
                    score = fuzz.partial_ratio(to_value_, keyword_.lower())
                    if score > best_match[1] and score >= 80:
                        best_match = (category, score)
            return best_match[0]
    
        df["category"] = df["to_lower"].apply(find_category)
        df.drop(columns=["to_lower"], inplace=True)
        return df

    else:
        return None


def extract_and_classify(bank,days):

    data = get_msgs(bank,days)
    amounts = []
    tos = []
    vias = []
    
    if bank == 'axiscc':
        for msg in data['msg']:
            amount = float(re.search('Transaction Amount: INR (\d+)',msg).group(1))
            to = re.search('Merchant Name: (.+) Axis Bank Credit Card',msg).group(1)
            via = 'card'
            amounts.append(amount)
            tos.append(to)
            vias.append(via)

    elif bank == 'axis':
        for msg in data['msg']:
            if 'UPI' in msg:
                try:
                    amount = float(re.search('INR (\d+\.\d+)',msg).group(1))
                    to = re.search('UPI/.+/(.+) If this',msg).group(1)
                    amounts.append(amount)
                    tos.append(to)
                    via = 'UPI'
                    vias.append(via)
                except Exception as e:
                    print(bank,via,e)
            elif 'IMPS' in msg:
                try:
                    amount = float(re.search('INR (\d+\.\d+)',msg).group(1))
                    to = 'RENT'
                    amounts.append(amount)
                    tos.append(to)
                    via = 'IMPS'
                    via.append(via)
                except Exception as e:
                    print(bank,via,e)

    elif bank == 'hdfc':
        for msg in data['msg']:
            if 'UPI' in msg:
                try:
                    amount = float(re.search('Rs\.(\d+\.\d+)',msg).group(1))
                    to = re.search(r"(\S+@\S+)\s+(.+?)\s+on\s+([\d\-]+)",msg).group(2)
                    amounts.append(amount)
                    tos.append(to)
                    via = 'UPI'
                    vias.append(via)
                except Exception as e:
                    print(bank,via,e)
            else:
                try:
                    amount = float(re.search('Rs\.(\d+\.\d+)',msg).group(1))
                    to = re.search(r"towards (.+?)\s+on\s+[\d\-]+",msg).group(1)
                    amounts.append(amount)
                    tos.append(to)
                    via = 'Card'
                    vias.append(via)
                except Exception as e:
                    print(bank,via,e)
    elif bank == 'mahb':
        for msg in data['msg']:
                try:
                    amount = float(re.search('INR (\d+\.\d+)',msg).group(1))
                    to = 'OTHERS'
                    amounts.append(amount)
                    tos.append(to)
                    via = 'UPI'
                    vias.append(via)
                except Exception as e:
                    print(bank,via,e)
    
    data['amount'] = amounts
    data['to'] = tos
    data['medium'] = vias
    data["date"] = pd.to_datetime(data["date"], utc=True, errors="coerce")
    data["date"] = data["date"].dt.tz_convert("Asia/Kolkata")
    data["date"] = data["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return classify(data)
                
def push_to_sheets(df):
    # SERVICE_ACCOUNT_FILE = "sac.json"

    # Scopes for Sheets API
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    
    # Authenticate
    creds = sac.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1Jd6E_x2Wqa7rPOhjT3SxwlF7r0kO6Hq35DntwLQ-Gi0/edit?pli=1&gid=0#gid=0').sheet1

    for index, row in df.iterrows():
        sheet.append_row(row.tolist())

    return 0


def statement_extraction(banks = ['axis','axiscc','mahb','hdfc'],days = 7):
    for bank in banks:
        df = extract_and_classify(bank,days)
        try:
            df['account'] = bank.capitalize()
            push_to_sheets(df)
            print('Statement push successful')

            return 0
        except Exception as e:
            print(e)
            return 100
        
def push_to_sheets(df):

    # Scopes for Sheets API
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    print(len(SHEETS_SAC_JSON))
    
    # Authenticate
    creds = sac.from_service_account_file(
        SHEETS_SAC_FILE,
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1Jd6E_x2Wqa7rPOhjT3SxwlF7r0kO6Hq35DntwLQ-Gi0/edit?pli=1&gid=0#gid=0').sheet1

    for index, row in df.iterrows():
        sheet.append_row(row.tolist())

    return 0


def statement_extraction(banks = ['axis','axiscc','mahb','hdfc'],days = 7):
    for bank in banks:
        df = extract_and_classify(bank,days)
        try:
            df['account'] = bank.upper()
            df['epoch'] = pd.to_datetime(df['date']).astype(int) // 10**9
            if(len(df) > 0):
                push_to_sheets(df)
            print('Statement push successful')
            # return 0

        except Exception as e:
            print(e)


