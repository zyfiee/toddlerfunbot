import os

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
SEARCH_RADIUS_METERS = int(os.environ.get("SEARCH_RADIUS_METERS", 2000))
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", 5))
