TIERS = [
    {
        "name": "Tier 0 - Emerging",
        "range_min": 1000, "range_max": 10000,
        "floors": {"spotify_listeners": 150, "shazam": 20, "soundcloud_plays": 150},
        "weights": {"spotify_listeners": 1.0, "shazam": 1.2, "soundcloud_plays": 1.0},
    },
    {
        "name": "Tier 1 - Developing",
        "range_min": 10000, "range_max": 30000,
        "floors": {"spotify_listeners": 300, "shazam": 40, "soundcloud_plays": 300},
        "weights": {"spotify_listeners": 1.0, "shazam": 1.1, "soundcloud_plays": 1.0},
    },
    {
        "name": "Tier 2 - Growth/Graduate Watch",
        "range_min": 30000, "range_max": 50000,
        "floors": {"spotify_listeners": 500, "shazam": 60, "soundcloud_plays": 500},
        "weights": {"spotify_listeners": 1.0, "shazam": 1.0, "soundcloud_plays": 1.0},
    },
]

NOISE_FLOOR = 1000
GRADUATE_CEILING = 50000
Z_SCORE_THRESHOLD = 2.5
Z_SCORE_CAP = 10
MIN_HISTORY_DAYS = 10
BASELINE_WINDOW_DAYS = 28
CONFIRMATION_MULTIPLIERS = {1: 1.0, 2: 1.5, 3: 2.0}
LABEL_STATUS_DEMOTE = True

LABEL_NAMES = {
    1: "UMG",
    2: "Sony (SME)",
    3: "Warner (WMG)",
    4: "BMG",
    5: "Big Indie",
    6: "Other Indie / Unsigned",
    7: "No Release in 5yrs",
}