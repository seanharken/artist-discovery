import json
import requests
from datetime import date, timedelta
from viberate_adapter import ViberateClient
from tier_config import MIN_HISTORY_DAYS

client = ViberateClient()
API_BASE = "https://data.viberate.com/api/v1"

PLATFORM_INFO = {
    "spotify_listeners": {"badge": "spotify", "label": "Spotify monthly listeners"},
    "shazam": {"badge": "shazam", "label": "Shazam recognitions"},
    "soundcloud_plays": {"badge": "soundcloud", "label": "SoundCloud plays"},
}
METRIC_MAP = {
    "spotify_listeners": "spotify_listeners",
    "shazam": "shazam_shazams",
    "soundcloud_plays": "soundcloud_plays",
}


def raw_get(path, params=None):
    url = f"{API_BASE}{path}"
    headers = {"Access-Key": client.api_key}
    resp = requests.get(url, headers=headers, params=params or {})
    resp.raise_for_status()
    return resp.json()


def date_range_strs(days_back):
    end = date.today()
    start = end - timedelta(days=days_back)
    return start.isoformat(), end.isoformat()


def fetch_genre(uuid):
    try:
        details = client.get_artist_details(uuid)["data"]
        genre = details.get("genre")
        if isinstance(genre, dict):
            return genre.get("name", "unknown")
        return genre or "unknown"
    except Exception:
        return "unknown"


def fetch_spotify_url(uuid):
    try:
        resp = raw_get(f"/artist/{uuid}/links")
        links = resp.get("data", {}).get("data", [])
        for l in links:
            if l.get("channel") == "spotify":
                return l.get("link")
    except Exception:
        pass
    return None


def fetch_total_series(uuid, metric_key):
    metric = METRIC_MAP[metric_key]
    date_from, date_to = date_range_strs(7)
    try:
        resp = client.get_artist_stats(uuid, metric, period="daily", graph_mode="total",
                                        date_from=date_from, date_to=date_to)
        totals = resp["data"]["data"]["total"]
    except Exception:
        return []
    dated = sorted(totals.items())
    return [v for _, v in dated]


def build_why(platform_results, confirming):
    parts, triggered = [], []
    for metric_key, result in platform_results.items():
        if result.get("status") in ("confirmed", "floor_only") and result.get("latest_delta") is not None:
            info = PLATFORM_INFO[metric_key]
            parts.append(f"{info['label']} +{result['latest_delta']}")
            triggered.append(info["badge"])
    detail = "; ".join(parts) if parts else "no platform cleared its floor yet"
    if confirming >= 2:
        tail = "Multi-platform confirmed."
    elif confirming == 1:
        tail = "Single platform, not yet cross-confirmed."
    else:
        tail = "No platform confirmed yet."
    trigger_str = ", ".join(triggered) if triggered else "none"
    return f"Cleared floor on {trigger_str} ({detail}). {tail}", triggered


def build_dashboard_entry(artist_result):
    platforms = artist_result.get("platforms", {})
    why, triggers = build_why(platforms, artist_result.get("confirming_platforms", 0))

    metrics = []
    overall_spark = None
    max_days_tracked = 0
    for metric_key, result in platforms.items():
        max_days_tracked = max(max_days_tracked, result.get("days_tracked", 0))
        if result.get("status") in ("confirmed", "floor_only"):
            series = fetch_total_series(artist_result["uuid"], metric_key)
            if not series:
                continue
            info = PLATFORM_INFO[metric_key]
            delta = series[-1] - series[0] if len(series) > 1 else 0
            metrics.append({
                "label": info["label"],
                "value": str(series[-1]),
                "delta": f"{delta:+d}",
                "spark": series,
            })
            if overall_spark is None:
                overall_spark = series

    return {
        "name": artist_result.get("name"),
        "genre": artist_result.get("genre") or fetch_genre(artist_result["uuid"]),
        "score": artist_result.get("score", 0),
        "maturity": max_days_tracked,
        "triggers": triggers or ["spotify"],
        "why": why,
        "metrics": metrics,
        "spark": overall_spark or [0, 0, 0, 0, 0, 0, 0],
        "flags": ["new"] if max_days_tracked < MIN_HISTORY_DAYS else [],
        "spotify_url": fetch_spotify_url(artist_result["uuid"]),
    }


def main():
    with open("discovery_results.json") as f:
        data = json.load(f)
    top25 = data.get("top_25_discovery", [])

    dashboard_artists = []
    for i, artist in enumerate(top25):
        print(f"[{i+1}/{len(top25)}] Enriching {artist['name']} for dashboard...")
        dashboard_artists.append(build_dashboard_entry(artist))

    with open("dashboard_data.json", "w") as f:
        json.dump({"date": data.get("date"), "artists": dashboard_artists}, f, indent=2)
    print(f"Wrote {len(dashboard_artists)} artists to dashboard_data.json")


if __name__ == "__main__":
    main()