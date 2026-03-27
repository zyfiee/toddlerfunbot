import requests
import math
from config import GOOGLE_API_KEY

# ── Config ─────────────────────────────────────────────

SEARCH_RADIUS_METERS = 2000
MAX_DISTANCE_METERS = 2000
API_RESULT_COUNT = 15
FINAL_RESULTS = 5

CATEGORY_QUERIES = {
    "outdoors": [
        "playground",
        "kids playground",
        "park playground"
    ],
    "indoors": [
        "indoor playground",
        "kids play centre"
    ],
    "food": [
        "family friendly restaurant",
        "kids friendly cafe",
        "cafe with play area",
        "restaurant playground"
    ],
}

# 🔍 Review keywords
POSITIVE_KEYWORDS = [
    "kid", "kids", "child", "children",
    "family", "family-friendly",
    "play", "playground", "play area",
    "toddler", "baby"
]

NEGATIVE_KEYWORDS = [
    "not kid", "not for kids", "no kids",
    "crowded", "unsafe", "dirty"
]


# ── Distance ───────────────────────────────────────────

def haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def format_distance(metres):
    if metres < 1000:
        return f"{int(metres)}m"
    return f"{metres / 1000:.1f}km"


# ── Review Scoring ─────────────────────────────────────

def score_reviews(place):
    reviews = place.get("reviews", [])
    score = 0

    for r in reviews:
        text = (r.get("text", {}).get("text") or "").lower()

        # positive signals
        for kw in POSITIVE_KEYWORDS:
            if kw in text:
                score += 2

        # negative signals
        for kw in NEGATIVE_KEYWORDS:
            if kw in text:
                score -= 3

    return score


# ── Ranking ────────────────────────────────────────────

def ranking_score(place):
    distance = place["_distance_m"]
    rating = place.get("rating") or 0
    reviews = place.get("userRatingCount") or 0
    review_score = place.get("_review_score", 0)

    return (
        distance,
        -review_score,           # 🔥 NEW: prioritise kid-friendly signal
        -rating,
        -min(reviews, 1000),
    )


# ── Core search ────────────────────────────────────────

def search_places(lat, lng, category):
    queries = CATEGORY_QUERIES.get(category, [])
    results = []
    seen_ids = set()

    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.rating,places.userRatingCount,places.googleMapsUri,"
            "places.currentOpeningHours,places.location,"
            "places.reviews"  # 🔥 IMPORTANT
        ),
    }

    for query in queries:
        payload = {
            "textQuery": query,
            "rankPreference": "DISTANCE",
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": SEARCH_RADIUS_METERS,
                }
            },
            "maxResultCount": API_RESULT_COUNT,
        }

        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        for place in data.get("places", []):
            pid = place.get("id")
            if not pid or pid in seen_ids:
                continue

            seen_ids.add(pid)

            loc = place.get("location", {})
            place_lat = loc.get("latitude")
            place_lng = loc.get("longitude")

            if not place_lat or not place_lng:
                continue

            distance = haversine_distance(lat, lng, place_lat, place_lng)

            # 🔥 HARD FILTER
            if distance > MAX_DISTANCE_METERS:
                continue

            rating = place.get("rating") or 0
            reviews_count = place.get("userRatingCount") or 0

            # ── Category-specific logic ──

            if category == "food":
                if rating < 3.8 or reviews_count < 20:
                    continue

                review_score = score_reviews(place)
                place["_review_score"] = review_score

                # 🔥 Require positive signal
                if review_score < 2:
                    continue

            else:
                if rating < 3.5 or reviews_count < 5:
                    continue

                place["_review_score"] = 0

            place["_distance_m"] = distance
            results.append(place)

    results.sort(key=ranking_score)

    return results[:FINAL_RESULTS]


# ── Map links ──────────────────────────────────────────

def build_map_links(place):
    loc = place.get("location", {})
    lat = loc.get("latitude")
    lng = loc.get("longitude")

    links = []
    if lat and lng:
        links.append(("🗺 Google Maps", f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"))
        links.append(("📍 Waze", f"https://waze.com/ul?ll={lat},{lng}&navigate=yes"))
        links.append(("🍎 Apple Maps", f"https://maps.apple.com/?q={lat},{lng}"))

    return links


# ── Formatter ──────────────────────────────────────────

def format_place(place, index):
    name = place.get("displayName", {}).get("text", "Unknown")
    address = place.get("formattedAddress", "No address available")
    rating = place.get("rating", "N/A")
    reviews = place.get("userRatingCount", 0)
    distance = format_distance(place.get("_distance_m", 0))

    hours_info = place.get("currentOpeningHours", {})
    open_now = hours_info.get("openNow")

    if open_now is True:
        status = "🟢 Open now"
    elif open_now is False:
        status = "🔴 Closed now"
    else:
        status = "⚪ Hours unknown"

    return (
        f"*{index}. {name}*\n"
        f"📏 {distance} away\n"
        f"🏠 {address}\n"
        f"⭐ {rating} ({reviews} reviews) · {status}"
    )
