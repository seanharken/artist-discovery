import json

with open("track_discovery.json") as f:
    data = json.load(f)

tracks = data.get("top_25_tracks", [])
rows = ""
for i, t in enumerate(tracks):
    artist_link = (f'<a href="{t["artist_spotify_url"]}" target="_blank">{t["artist_name"]}</a>'
                   if t.get("artist_spotify_url") else t["artist_name"])
    track_link = (f'<a href="{t["track_spotify_url"]}" target="_blank">{t["track_title"]}</a>'
                  if t.get("track_spotify_url") else t["track_title"])
    rows += f"""
    <tr>
      <td>{i+1}</td>
      <td>{track_link}</td>
      <td>{artist_link}</td>
      <td>{t.get("artist_tier","")}</td>
      <td>{t.get("streams_1w","")}</td>
      <td>{t.get("streams_1w_growth","")}%</td>
      <td>{t.get("track_score","")}</td>
    </tr>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Top 25 Tracks - {data.get('date','')}</title>
<style>
  body {{ background:#14161a; color:#ece8e0; font-family: -apple-system, sans-serif; padding: 30px; }}
  h1 {{ font-size: 22px; }}
  table {{ width:100%; border-collapse: collapse; margin-top: 20px; }}
  th, td {{ text-align:left; padding: 8px 10px; border-bottom: 1px solid #2b2f38; font-size: 14px; }}
  th {{ color:#888c98; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; }}
  a {{ color:#d9a441; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
</style>
</head>
<body>
<h1>Top 25 Tracks - {data.get('date','')}</h1>
<table>
<tr><th>#</th><th>Track</th><th>Artist</th><th>Tier</th><th>Streams (7d)</th><th>7d Growth</th><th>Score</th></tr>
{rows}
</table>
</body>
</html>"""

with open("tracks_dashboard.html", "w") as f:
    f.write(html)
print(f"Wrote tracks_dashboard.html with {len(tracks)} tracks.")