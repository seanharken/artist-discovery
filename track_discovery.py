import json
from datetime import date
from run_discovery import passes_filters, raw_get, client


def fetch_top_tracks(uuid, limit=5):
    try:
        resp = raw_get(f"/artist/{uuid}/spotify/tracks",
                        {"limit": limit, "sort": "streams", "order": "desc"})
        return resp.get("data", {}).get("data", [])
    except Exception:
        return []


def fetch_spotify_link(uuid):
    try:
        resp = raw_get(f"/artist/{uuid}/links")
        for l in resp.get("data", {}).get("data", []):
            if l.get("channel") == "spotify":
                return l.get("link")
    except Exception:
        pass
    return None


def track_score(t):
    streams_1w = t.get("streams_1w") or 0
    growth = t.get("streams_1w_growth") or 0
    return round(streams_1w * (1 + max(growth, 0) / 100), 1)


def main():
    with open("candidates.json") as f:
        candidates = json.load(f)["candidates"]

    all_tracks = []
    for i, c in enumerate(candidates):
        is_watchlist = "watchlist" in str(c.get("source", ""))
        print(f"[{i+1}/{len(candidates)}] Checking tracks for {c['name']}...")
        if not is_watchlist:
            ok, reason, _ = passes_filters(c["uuid"])
            if not ok:
                print(f"    skipped ({reason})")
                continue

        tracks = fetch_top_tracks(c["uuid"], limit=5)
        spotify_link = fetch_spotify_link(c["uuid"])
        for t in tracks:
            all_tracks.append({
                "artist_name": c["name"],
                "artist_uuid": c["uuid"],
                "artist_tier": c.get("tier"),
                "artist_spotify_url": spotify_link,
                "track_title": t.get("title"),
                "track_spotify_url": f"https://open.spotify.com/track/{t.get('link_id')}" if t.get("link_id") else None,
                "release_date": t.get("release_date"),
                "streams_1d": t.get("streams_1d"),
                "streams_1w": t.get("streams_1w"),
                "streams_1w_growth": t.get("streams_1w_growth"),
                "streams_1m": t.get("streams_1m"),
                "track_score": track_score(t),
            })

    all_tracks.sort(key=lambda x: -x["track_score"])
    top25_tracks = all_tracks[:25]

    out = {"date": str(date.today()), "top_25_tracks": top25_tracks}
    with open("track_discovery.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote top 25 tracks to track_discovery.json ({len(all_tracks)} tracks considered)")


if __name__ == "__main__":
    main()