import json
import os
import statistics
import time
import requests
from datetime import date, timedelta
from viberate_adapter import ViberateClient
from tier_config import (
    TIERS, Z_SCORE_THRESHOLD, MIN_HISTORY_DAYS,
    BASELINE_WINDOW_DAYS, CONFIRMATION_MULTIPLIERS, Z_SCORE_CAP,
)

client = ViberateClient()

API_BASE = "https://data.viberate.com/api/v1"

METRIC_MAP = {
    "spotify_listeners": "spotify_listeners",
    "shazam": "shazam_shazams",
    "soundcloud_plays": "soundcloud_plays",
}

EXCLUDED_GENRES = {"classical", "latin"}
ALLOWED_COUNTRY = "US"


def raw_get(path, params=None):
    """Direct call for endpoints not yet wrapped in viberate_adapter.py."""
    url = f"{API_BASE}{path}"
    headers = {"Access-Key": client.api_key}
    resp = requests.get(url, headers=headers, params=params or {})
    resp.raise_for_status()
    return resp.json()


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def date_range_strs(days_back):
    end = date.today()
    start = end - timedelta(days=days_back)
    return start.isoformat(), end.isoformat()


# ---------- candidate scanning ----------

def scan_tier(tier, sub_buckets=4, page_size=20):
    """Demo key blocks offset > 0 (max 20 results per query, no pagination).
    Split each tier's listener range into sub-ranges queried separately at offset=0."""
    span = tier["range_max"] - tier["range_min"]
    step = span // sub_buckets
    all_artists = []
    for i in range(sub_buckets):
        sub_min = tier["range_min"] + i * step
        sub_max = tier["range_min"] + (i + 1) * step if i < sub_buckets - 1 else tier["range_max"]
        resp = client.artist_chart(
            sort="spotify-listeners", timeframe="1w",
            range_filter="spotify-listeners",
            range_min=sub_min, range_max=sub_max,
            limit=page_size, offset=0,
        )
        all_artists.extend(resp.get("data", []))
        time.sleep(0.3)
    return all_artists


def build_candidates():
    candidates = {}
    for tier in TIERS:
        for a in scan_tier(tier):
            uuid = a.get("uuid")
            if not uuid:
                continue
            candidates[uuid] = {
                "uuid": uuid, "name": a.get("name"),
                "tier": tier["name"], "source": "chart-scan",
                "labels": a.get("labels"),
            }

    watchlist = load_json("watchlist.json", [])
    for a in watchlist:
        uuid = a.get("uuid")
        if not uuid:
            continue
        if uuid not in candidates:
            candidates[uuid] = {
                "uuid": uuid, "name": a.get("name"),
                "tier": "watchlist", "source": "watchlist",
            }
        else:
            candidates[uuid]["source"] = "watchlist+chart-scan"

    out = {"date": str(date.today()), "candidate_count": len(candidates),
           "candidates": list(candidates.values())}
    with open("candidates.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {len(candidates)} candidates to candidates.json")
    return list(candidates.values())


# ---------- filters (genre / country / release year) ----------

def passes_filters(uuid):
    try:
        details = client.get_artist_details(uuid)["data"]
    except Exception:
        return False, "details_fetch_failed", None

    country = details.get("country") or {}
    country_code = country.get("alpha2")
    genre = details.get("genre") or {}
    genre_name = (genre.get("name") or "").strip()

    if country_code != ALLOWED_COUNTRY:
        return False, f"country={country_code or 'unknown'}", genre_name
    if not genre_name:
        return False, "genre=unknown", genre_name
    if genre_name.lower() in EXCLUDED_GENRES:
        return False, f"genre={genre_name}", genre_name

    try:
        tracks_resp = raw_get(f"/artist/{uuid}/spotify/tracks",
                               {"limit": 1, "sort": "release_date", "order": "desc"})
        tracks = tracks_resp.get("data", {}).get("data", [])
    except Exception:
        return False, "tracks_fetch_failed", genre_name

    latest = tracks[0].get("release_date") if tracks else None
    if not latest or not latest.startswith("2026"):
        return False, f"no_2026_release(latest={latest or 'none'})", genre_name

    return True, "ok", genre_name


# ---------- scoring ----------

def tier_for(spotify_listeners):
    for tier in TIERS:
        if tier["range_min"] <= spotify_listeners < tier["range_max"]:
            return tier
    return None


def score_platform(uuid, metric_key, floor):
    metric = METRIC_MAP[metric_key]
    date_from, date_to = date_range_strs(BASELINE_WINDOW_DAYS + 5)
    try:
        resp = client.get_artist_stats(uuid, metric, period="daily", graph_mode="diff",
                                        date_from=date_from, date_to=date_to)
        diffs = resp["data"]["data"]["diff"]
    except Exception as e:
        return {"status": "error", "error": str(e)}

    dated = sorted(diffs.items())
    if not dated:
        return {"status": "no_data"}

    latest_date, latest_delta = dated[-1]
    baseline_vals = [v for _, v in dated[:-1]][-BASELINE_WINDOW_DAYS:]
    above_floor = latest_delta >= floor
    recent_series = [v for _, v in dated[-7:]]

    if len(baseline_vals) < MIN_HISTORY_DAYS:
        return {"status": "low_confidence", "latest_delta": latest_delta,
                "above_floor": above_floor, "z_score": None,
                "recent_series": recent_series, "days_tracked": len(dated)}

    mean = statistics.mean(baseline_vals)
    stdev = statistics.pstdev(baseline_vals) or 1e-9
    z = (latest_delta - mean) / stdev
    z = max(min(z, Z_SCORE_CAP), -Z_SCORE_CAP)

    status = "confirmed" if (above_floor and z >= Z_SCORE_THRESHOLD) else ("floor_only" if above_floor else "flat")
    return {"status": status, "latest_delta": latest_delta, "above_floor": above_floor,
            "z_score": round(z, 2), "recent_series": recent_series, "days_tracked": len(dated)}


def score_artist(uuid, name, current_spotify_listeners, labels=None):
    tier = tier_for(current_spotify_listeners)
    if tier is None:
        return None
    platform_results, confirming, weighted = {}, 0, 0.0
    for metric_key, floor in tier["floors"].items():
        weight = tier["weights"].get(metric_key, 1.0)
        result = score_platform(uuid, metric_key, floor)
        platform_results[metric_key] = result
        if result.get("status") in ("confirmed", "floor_only"):
            confirming += 1
            weighted += weight * max(result.get("z_score") or 1.0, 0.5)
    multiplier = CONFIRMATION_MULTIPLIERS.get(min(confirming, 3), 1.0)
    labels = labels or []
    label_status = ", ".join(l.get("display_name", l.get("name", "Unknown")) for l in labels) or "Unknown"
    label_status_flag = any(l.get("id") not in (6, 7) for l in labels)
    return {"uuid": uuid, "name": name, "tier": tier["name"],
            "current_spotify_listeners": current_spotify_listeners,
            "confirming_platforms": confirming, "confirmation_multiplier": multiplier,
            "score": round(weighted * multiplier, 2),
            "label_status_flag": label_status_flag, "label_status": label_status,
            "platforms": platform_results}


def score_all(candidates):
    results = []
    for i, c in enumerate(candidates):
        is_watchlist = "watchlist" in str(c.get("source", ""))
        print(f"[{i+1}/{len(candidates)}] Scoring {c['name']}...")

        genre_name = None
        if not is_watchlist:
            ok, reason, genre_name = passes_filters(c["uuid"])
            if not ok:
                print(f"    skipped ({reason})")
                continue

        try:
            chart_hit = client.artist_chart(uuid=c["uuid"], limit=1)["data"]
            current_listeners = chart_hit[0]["charts"]["spotify"]["overall"]["listeners"]["total"] if chart_hit else 0
        except Exception:
            current_listeners = 0
        scored = score_artist(c["uuid"], c["name"], current_listeners, c.get("labels"))
        if scored:
            scored["source"] = c.get("source", "chart-scan")
            if genre_name:
                scored["genre"] = genre_name
            results.append(scored)
        elif is_watchlist:
            results.append({"uuid": c["uuid"], "name": c["name"], "tier": "watchlist (untiered)",
                             "score": 0, "source": c.get("source"), "note": "guaranteed inclusion"})
    return results


# ---------- archiving ----------

def archive_snapshot(discovery_data):
    os.makedirs("history", exist_ok=True)
    path = f"history/discovery_results_{discovery_data['date']}.json"
    with open(path, "w") as f:
        json.dump(discovery_data, f, indent=2)
    print(f"Archived today's snapshot to {path}")


def main():
    candidates = build_candidates()
    results = score_all(candidates)

    watchlist_items = [r for r in results if str(r.get("source", "")).startswith("watchlist")]
    scanned = [r for r in results if not str(r.get("source", "")).startswith("watchlist")]
    scanned.sort(key=lambda r: (r.get("label_status_flag", False), -r["score"]))
    top25 = scanned[:25]

    discovery_data = {"date": str(date.today()), "top_25_discovery": top25,
                       "watchlist_status": watchlist_items}

    with open("discovery_results.json", "w") as f:
        json.dump(discovery_data, f, indent=2)
    print(f"Wrote top 25 to discovery_results.json ({len(scanned)} candidates scored)")

    archive_snapshot(discovery_data)


if __name__ == "__main__":
    main()