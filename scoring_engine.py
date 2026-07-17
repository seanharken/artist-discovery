import json
import statistics
from datetime import date, timedelta
from viberate_adapter import ViberateClient
from tier_config import TIERS, Z_SCORE_THRESHOLD, MIN_HISTORY_DAYS, BASELINE_WINDOW_DAYS, CONFIRMATION_MULTIPLIERS, Z_SCORE_CAP

client = ViberateClient()

METRIC_MAP = {
    "spotify_listeners": "spotify_listeners",
    "shazam": "shazam_shazams",
    "soundcloud_plays": "soundcloud_plays",
}

def date_range_strs(days_back):
    end = date.today()
    start = end - timedelta(days=days_back)
    return start.isoformat(), end.isoformat()

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

    if len(baseline_vals) < MIN_HISTORY_DAYS:
        return {"status": "low_confidence", "latest_delta": latest_delta,
                "above_floor": above_floor, "z_score": None}

    mean = statistics.mean(baseline_vals)
    stdev = statistics.pstdev(baseline_vals) or 1e-9
    z = (latest_delta - mean) / stdev
    z = max(min(z, Z_SCORE_CAP), -Z_SCORE_CAP)

    status = "confirmed" if (above_floor and z >= Z_SCORE_THRESHOLD) else ("floor_only" if above_floor else "flat")
    return {"status": status, "latest_delta": latest_delta, "above_floor": above_floor, "z_score": round(z, 2)}

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

def main():
    with open("candidates.json") as f:
        candidates = json.load(f)["candidates"]
    results = []
    for i, c in enumerate(candidates):
        print(f"[{i+1}/{len(candidates)}] Scoring {c['name']}...")
        try:
            chart_hit = client.artist_chart(uuid=c["uuid"], limit=1)["data"]
            current_listeners = chart_hit[0]["charts"]["spotify"]["overall"]["listeners"]["total"] if chart_hit else 0
        except Exception:
            current_listeners = 0
        scored = score_artist(c["uuid"], c["name"], current_listeners, c.get("labels"))
        if scored:
            scored["source"] = c.get("source", "chart-scan")
            results.append(scored)
        elif str(c.get("source", "")).startswith("watchlist"):
            results.append({"uuid": c["uuid"], "name": c["name"], "tier": "watchlist (untiered)",
                             "score": 0, "source": c.get("source"), "note": "guaranteed inclusion"})

    watchlist_items = [r for r in results if str(r.get("source", "")).startswith("watchlist")]
    scanned = [r for r in results if not str(r.get("source", "")).startswith("watchlist")]
    scanned.sort(key=lambda r: (r.get("label_status_flag", False), -r["score"]))
    top25 = scanned[:25]

    with open("discovery_results.json", "w") as f:
        json.dump({"date": str(date.today()), "top_25_discovery": top25,
                   "watchlist_status": watchlist_items}, f, indent=2)
    print(f"Wrote top 25 to discovery_results.json ({len(scanned)} candidates scored)")

if __name__ == "__main__":
    main()