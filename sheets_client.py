"""
sheets_client.py - Google Sheets connector for personal health log
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Health Log")
WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "Daily Log")

HEADERS = [
    "Date", "Weight (kg)",
    "Breakfast", "Lunch", "Dinner", "Snacks",
    "Calories", "Protein (g)", "Carbs (g)", "Fat (g)",
    "Exercise", "Steps (yesterday)"
]


def _get_credentials():
    """
    Loads service account credentials.
    Supports either:
    - GOOGLE_CREDENTIALS_JSON env var (full JSON as a string) — used for cloud deploy
    - GOOGLE_CREDENTIALS_FILE path to a local json file — used for local dev
    """
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        info = json.loads(creds_json)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    if os.path.exists(creds_file):
        return Credentials.from_service_account_file(creds_file, scopes=SCOPES)

    raise RuntimeError(
        "No Google credentials found. Set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_FILE."
    )


def get_worksheet():
    """Connect to the sheet, creating it (and headers) if needed."""
    creds = _get_credentials()
    client = gspread.authorize(creds)

    try:
        sheet = client.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(SHEET_NAME)

    try:
        worksheet = sheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=len(HEADERS))
        worksheet.append_row(HEADERS)

    # Ensure headers exist if sheet was empty
    first_row = worksheet.row_values(1)
    if first_row != HEADERS:
        worksheet.insert_row(HEADERS, 1)

    return worksheet


def append_log(entry: dict):
    """Append one day's log. entry keys should match HEADERS (Date auto-filled if missing)."""
    worksheet = get_worksheet()
    entry.setdefault("Date", datetime.now().strftime("%Y-%m-%d"))
    row = [entry.get(h, "") for h in HEADERS]
    worksheet.append_row(row)
    return True


def get_history(limit: int = 30):
    """Return the most recent `limit` rows as a list of dicts."""
    worksheet = get_worksheet()
    records = worksheet.get_all_records()
    return records[-limit:]


def has_entry_for_today():
    """Check if today's date already has a row (avoid duplicate logging)."""
    today = datetime.now().strftime("%Y-%m-%d")
    records = get_history(limit=1000)
    return any(r.get("Date") == today for r in records)
