import json
import time
from datetime import date
from viberate_adapter import ViberateClient
from tier_config import TIERS

client = ViberateClient()

def scan_tier(tier, sub_buckets=4, page_size=20):
    """The demo key blocks offset > 0 (max 20 results per query, no pagination).
    To still get a broad pool, we split each tier's listener range into smaller
    sub-ranges and query each one separately at offset=0."""
    span = tier["range_max"] - tier["range_min"]
    step = span // sub_buckets
    all_artists = []
    for i in range(sub_buckets):
        sub_min = tier["range_min"] + i * step
        sub_max = tier["range_min"] + (i + 1) * step if i < sub_buckets - 1 else tier["range_max"]
        resp = client.artist_chart(
            sort="spotify-listeners",
            timeframe="1w",
            range_filter="spotify-listeners",
            range_min=sub_min,
            range_max=sub_max,
            limit=page_size,
            offset=0,
        )
        all_artists.extend(resp.get("data", []))
        time.sleep(0.3)
    return all_artists

def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def main():
    candidates = {}
    for tier in TIERS:
        for a in scan_tier(tier):
            uuid = a.get("uuid")
            if not uuid:
                continue
            candidates[uuid] = {"uuid": uuid, "name": a.get("name"),
                                 "tier": tier["name"], "source": "chart-scan",
                                 "labels": a.get("labels")}

    watchlist = load_json("watchlist.json", [])
    for a in watchlist:
        uuid = a.get("uuid")
        if not uuid:
            continue
        if uuid not in candidates:
            candidates[uuid] = {"uuid": uuid, "name": a.get("name"),
                                 "tier": "watchlist", "source": "watchlist"}
        else:
            candidates[uuid]["source"] = "watchlist+chart-scan"

    out = {"date": str(date.today()), "candidate_count": len(candidates),
           "candidates": list(candidates.values())}
    with open("candidates.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {len(candidates)} candidates to candidates.json")

if __name__ == "__main__":
    main()