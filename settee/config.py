"""The settings file (config.json in the data folder): channels, place, news feed, photo folder and the look.
Everything read from disk or from the settings page goes through clean(), so a broken file never stops the TV."""
import json
import os
import threading
from pathlib import Path

LOOKS = ("evening", "daylight")
ACCENTS = ("marigold", "coral", "sage", "sky", "plum")
LANGUAGES = ("en", "sv")
KINDS = ("web", "app")
MAX_CHANNELS = 30
FEEDS = {"en": "https://feeds.bbci.co.uk/news/world/rss.xml", "sv": "https://www.svt.se/nyheter/rss.xml"}

DEFAULT_CHANNELS = [
    {"name": "YouTube", "kind": "web", "target": "https://www.youtube.com/"},
    {"name": "Netflix", "kind": "web", "target": "https://www.netflix.com/"},
    {"name": "Spotify", "kind": "web", "target": "https://open.spotify.com/"},
    {"name": "Wikipedia", "kind": "web", "target": "https://www.wikipedia.org/"},
    {"name": "Radio Garden", "kind": "web", "target": "https://radio.garden/"},
]

_LOCK = threading.Lock()


def default_photos():
    return str(Path.home() / "Pictures")


def defaults():
    return {"language": "en", "look": "evening", "accent": "marigold", "place": None,  # asked on the settings page: no one's home town by default
            "news": FEEDS["en"], "photos": default_photos(), "channels": [dict(c) for c in DEFAULT_CHANNELS]}


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def clean_channel(c):
    """One channel, or None: a web channel needs an http(s) address, an app channel a path to a program."""
    if not isinstance(c, dict):
        return None
    name, kind, target = _text(c.get("name"), 40), c.get("kind"), _text(c.get("target"), 500)
    if not name or kind not in KINDS or not target:
        return None
    if kind == "web" and not target.lower().startswith(("http://", "https://")):
        return None
    return {"name": name, "kind": kind, "target": target}


def clean(raw):
    """Any JSON value -> a complete, valid settings dict (unknown or bad fields fall back to the defaults)."""
    d = defaults()
    raw = raw if isinstance(raw, dict) else {}
    for key, allowed in (("language", LANGUAGES), ("look", LOOKS), ("accent", ACCENTS)):
        if raw.get(key) in allowed:
            d[key] = raw[key]
    if "news" not in raw or not isinstance(raw.get("news"), str):
        d["news"] = FEEDS[d["language"]]
    elif raw["news"].strip() == "" or raw["news"].strip().lower().startswith(("http://", "https://")):
        d["news"] = raw["news"].strip()[:500]  # "" turns the news off
    place = raw.get("place")
    if isinstance(place, dict):
        try:
            lat, lon = float(place.get("lat")), float(place.get("lon"))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                d["place"] = {"name": _text(place.get("name"), 60) or "?", "lat": round(lat, 4), "lon": round(lon, 4)}
        except (TypeError, ValueError):
            pass
    if isinstance(raw.get("photos"), str):
        d["photos"] = raw["photos"].strip()[:500]
    if isinstance(raw.get("channels"), list):
        d["channels"] = [c for c in map(clean_channel, raw["channels"]) if c][:MAX_CHANNELS]
    return d


class Settings:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.path = self.folder / "config.json"

    def load(self):
        try:
            return clean(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return defaults()

    def save(self, raw):
        """Cleans and writes atomically -> the saved settings."""
        data = clean(raw)
        with _LOCK:
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(str(tmp), str(self.path))
        return data
