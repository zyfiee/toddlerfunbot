import requests
import math
from config import GOOGLE_API_KEY, SEARCH_RADIUS_METERS, MAX_RESULTS

CATEGORY_QUERIES = {
    "outdoors": ["playground", "park"],
    "indoors": ["indoor play centre", "children's play area", "kids indoor playground"],
}


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate straight-line distance in metres between two coordinates."""
    R = 6371000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def format_distance(metres: float) -> str:
    if metres < 1000:
        return f"{int(metres)}m"
    return f"{metres / 1000:.1f}km"


def search_places(lat: float, lng: float, category: str) -> list[dict]:
    """Search Google Places API (New), deduplicate, sort by proximity."""
    queries = CATEGORY_QUERIES.get(category, [])
    results = []
    seen_ids = set()

    for query in queries:
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
        payload = {
            "textQuery": query,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": SEARCH_RADIUS_METERS,
                }
            },
            "maxResultCount": MAX_RESULTS,
        }

        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        for place in data.get("places", []):
            pid = place.get("id")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)

                # Attach calculated distance from user
                place_lat = place.get("location", {}).get("latitude")
                place_lng = place.get("location", {}).get("longitude")
                if place_lat and place_lng:
                    place["_distance_m"] = haversine_distance(lat, lng, place_lat, place_lng)
                else:
                    place["_distance_m"] = float("inf")

                results.append(place)

    # Sort by proximity — closest first
    results.sort(key=lambda p: p["_distance_m"])

    return results[:MAX_RESULTS]


def build_map_links(place: dict) -> list[tuple[str, str]]:
    """Return (label, url) tuples for Google Maps, Waze, and Apple Maps."""
    loc = place.get("location", {})
    lat = loc.get("latitude")
    lng = loc.get("longitude")
    name = place.get("displayName", {}).get("text", "")

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


def format_place(place: dict, index: int) -> str:
    """Format a single place as a Telegram message string."""
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
