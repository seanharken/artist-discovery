import json
from datetime import date
from viberate_adapter import ViberateClient
from spotify_fallback import get_artist

client = ViberateClient()

def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def main():
    pending = load_json("pending_watchlist.json", [])
    watchlist = load_json("watchlist.json", [])
    still_pending = []

    for artist in pending:
        try:
            result = client._get(f"/artist/by-channel/spotify/{artist['spotify_id']}")
            uuid = result["data"]["uuid"]
            watchlist.append({"name": artist["name"], "uuid": uuid})
            print(f"Promoted {artist['name']} to watchlist.json (now Viberate-indexed)")
        except Exception:
            snapshot = get_artist(artist["spotify_id"])
            snapshot["date"] = str(date.today())
            artist["last_spotify_snapshot"] = snapshot
            still_pending.append(artist)
            print(f"{artist['name']} still not on Viberate - saved Spotify fallback snapshot")

    with open("watchlist.json", "w") as f:
        json.dump(watchlist, f, indent=2)
    with open("pending_watchlist.json", "w") as f:
        json.dump(still_pending, f, indent=2)

if __name__ == "__main__":
    main()