import os

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # e.g. https://your-app.railway.app
SEARCH_RADIUS_METERS = int(os.environ.get("SEARCH_RADIUS_METERS", 2000))
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", 5))
PORT = int(os.environ.get("PORT", 8080))
