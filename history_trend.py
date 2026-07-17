import argparse
import glob
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    args = parser.parse_args()

    rows = []
    for path in sorted(glob.glob("history/discovery_results_*.json")):
        with open(path) as f:
            data = json.load(f)
        pool = data.get("top_25_discovery", []) + data.get("watchlist_status", [])
        for artist in pool:
            if artist.get("name", "").lower() == args.name.lower():
                rows.append((data.get("date"), artist.get("score"), artist.get("current_spotify_listeners")))

    if not rows:
        print(f"No history found yet for '{args.name}'.")
        return

    print(f"History for {args.name}:")
    for d, score, listeners in rows:
        print(f"  {d}: score={score}  spotify_listeners={listeners}")


if __name__ == "__main__":
    main()