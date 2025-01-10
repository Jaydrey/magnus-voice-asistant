from typing import Any
from pathlib import Path
import logging
from functools import wraps

import numpy as np
import pandas as pd

from google.oauth2.service_account import Credentials
import gspread

from fastapi import (
    Request, 
    HTTPException,
    Header,
)

from twilio.request_validator import RequestValidator



logger = logging.getLogger(LOGGER_NAME)

def validate_twilio_request(f):
    """Validates that incoming requests genuinely originated from Twilio"""
    @wraps(f)
    async def decorated_function(request: Request, x_twilio_signature: str = Header(None), *args, **kwargs):
        
        validator = RequestValidator(TWILIO_AUTH_TOKEN)

        # Validate the request using its URL, POST data,
        # and X-TWILIO-SIGNATURE header
        form_data = await request.form()
        request_valid = validator.validate(
            str(request.url),
            form_data,
            x_twilio_signature or "",
        )

        # Continue processing the request if it's valid, return a 403 error if
        # it's not
        if request_valid or DEBUG:
            return await f(*args, **kwargs)
        else:
            logger.error("Twilio Request Validation Failed")
            return HTTPException(
                status_code=403,
                detail="Twilio Request Validation Failed"
            )
        
    return decorated_function

def authenticate_google_sheets(credentials_file: Path) -> (gspread.client.Client | None):
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
        ]
        credentials = Credentials.from_service_account_file(credentials_file.as_posix(), scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        print(f"Error occurred in authenticate_google_sheets(): {e}")
        logger.exception("Error occurred in authenticate_google_sheets()")
        return None
    
def connect_to_google_sheet(client: gspread.client.Client, spreadsheet_id: str) -> (gspread.spreadsheet.Spreadsheet | None):
    try:
        sheet = client.open_by_key(spreadsheet_id)
        return sheet
    except Exception as e:
        print(f"Error occurred in connect_to_google_sheet(): {e}")
        logger.exception("Error occurred in connect_to_google_sheet()")
        return None
    
def get_data_frame(records: list[dict[str, Any]]) -> (pd.DataFrame | None):
    try:
        column_names = ["Caller SID", "Caller Number", "Full Name", "Call Transcript", "Call Summary"]
        df = pd.DataFrame(records, columns=column_names)
        return df
    except Exception as e:
        logger.exception("Error occurred in get_dataframe()")
        return None
    
def get_caller_first_message(caller_number: str) -> (dict[str, str] | None):
    client = authenticate_google_sheets(GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_FILE)
    if client is None:
        return None
    
    sheet = connect_to_google_sheet(client, SPREADSHEET_ID)
    if sheet is None:
        return None
    
    try:
        worksheet = sheet.get_worksheet_by_id()
    except gspread.exceptions.WorksheetNotFound:
        logger.exception("Worksheet not found")
        return None

   
    records = worksheet.get_all_records()
    df = get_data_frame(records)
    caller_df = df[df["Caller Number"] == caller_number]
    if caller_df.empty:
        return None
    
    last_call = caller_df.iloc[-1]

    return {
        "call_summary": last_call["Call Summary"],
        "full_name": last_call["Full Name"],
    }


