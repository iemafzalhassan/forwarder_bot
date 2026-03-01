"""Configuration — loads environment variables."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_HASH = os.getenv("API_HASH", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# API_ID must be a valid 32-bit integer (max 2,147,483,647)
_raw_api_id = os.getenv("API_ID", "0").strip()
try:
    API_ID = int(_raw_api_id)
except ValueError:
    print(f"❌ FATAL: API_ID is not a valid number: '{_raw_api_id}'", file=sys.stderr)
    sys.exit(1)

if API_ID > 2_147_483_647 or API_ID <= 0:
    print(f"❌ FATAL: API_ID={API_ID} is invalid! Must be between 1 and 2147483647.", file=sys.stderr)
    print(f"   Check your .env file. Raw value was: '{_raw_api_id}'", file=sys.stderr)
    sys.exit(1)

if not all([BOT_TOKEN, API_ID, API_HASH]):
    print("❌ FATAL: BOT_TOKEN, API_ID, and API_HASH must be set in .env", file=sys.stderr)
    print(f"   BOT_TOKEN={'SET' if BOT_TOKEN else 'MISSING'}", file=sys.stderr)
    print(f"   API_ID={API_ID}", file=sys.stderr)
    print(f"   API_HASH={'SET' if API_HASH else 'MISSING'}", file=sys.stderr)
    sys.exit(1)

print(f"✅ Config loaded: API_ID={API_ID}, ADMIN_ID={ADMIN_ID}")
