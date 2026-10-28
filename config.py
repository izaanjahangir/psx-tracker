"""Settings shared by all scripts, read from .env (see .env.example)."""

import os
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


def setting(name, default=None):
    value = os.getenv(name) or default
    if value in (None, ""):
        sys.exit(f"Missing setting {name}. Copy .env.example to .env and fill it in.")
    return value


KEY_FILE = PROJECT_DIR / setting("GOOGLE_KEY_FILE", "service-account.json")
TRADE_SHEET = setting("TRADE_SHEET", "Trade List")
PERF_SHEET = setting("PERF_SHEET", "Daily Performance")
PRICES_SHEET = setting("PRICES_SHEET", "Latest Prices")
DIVIDEND_SHEET = setting("DIVIDEND_SHEET", "Dividend summary")
# How many days back to re-price using the current Trade List.
DAYS_TO_REFILL = int(setting("DAYS_TO_REFILL", "30"))
PSX = setting("PSX_BASE_URL", "https://dps.psx.com.pk")
TEMPLATE_FILE = PROJECT_DIR / "template.json"


def spreadsheet_id():
    return setting("SPREADSHEET_ID")


def open_spreadsheet(sheet_id):
    if not KEY_FILE.exists():
        sys.exit(f"Key file not found: {KEY_FILE}. Set GOOGLE_KEY_FILE in .env.")
    return gspread.service_account(filename=str(KEY_FILE)).open_by_key(sheet_id)
