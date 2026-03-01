"""Configuration — loads environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Bot owner's Telegram user ID

if not all([BOT_TOKEN, API_ID, API_HASH]):
    raise ValueError("BOT_TOKEN, API_ID, and API_HASH must be set in .env")
