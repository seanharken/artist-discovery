# Note: unused — early exploration of a direct Spotify Web API integration.
# The final pipeline uses Viberate's unified stats endpoint instead, which
# covers Spotify, Shazam, and SoundCloud without needing separate API keys.

import os
import time
import requests

TOKEN_CACHE = {"token": None, "expires_at": 0}

def get_token():
    if TOKEN_CACHE["token"] and time.time() < TOKEN_CACHE["expires_at"]:
        return TOKEN_CACHE["token"]
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"]),
    )
    resp.raise_for_status()
    data = resp.json()
    TOKEN_CACHE["token"] = data["access_token"]
    TOKEN_CACHE["expires_at"] = time.time() + data["expires_in"] - 60
    return TOKEN_CACHE["token"]

def get_artist(spotify_id):
    token = get_token()
    resp = requests.get(
        f"https://api.spotify.com/v1/artists/{spotify_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "name": data.get("name"),
        "followers": data.get("followers", {}).get("total"),
        "popularity": data.get("popularity"),
        "genres": data.get("genres", []),
    }