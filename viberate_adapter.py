import os
import time
import requests

class ViberateClient:
    BASE_URL = "https://data.viberate.com/api/v1"

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ["VIBERATE_API_KEY"]

    def _get(self, path, params=None):
        url = f"{self.BASE_URL}{path}"
        headers = {"Access-Key": self.api_key}
        for attempt in range(3):
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()

    def search_artist(self, q, limit=5, offset=0):
        """GET /artist/search - search artists by name."""
        return self._get("/artist/search", params={"q": q, "limit": limit, "offset": offset})

    def get_artist_stats(self, uuid, metric, period="daily", graph_mode="diff",
                          date_from=None, date_to=None):
        """
        GET /artist/{uuid}/stats - unified metric endpoint, verified live this session.
        metric options include: spotify_listeners, spotify_followers, spotify_streams,
        spotify_popularity, soundcloud_plays, soundcloud_followers, shazam_shazams,
        tiktok_views, tiktok_followers, instagram_followers, youtube_subscribers, etc.
        graph_mode: "" (both), "total", or "diff". period: daily/weekly/monthly.
        Returns up to ~18 months of history on the current demo key (verified: data
        back to 2025-01-14 works, earlier raises history_depth_exceeded).
        """
        params = {"metric": metric, "period": period}
        if graph_mode:
            params["graph-mode"] = graph_mode
        if date_from:
            params["date-from"] = date_from
        if date_to:
            params["date-to"] = date_to
        return self._get(f"/artist/{uuid}/stats", params=params)

    def get_artist_details(self, uuid):
        """GET /artist/{uuid}/details - bio/metadata (genre, country, verified, rank). No listener counts here."""
        return self._get(f"/artist/{uuid}/details")

    def artist_chart(self, sort="spotify-listeners", timeframe="1w", range_filter=None,
                      range_min=None, range_max=None, labels=None, genres=None,
                      limit=100, offset=0, **extra_params):
        """GET /artist/viberate/chart - global leaderboard, used as the broad discovery feed."""
        params = {"sort": sort, "timeframe": timeframe, "limit": limit, "offset": offset}
        if range_filter: params["range-filter"] = range_filter
        if range_min is not None: params["range-min"] = range_min
        if range_max is not None: params["range-max"] = range_max
        if labels: params["labels"] = labels
        if genres: params["genres"] = genres
        params.update(extra_params)
        return self._get("/artist/viberate/chart", params=params)