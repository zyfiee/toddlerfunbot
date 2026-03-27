import requests
import math
from config import GOOGLE_API_KEY

# 🔧 Tunable constants
SEARCH_RADIUS_METERS = 2000        # Soft bias
MAX_DISTANCE_METERS = 2000         # HARD cutoff
API_RESULT_COUNT = 15              # Fetch more, filter later
FINAL_RESULTS = 5                  # What user sees

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
}


# ── Distance helpers ─────────────────────────────────────────────

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def format_distance(metres: float) -> str:
    if metres < 1000:
        return f"{int(metres)}m"
    return f"{metres / 1000:.1f}km"


# ── Ranking logic (Google-like) ─────────────────────────────────

def ranking_score(place: dict):
    distance = place["_distance_m"]
    rating = place.get("rating") or 0
    reviews = place.get("userRatingCount") or 0

    return (
        distance,                 # closest first
        -rating,                  # higher rating first
        -min(reviews, 1000),      # popularity (capped)
    )


# ── Core search ─────────────────────────────────────────────────

def search_places(lat: float, lng: float, category: str) -> list[dict]:
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
            "places.currentOpeningHours,places.location"
        ),
    }

    for query in queries:
        payload = {
            "textQuery": query,
            "rankPreference": "DISTANCE",  # 🔥 critical
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

            # Get coordinates
            place_lat = place.get("location", {}).get("latitude")
            place_lng = place.get("location", {}).get("longitude")

            if not place_lat or not place_lng:
                continue

            # Calculate distance
            distance = haversine_distance(lat, lng, place_lat, place_lng)

            # 🔥 HARD FILTER (no >2km results EVER)
            if distance > MAX_DISTANCE_METERS:
                continue

            # Optional quality filters (huge UX improvement)
            rating = place.get("rating") or 0
            reviews = place.get("userRatingCount") or 0

            if rating < 3.5 or reviews < 5:
                continue

            place["_distance_m"] = distance
            results.append(place)

    # Sort like Google Maps (distance + quality)
    results.sort(key=ranking_score)

    return results[:FINAL_RESULTS]


# ── Map links ───────────────────────────────────────────────────

def build_map_links(place: dict) -> list[tuple[str, str]]:
    loc = place.get("location", {})
    lat = loc.get("latitude")
    lng = loc.get("longitude")

    links = []
    if lat and lng:
        links.append((
            "🗺 Google Maps",
            f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        ))
        links.append((
            "📍 Waze",
            f"https://waze.com/ul?ll={lat},{lng}&navigate=yes"
        ))
        links.append((
            "🍎 Apple Maps",
            f"https://maps.apple.com/?q={lat},{lng}"
        ))

    return links


# ── Formatter ───────────────────────────────────────────────────

def format_place(place: dict, index: int) -> str:
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
